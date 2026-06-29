from pathlib import Path
import importlib
import sys
import types

import config


def test_model_config_primary_is_gemma4():
    assert config.LLM_MODEL_PRIMARY == "gemma4:26b"
    assert config.LLM_MODEL_FALLBACK == "qwen2.5:3b"


def test_no_qwen_hardcoded_as_primary():
    root = Path(__file__).resolve().parents[1]
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        assert 'LLM_MODEL = "qwen' not in text
        assert 'LLM_MODEL_PRIMARY = "qwen' not in text
        assert "qwen3.5" not in text


def test_health_endpoint_schema():
    try:
        from fastapi.testclient import TestClient
        from app.main import app

        response = TestClient(app).get("/health")
        assert response.status_code == 200
        payload = response.json()
    except ModuleNotFoundError:
        fake_fastapi = types.ModuleType("fastapi")

        class FakeFastAPI:
            def __init__(self, *args, **kwargs):
                pass

            def get(self, *args, **kwargs):
                return lambda fn: fn

            def post(self, *args, **kwargs):
                return lambda fn: fn

        fake_fastapi.FastAPI = FakeFastAPI
        fake_pydantic = types.ModuleType("pydantic")

        class FakeBaseModel:
            pass

        def fake_field(default_factory=None, **kwargs):
            return default_factory() if default_factory else None

        fake_pydantic.BaseModel = FakeBaseModel
        fake_pydantic.Field = fake_field
        sys.modules.pop("app.main", None)
        sys.modules["fastapi"] = fake_fastapi
        sys.modules["pydantic"] = fake_pydantic
        payload = importlib.import_module("app.main").health()

    assert payload["model_primary"] == "gemma4:26b"
    assert payload["model_fallback"] == "qwen2.5:3b"
    assert "primary_available" in payload
    assert "fallback_available" in payload
    assert payload["vector_db"]["collection"] == config.COLLECTION
