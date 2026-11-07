import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda

from app.api import create_app

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def load_sample(name: str) -> dict:
    return json.loads((SAMPLES / f"{name}.json").read_text())


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(data_dir=tmp_path))


@pytest.fixture
def client_with(tmp_path):
    """Build a client around a custom (e.g. faulty) reasoner."""

    def make(fn):
        return TestClient(create_app(reasoner=RunnableLambda(fn), data_dir=tmp_path))

    return make
