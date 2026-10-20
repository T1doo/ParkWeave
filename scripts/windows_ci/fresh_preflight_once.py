"""Call the original five native wrappers on an unconfigured hosted Server.

AT-01 fresh error/preflight subset only. Never creates application config,
sessions, private ACLs, a database, API/worker, or a replacement installation.
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
BRANCH = "refs/heads/dev/windows-native-preflight-20261020"


def require_context(environment):
    expected = {"NATIVE_REPOSITORY": "T1doo/ParkWeave", "NATIVE_REF": BRANCH,
                "NATIVE_EVENT": "push", "NATIVE_ATTEMPT": "1", "NATIVE_NUMBER": "2",
                "NATIVE_PUBLIC": "true", "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Windows"}
    if any(environment.get(k) != v for k, v in expected.items()):
        raise RuntimeError("only the authorized public second hosted Windows push is allowed")
    if any(k.startswith("PARKWEAVE_") for k in environment):
        raise RuntimeError("inherited business configuration refused")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", environment.get("NATIVE_SHA", "")) or commit != environment["NATIVE_SHA"]:
        raise RuntimeError("exact checked-out source required")
    return commit


def original_sources():
    paths = sorted(p for p in (ROOT / "scripts/windows").iterdir() if p.suffix in {".py", ".ps1"})
    paths += [ROOT / "src/parkweave/synthetic_session_file.py", ROOT / "src/parkweave/process_env.py"]
    return {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in paths}


def fresh_application_state():
    for name in (".runtime", ".venv-windows"):
        if os.path.lexists(ROOT / name):
            raise RuntimeError("fresh unconfigured checkout required; preserve existing state")


def main():
    report = {"scope": "WINDOWS_SERVER_AT01_FRESH_NATIVE_PREFLIGHT_ONLY", "status": "NOT_RUN", "cases": [],
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
            try:
                result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, timeout=timeout)
            except subprocess.TimeoutExpired as error:
                stdout, stderr = error.output or b"", error.stderr or b""
                (out / (name + ".stdout")).write_bytes(stdout)
                (out / (name + ".stderr")).write_bytes(stderr)
                report["failed_command"] = dict(phase=name, timed_out=True,
                    stdout_sha256=sha256(stdout).hexdigest(), stderr_sha256=sha256(stderr).hexdigest())
                raise
            (out / (name + ".stdout")).write_bytes(result.stdout)
            (out / (name + ".stderr")).write_bytes(result.stderr)
            return result

        os_info = capture(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                           "Get-CimInstance Win32_OperatingSystem | Select-Object Caption,BuildNumber,ProductType | ConvertTo-Json -Compress"],
                          "OS_METADATA", 20)
        assert os_info.returncode == 0
        info = json.loads(os_info.stdout.decode("utf-8-sig"))
        assert "Windows Server 2025" in info["Caption"] and info["ProductType"] != 1
        report["platform"] = info
        report["python"] = sys.version.split()[0]
        report["image"] = {k: os.environ.get(k) for k in ("ImageOS", "ImageVersion")}
        frozen = original_sources()
        fresh_application_state()

        def invoke(action, expected_exit):
            fresh_application_state()
            t = time.monotonic()
            run = capture(["powershell.exe", "-NoProfile", "-NonInteractive", "-File",
                           str(ROOT / "scripts/windows" / (action + ".ps1")), "-Python", sys.executable], action, 25)
            row = {"action": action, "exit_code": run.returncode, "expected_exit": expected_exit,
                   "seconds": round(time.monotonic() - t, 3), "stdout_sha256": sha256(run.stdout).hexdigest(),
                   "stderr_sha256": sha256(run.stderr).hexdigest(), "status": "FAIL"}
            report["cases"].append(row)
            assert run.returncode == expected_exit, "original wrapper exit differs from its expected fresh-state outcome"
            fresh_application_state()
            assert original_sources() == frozen
            return run.stdout.decode("utf-8-sig"), run.stderr.decode("utf-8-sig"), row

        stdout, _, row = invoke("Doctor", 0)
        doctor = json.loads(stdout)
        assert doctor["platform"] == "win32" and doctor["model"] == "DISABLED"
        assert doctor["new_setup"]["status"] == "BLOCKED" and doctor["new_setup"]["reason"] == "OWNER_MUTATION_PAUSED"
        assert doctor["new_setup"]["native_acceptance"] == "NOT_ACCEPTED"
        row.update(status="PASS_EXPECTED_PREFLIGHT", observed=doctor)
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
        report.update(status="PASS_FRESH_NATIVE_PREFLIGHT_ONLY", application_state_remained_absent=True,
                      original_source_sha256=frozen, original_sources_unchanged=True,
                      child_environment_keys=sorted(environment), active_phase="COMPLETE")
    except BaseException as error:
        report.update(status="FAIL", error_type=type(error).__name__)
        # No raw exception/command/environment payload is published.
    report["seconds"] = round(time.monotonic() - started, 3)
    value = json.dumps(report, ensure_ascii=True)
    if out is not None:
        (out / "preflight-result.json").write_text(value + "\n", encoding="ascii")
    print(value, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as stream:
            stream.write("```json\n" + value + "\n```\n")
    return 0 if report["status"] == "PASS_FRESH_NATIVE_PREFLIGHT_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
