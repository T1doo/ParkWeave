"""Call only Setup/Start/Status/Stop on an isolated unconfigured hosted Server.

Expected original refusal/NOOP subset; no Doctor or successful installation.
"""
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
BRANCH = "refs/heads/dev/windows-four-wrapper-fresh-20261020"
if __package__:
    from . import fresh_preflight_once as preflight
else:
    import fresh_preflight_once as preflight


def require_context(environment):
    expected = {"NATIVE_REPOSITORY": "T1doo/ParkWeave", "NATIVE_REF": BRANCH,
                "NATIVE_EVENT": "push", "NATIVE_ATTEMPT": "1", "NATIVE_NUMBER": "1",
                "NATIVE_PUBLIC": "true", "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Windows"}
    if any(environment.get(k) != v for k, v in expected.items()):
        raise RuntimeError("only the authorized public remaining-wrapper first hosted Windows push is allowed")
    if any(k.startswith("PARKWEAVE_") for k in environment):
        raise RuntimeError("inherited business configuration refused")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", environment.get("NATIVE_SHA", "")) or commit != environment["NATIVE_SHA"]:
        raise RuntimeError("exact checked-out source required")
    return commit


def main():
    report = {"scope": "WINDOWS_SERVER_REMAINING_FRESH_REFUSAL_NOOP_SUBSET_ONLY", "status": "NOT_RUN", "cases": [], "attempted_actions": [], "doctor": "NOT_RUN_THIS_WINDOW",
              "whole_AT01": "NOT_RUN", "AT04_AT05_AT34": "NOT_RUN", "Win11": "NOT_RUN",
              "successful_app_start_stop_restart": "NOT_RUN", "business_isolation": "NOT_RUN",
              "real_model_calls": 0, "database_calls": 0, "owner_ACL_security_mutations": 0}
    out = None
    started = time.monotonic()
    try:
        report["source_sha"] = require_context(os.environ)
        if sys.platform != "win32" or sys.version_info[:2] != (3, 12) or struct.calcsize("P") != 8:
            raise RuntimeError("native Windows Python3.12 x64 required")
        runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve()
        out = Path(os.environ["NATIVE_EVIDENCE_ROOT"])
        if (not out.is_absolute() or out.parent.resolve() != runner_temp or not out.name.startswith("parkweave-preflight-")
                or not out.is_dir() or out.is_symlink() or out.is_junction()):
            out = None
            raise RuntimeError("exact new runner evidence directory required")
        if Path(sys.prefix).resolve() != (out / "venv").resolve():
            raise RuntimeError("this run's isolated dependency environment required")
        if version("psutil") != "7.2.2":
            raise RuntimeError("existing approved psutil pin required")
        report["psutil"] = version("psutil")
        sys.path.insert(0, str(ROOT / "src"))
        sys.path.insert(0, str(ROOT / "scripts/windows"))
        from parkweave.process_env import minimal_environment
        from lifecycle_diagnostics import parse

        environment = minimal_environment(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")

        def capture(command, name, timeout):
            report["active_phase"] = name
            capture_started = time.monotonic()
            try:
                result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, timeout=timeout)
            except subprocess.TimeoutExpired as error:
                stdout, stderr = error.output or b"", error.stderr or b""
                (out / (name + ".stdout")).write_bytes(stdout)
                (out / (name + ".stderr")).write_bytes(stderr)
                report["failed_command"] = dict(phase=name, timed_out=True,
                    limit_seconds=timeout, seconds=round(time.monotonic() - capture_started, 3),
                    stdout_sha256=sha256(stdout).hexdigest(), stderr_sha256=sha256(stderr).hexdigest())
                raise
            (out / (name + ".stdout")).write_bytes(result.stdout)
            (out / (name + ".stderr")).write_bytes(result.stderr)
            return result

        metadata_started = time.monotonic()
        report["os_metadata_collection"] = dict(method="sys.getwindowsversion", limit_seconds=preflight.OS_METADATA_TIMEOUT,
            isolated=True, site_disabled=True, code_sha256=sha256(preflight.OS_METADATA_CODE.encode()).hexdigest())
        report["platform"] = preflight.collect_os_metadata(capture)
        report["os_metadata_collection"]["seconds"] = round(time.monotonic() - metadata_started, 3)
        report["python"] = sys.version.split()[0]
        report["image"] = {k: os.environ.get(k) for k in ("ImageOS", "ImageVersion")}
        frozen = preflight.original_sources()
        preflight.fresh_application_state()

        def invoke(action, expected_exit):
            preflight.fresh_application_state()
            t = time.monotonic()
            report["attempted_actions"].append(action)
            run = capture(["powershell.exe", "-NoProfile", "-NonInteractive", "-File",
                           str(ROOT / "scripts/windows" / (action + ".ps1")), "-Python", sys.executable], action, 25)
            row = {"action": action, "exit_code": run.returncode, "expected_exit": expected_exit,
                   "seconds": round(time.monotonic() - t, 3), "stdout_sha256": sha256(run.stdout).hexdigest(),
                   "stderr_sha256": sha256(run.stderr).hexdigest(), "status": "FAIL"}
            if action in {"Setup", "Start"}:
                row["diagnostic"] = parse(run.stdout.decode("utf-8-sig", errors="replace"), action.lower())
            report["cases"].append(row)
            assert run.returncode == expected_exit, "original wrapper exit differs from its expected fresh-state outcome"
            preflight.fresh_application_state()
            assert preflight.original_sources() == frozen
            return run.stdout.decode("utf-8-sig"), run.stderr.decode("utf-8-sig"), row

        for action, reason in (("Setup", "OWNER_MUTATION_PAUSED"), ("Start", "CONFIG_MISSING")):
            stdout, stderr, row = invoke(action, 1)
            diagnostic = parse(stdout, action.lower())
            assert diagnostic["boundary_reason"] == reason
            row.update(status="PASS_EXPECTED_REFUSAL", diagnostic=diagnostic)
        _, stderr, row = invoke("Status", 1)
        assert "setup not completed; run Setup.ps1 first" in stderr
        row.update(status="PASS_EXPECTED_REFUSAL", observation="CONFIG_MISSING original error text")
        stdout, _, row = invoke("Stop", 0)
        assert "No managed process record. No process/data changed." in stdout
        row.update(status="PASS_EXPECTED_NOOP", observation="NO_MANAGED_RECORD; not a successful service stop")
        report.update(status="PASS_REMAINING_FRESH_REFUSAL_NOOP_SUBSET_ONLY", application_state_remained_absent=True,
                      original_source_sha256=frozen, original_sources_unchanged=True,
                      child_environment_keys=sorted(environment), active_phase="COMPLETE")
    except BaseException as error:
        report.update(status="FAIL", error_type=type(error).__name__)
        # No raw exception/command/environment payload is published.
    report["seconds"] = round(time.monotonic() - started, 3)
    value = json.dumps(report, ensure_ascii=True)
    if out is not None:
        (out / "four-wrapper-fresh-result.json").write_text(value + "\n", encoding="ascii")
    print(value, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as stream:
            stream.write("```json\n" + value + "\n```\n")
    return 0 if report["status"] == "PASS_REMAINING_FRESH_REFUSAL_NOOP_SUBSET_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
