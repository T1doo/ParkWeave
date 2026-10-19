"""Contract for the isolated page harness; this test never launches a browser."""
import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def test_readonly_harness_original_page_authentication_and_write_guard():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("browser_readiness_smoke", root / "scripts/browser_readiness_smoke.py")
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    with pytest.raises(RuntimeError, match="first public dedicated hosted Linux push"):
        smoke.require_hosted_once({})
    with smoke.readonly_application() as (app, evidence), TestClient(app) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert home.content == (root / "src/parkweave/web.html").read_bytes()
        assert home.headers["content-type"].startswith("text/html")
        for path in ["/api/preparations", "/api/preparation-catalog"]:
            response = client.get(path)
            assert response.status_code == 401
            assert response.json() == {"detail": "session required"}
        # Negative harness probe is intercepted before any product POST handler.
        response = client.post("/api/runs", json={})
        assert response.status_code == 405
        assert response.json() == {"detail": "read-only smoke guard"}
        assert evidence["blocked_write_probes"] == 1
        assert evidence["db_connect_attempts"] == 0
