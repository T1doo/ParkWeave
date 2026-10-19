"""Contract for the isolated page harness; this test never launches a browser."""
import importlib.util
from pathlib import Path
import subprocess

import pytest
from fastapi.testclient import TestClient


def test_readonly_harness_original_page_authentication_and_write_guard():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("browser_readiness_smoke", root / "scripts/browser_readiness_smoke.py")
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    with pytest.raises(RuntimeError, match="authorized public dedicated hosted Linux push"):
        smoke.require_hosted_once({})
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    hosted = {"SMOKE_REPOSITORY": "T1doo/ParkWeave", "SMOKE_REF": smoke.BRANCH,
              "SMOKE_EVENT": "push", "SMOKE_ATTEMPT": "1", "SMOKE_NUMBER": "6",
              "SMOKE_PUBLIC": "true", "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Linux",
              "SMOKE_SHA": sha}
    assert smoke.require_hosted_once(hosted) == sha
    for wrong_scope in [{"SMOKE_NUMBER": "5"}, {"SMOKE_NUMBER": "7"}, {"SMOKE_ATTEMPT": "2"}]:
        with pytest.raises(RuntimeError, match="authorized public dedicated hosted Linux push"):
            smoke.require_hosted_once(hosted | wrong_scope)
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
