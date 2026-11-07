import { useEffect, useMemo, useRef, useState } from "react";
import { api, Decision, Evaluation, Finding, Sample } from "./api";

const PIPELINE = [
  { id: "understand_request", label: "Understand Request" },
  { id: "examine_evidence", label: "Examine Evidence" },
  { id: "identify_gaps", label: "Identify Gaps" },
  { id: "evaluate_readiness", label: "Evaluate Readiness" },
  { id: "policy_check", label: "Policy Check" },
  { id: "route", label: "Ready / Not Ready" },
  { id: "human_approval", label: "Human Approval" },
  { id: "final_report", label: "Final Report" },
];

const LABEL: Record<Decision, string> = { READY: "Ready", NOT_READY: "Not ready", NEEDS_REVIEW: "Needs review" };

export default function App() {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [activeSample, setActiveSample] = useState<string>("");
  const [configText, setConfigText] = useState("");
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [provider, setProvider] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.health().then((h) => setProvider(h.model_provider)).catch(() => setError("Backend not reachable on :8000"));
    api.samples().then((s) => { setSamples(s); if (s[0]) loadSample(s[0].id); }).catch(() => {});
  }, []);

  async function loadSample(id: string) {
    setActiveSample(id);
    setEvaluation(null);
    setError("");
    const cfg = await api.sample(id);
    setConfigText(JSON.stringify(cfg, null, 2));
  }

  function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    f.text().then((t) => { setConfigText(t); setActiveSample(""); setEvaluation(null); });
    e.target.value = "";
  }

  async function run<T>(fn: () => Promise<T>) {
    setBusy(true);
    setError("");
    try { return await fn(); } catch (e: any) { setError(e.message || String(e)); } finally { setBusy(false); }
  }

  async function evaluate() {
    let cfg: unknown;
    try { cfg = JSON.parse(configText); } catch { setError("Configuration is not valid JSON"); return; }
    const r = await run(() => api.evaluate(cfg));
    if (r) setEvaluation(r);
  }

  return (
    <div className="shell">
      <header className="top">
        <div>
          <div className="eyebrow">AI Evidence Decision Engine</div>
          <h1>Enterprise AI Readiness</h1>
        </div>
        <div className="meta">
          <span className="pill">LangGraph</span>
          <span className="pill">model: {provider || "—"}</span>
          <span className="pill subtle">synthetic data only</span>
        </div>
      </header>

      <main className="grid">
        <section className="card input">
          <h2>Evaluate this AI application for enterprise deployment</h2>
          <div className="samples">
            {samples.map((s) => (
              <button key={s.id} className={`chip ${activeSample === s.id ? "on" : ""}`} onClick={() => loadSample(s.id)} title={s.why}>
                {s.title}
                <span className="chip-exp">expect {s.expected}</span>
              </button>
            ))}
          </div>
          <textarea spellCheck={false} value={configText} onChange={(e) => { setConfigText(e.target.value); setActiveSample(""); }} />
          <div className="row">
            <input ref={fileRef} type="file" accept="application/json,.json" hidden onChange={onUpload} />
            <button className="ghost" onClick={() => fileRef.current?.click()}>Upload JSON</button>
            <button className="primary" disabled={busy || !configText} onClick={evaluate}>{busy ? "Evaluating…" : "Evaluate"}</button>
          </div>
          {error && <div className="error">{error}</div>}
        </section>

        <section className="results">
          <Pipeline evaluation={evaluation} />
          {evaluation ? (
            <>
              <Verdict ev={evaluation} />
              <Findings ev={evaluation} />
              {evaluation.status === "awaiting_review" && (
                <Review ev={evaluation} busy={busy} onSubmit={async (body) => { const r = await run(() => api.review(evaluation.evaluation_id, body)); if (r) setEvaluation(r); }} />
              )}
              {evaluation.report && <ReportCard ev={evaluation} />}
              <Trace ev={evaluation} />
            </>
          ) : (
            <div className="card empty">Pick a sample or upload a configuration, then click <b>Evaluate</b>. The graph will investigate the evidence and pause for an architect.</div>
          )}
        </section>
      </main>
      <footer>Let the model reason. Let the deterministic rules govern. · Intent-Driven Engineering</footer>
    </div>
  );
}

function Pipeline({ evaluation }: { evaluation: Evaluation | null }) {
  const visited = new Set((evaluation?.trace || []).map((t) => (t.node.startsWith("route_") ? "route" : t.node)));
  const waiting = evaluation?.status === "awaiting_review";
  const branch = [...(evaluation?.trace || [])].reverse().find((t) => t.node.startsWith("route_"))?.node;
  return (
    <div className="card pipeline">
      {PIPELINE.map((n, i) => {
        const state = waiting && n.id === "human_approval" ? "wait" : visited.has(n.id) ? "done" : "idle";
        const label = n.id === "route" && branch ? (branch === "route_ready" ? "Ready" : "Not Ready") : n.label;
        return (
          <div key={n.id} className="step-wrap">
            <div className={`step ${state} ${n.id === "policy_check" ? "gate" : ""} ${n.id === "route" && branch === "route_not_ready" ? "blocked" : ""}`}>
              <span className="dot" />
              {label}
            </div>
            {i < PIPELINE.length - 1 && <span className="arrow">›</span>}
          </div>
        );
      })}
      {evaluation && evaluation.iteration > 1 && <div className="iter">iteration {evaluation.iteration}</div>}
    </div>
  );
}

function Badge({ d }: { d?: Decision | string }) {
  if (!d) return <span className="badge">—</span>;
  return <span className={`badge ${d}`}>{LABEL[d as Decision] ?? d}</span>;
}

function Verdict({ ev }: { ev: Evaluation }) {
  const final = ev.report?.decision;
  return (
    <div className="card verdict">
      <div className="verdict-main">
        <div className="muted">{final ? "Final decision" : "Policy gate decision"} · {ev.request.application}</div>
        <div className="big"><Badge d={final ?? ev.gate.decision} /></div>
        <ul className="reasons">{ev.gate.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
      </div>
      <div className="verdict-side">
        <div className="kv"><span>Model recommended</span><Badge d={ev.assessment.decision} /></div>
        <div className="kv"><span>Policy gate</span><Badge d={ev.gate.decision} /></div>
        <div className="kv"><span>Gate overrode model</span><b>{ev.gate.overrode_model ? "yes" : "no"}</b></div>
        <div className="kv"><span>Human approval</span><b>{ev.approval?.status ?? "pending"}</b></div>
        {ev.assessment.error && <div className="error small">Model failure: {ev.assessment.error}</div>}
        {ev.gate.invented_citations.length > 0 && <div className="error small">Rejected invented evidence: {ev.gate.invented_citations.join(", ")}</div>}
      </div>
      {ev.assessment.rationale && <p className="rationale">“{ev.assessment.rationale}”</p>}
    </div>
  );
}

function FindingList({ title, items, tone }: { title: string; items: Finding[]; tone: string }) {
  if (!items.length) return null;
  return (
    <div className={`findings ${tone}`}>
      <h3>{title} <span className="count">{items.length}</span></h3>
      {items.map((f) => (
        <div key={f.policy_id} className="finding">
          <div><b>{f.policy_id}</b> {f.title}</div>
          <div className="ref"><code>{f.evidence_ref}</code>{f.observed !== undefined && <> = <code>{JSON.stringify(f.observed)}</code></>}</div>
          {f.remediation && <div className="fix">→ {f.remediation}</div>}
        </div>
      ))}
    </div>
  );
}

function Findings({ ev }: { ev: Evaluation }) {
  const c = ev.assessment.contradictions || [];
  return (
    <div className="card">
      {c.length > 0 && (
        <div className="findings contradiction">
          <h3>Claims contradicted by evidence <span className="count">{c.length}</span></h3>
          {c.map((x, i) => (
            <div key={i} className="finding">
              <div className="claim">“{x.claim}”</div>
              <div className="fix">✕ {x.explanation}</div>
            </div>
          ))}
        </div>
      )}
      <FindingList title="Policy violations" items={ev.findings.violations} tone="bad" />
      <FindingList title="Missing evidence" items={ev.findings.missing} tone="warn" />
      <FindingList title="Policies satisfied" items={ev.findings.passed} tone="good" />
    </div>
  );
}

function Review({ ev, busy, onSubmit }: { ev: Evaluation; busy: boolean; onSubmit: (b: any) => void }) {
  const [reviewer, setReviewer] = useState("architect");
  const [comment, setComment] = useState("");
  const template = useMemo(() => {
    const t: Record<string, unknown> = {};
    ev.findings.missing.forEach((m) => (t[m.evidence_ref] = null));
    ev.findings.violations.forEach((v) => (t[v.evidence_ref] = v.observed));
    return JSON.stringify(t, null, 2);
  }, [ev]);
  const [evidence, setEvidence] = useState(template);
  const [err, setErr] = useState("");
  useEffect(() => setEvidence(template), [template]);

  function addEvidence() {
    try { onSubmit({ action: "add_evidence", reviewer, comment, evidence: JSON.parse(evidence) }); setErr(""); }
    catch { setErr("Evidence must be a JSON object of { \"dotted.path\": value }"); }
  }

  const blocked = ev.gate.decision !== "READY";
  return (
    <div className="card review">
      <h2>Architect review <span className="paused">graph paused</span></h2>
      <p className="muted">{ev.review_request?.note}</p>
      <div className="row">
        <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="Reviewer" />
        <input className="grow" value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Comment (optional)" />
      </div>
      <div className="row">
        <button className="primary" disabled={busy} onClick={() => onSubmit({ action: "approve", reviewer, comment })}>
          {blocked ? "Acknowledge (stays blocked)" : "Approve deployment"}
        </button>
        <button className="danger" disabled={busy} onClick={() => onSubmit({ action: "reject", reviewer, comment })}>Reject</button>
      </div>
      {blocked && (
        <details open>
          <summary>Supply additional evidence and re-evaluate</summary>
          <textarea className="small-ta" spellCheck={false} value={evidence} onChange={(e) => setEvidence(e.target.value)} />
          <button className="ghost" disabled={busy} onClick={addEvidence}>Add evidence &amp; resume graph</button>
          {err && <div className="error small">{err}</div>}
        </details>
      )}
    </div>
  );
}

function ReportCard({ ev }: { ev: Evaluation }) {
  const r = ev.report!;
  return (
    <div className="card report">
      <div>
        <h2>Evidence report</h2>
        <div className="muted">{r.evidence_references.length} evidence references · {r.recommended_remediation.length} remediation items · approval {r.human_approval.status}</div>
      </div>
      <a className="primary btn" href={api.reportUrl(ev.evaluation_id)} download>Download JSON report</a>
    </div>
  );
}

function Trace({ ev }: { ev: Evaluation }) {
  return (
    <details className="card trace">
      <summary>Graph execution trace · {ev.trace.length} steps · thread {ev.evaluation_id}</summary>
      <ol>{ev.trace.map((t, i) => <li key={i}><code>{t.node}</code> <span className="muted">{t.summary}</span></li>)}</ol>
    </details>
  );
}
