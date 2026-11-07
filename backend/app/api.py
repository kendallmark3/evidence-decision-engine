"""FastAPI surface for the Evidence Decision Engine.

Synchronous for V1: POST /api/evaluations runs the graph until it pauses for the
architect. POST /api/evaluations/{id}/review resumes the saved graph state.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from .graph import build_graph
from .policy import load_policies

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
DATA_DIR = Path(os.getenv("EDE_DATA_DIR", ROOT / "data"))
FRONTEND_DIST = ROOT.parent / "frontend" / "dist"


class EvaluateRequest(BaseModel):
    config: dict[str, Any]


class ReviewRequest(BaseModel):
    action: Literal["approve", "reject", "add_evidence"]
    reviewer: str = Field(default="architect", max_length=80)
    comment: str = Field(default="", max_length=2000)
    evidence: dict[str, Any] | None = None


def create_app(reasoner=None, data_dir: Path | None = None) -> FastAPI:
    data_dir = Path(data_dir or DATA_DIR)
    (data_dir / "reports").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(data_dir / "checkpoints.db", check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    provider = os.getenv("EDE_MODEL_PROVIDER", "offline").lower()
    graph = build_graph(checkpointer, reasoner=reasoner, provider=provider)
    policies = load_policies()

    app = FastAPI(title="AI Evidence Decision Engine", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    def thread(eid: str) -> dict:
        return {"configurable": {"thread_id": eid}}

    def view(eid: str) -> dict[str, Any]:
        snap = graph.get_state(thread(eid))
        if not snap.values:
            raise HTTPException(404, f"Evaluation {eid} not found")
        v = snap.values
        pending = [i.value for t in snap.tasks for i in t.interrupts]
        status = "awaiting_review" if pending else ("complete" if v.get("report") else "running")
        if v.get("report"):
            (data_dir / "reports" / f"{eid}.json").write_text(json.dumps(v["report"], indent=2, default=str))
        return {
            "evaluation_id": eid,
            "status": status,
            "model_provider": v.get("model_provider"),
            "request": v.get("request"),
            "iteration": v.get("iteration"),
            "config": v.get("config"),
            "findings": v.get("findings"),
            "assessment": v.get("assessment"),
            "gate": v.get("gate"),
            "approval": v.get("approval"),
            "review_request": pending[0] if pending else None,
            "trace": v.get("trace", []),
            "report": v.get("report"),
        }

    @app.get("/api/health")
    def health():
        return {"status": "ok", "model_provider": provider, "policy_set": policies["version"]}

    @app.get("/api/policies")
    def get_policies():
        return policies

    @app.get("/api/samples")
    def list_samples():
        out = []
        for f in sorted(SAMPLES.glob("*.json")):
            meta = json.loads(f.read_text()).get("_sample", {})
            out.append({"id": f.stem, **meta})
        return out

    @app.get("/api/samples/{sample_id}")
    def get_sample(sample_id: str):
        f = SAMPLES / f"{sample_id}.json"
        if not f.is_file() or f.parent != SAMPLES:
            raise HTTPException(404, "Sample not found")
        return json.loads(f.read_text())

    @app.post("/api/evaluations")
    def create_evaluation(req: EvaluateRequest):
        if not isinstance(req.config.get("application"), dict):
            raise HTTPException(422, "Configuration must include an 'application' object")
        eid = uuid.uuid4().hex[:12]
        graph.invoke(
            {"evaluation_id": eid, "config": req.config, "model_provider": provider, "provenance": {}, "trace": []},
            thread(eid),
        )
        return view(eid)

    @app.get("/api/evaluations/{eid}")
    def get_evaluation(eid: str):
        return view(eid)

    @app.post("/api/evaluations/{eid}/review")
    def review(eid: str, req: ReviewRequest):
        current = view(eid)
        if current["status"] != "awaiting_review":
            raise HTTPException(409, f"Evaluation is {current['status']}, not awaiting review")
        if req.action == "add_evidence" and not req.evidence:
            raise HTTPException(422, "add_evidence requires an 'evidence' object of {dotted.path: value}")
        try:
            graph.invoke(Command(resume=req.model_dump()), thread(eid))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return view(eid)

    @app.get("/api/evaluations/{eid}/report")
    def download_report(eid: str):
        v = view(eid)
        if not v["report"]:
            raise HTTPException(409, "Report is produced after architect review")
        return JSONResponse(
            v["report"],
            headers={"Content-Disposition": f'attachment; filename="evidence-report-{eid}.json"'},
        )

    if FRONTEND_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
