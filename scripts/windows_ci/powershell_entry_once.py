"""One native PowerShell entry probe in the original Doctor child environment.

No Doctor invocation or internal source markers before this prerequisite is
proven. No shell substitution, environment expansion, timeout increase or retry.
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

if __package__:
    from . import fresh_preflight_once as preflight
else:
    import fresh_preflight_once as preflight

ROOT = Path(__file__).resolve().parents[2]
BRANCH = "refs/heads/dev/windows-doctor-entry-20261020"
PROBE_TIMEOUT = 25
PROBE_CODE = "[Console]::Error.WriteLine('PS_ENTERED'); [Console]::Error.Flush(); exit 0"


def probe_command():
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", PROBE_CODE]


def require_context(environment):
    expected = dict(NATIVE_REPOSITORY="T1doo/ParkWeave", NATIVE_REF=BRANCH, NATIVE_EVENT="push",
                    NATIVE_ATTEMPT="1", NATIVE_NUMBER="1", NATIVE_PUBLIC="true",
                    RUNNER_ENVIRONMENT="github-hosted", RUNNER_OS="Windows")
    if any(environment.get(k) != v for k, v in expected.items()) or any(k.startswith("PARKWEAVE_") for k in environment):
        raise RuntimeError("only the authorized public first hosted Windows entry probe is allowed")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", environment.get("NATIVE_SHA", "")) or head != environment["NATIVE_SHA"]:
        raise RuntimeError("exact checked-out source required")
    return head


def observe_entry(capture):
    started = time.monotonic()
    timed_out, exit_code = False, None
    try:
        result = capture(probe_command(), "POWERSHELL_ENTRY", PROBE_TIMEOUT)
        stdout, stderr, exit_code = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout, stderr = error.output or b"", error.stderr or b""
    bounded = isinstance(stdout, bytes) and isinstance(stderr, bytes) and len(stdout) <= 4096 and len(stderr) <= 4096
    entered = bounded and b"PS_ENTERED" in stderr.splitlines()
    clean = bounded and stdout == b"" and stderr.splitlines() == [b"PS_ENTERED"]
    passed = not timed_out and exit_code == 0 and clean
    return dict(status="PASS_PS_ENTERED" if passed else "FAIL_ENTRY_PROBE", timed_out=timed_out,
                exit_code=exit_code, ps_entered=entered, bounded_output=bounded,
                stdout_sha256=sha256(stdout).hexdigest(), stderr_sha256=sha256(stderr).hexdigest(),
                limit_seconds=PROBE_TIMEOUT, seconds=round(time.monotonic() - started, 3),
                interpretation="ENTRY_AND_EXIT_PROVEN" if passed else
                    "ENTRY_SEEN_BUT_NOT_CLEANLY_COMPLETED" if entered else "NO_ENTRY_MARKER_OBSERVED")


def main():
    report = dict(scope="WINDOWS_SERVER_POWERSHELL_ENTRY_DIAGNOSTIC_ONLY", status="NOT_RUN", doctor_invoked=False,
                  internal_stage_markers_added=False, original_doctor_limit_seconds=25,
                  real_model_calls=0, database_calls=0, owner_ACL_security_mutations=0,
                  whole_AT01="NOT_RUN", Win11="NOT_RUN", native_wrapper_acceptance="NOT_RUN")
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
        if Path(sys.prefix).resolve() != (out / "venv").resolve() or version("psutil") != "7.2.2":
            raise RuntimeError("original isolated interpreter and dependency pin required")
        sys.path.insert(0, str(ROOT / "src"))
        from parkweave.process_env import minimal_environment
        environment = minimal_environment(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
        report["child_environment_keys"] = sorted(environment)
        report["psutil"] = version("psutil")
        report["python"] = sys.version.split()[0]
        report["image"] = {k: os.environ.get(k) for k in ("ImageOS", "ImageVersion")}

        def capture(command, name, timeout):
            report["active_phase"] = name
            try:
                result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, timeout=timeout)
            except subprocess.TimeoutExpired as error:
                (out / (name + ".stdout")).write_bytes(error.output or b"")
                (out / (name + ".stderr")).write_bytes(error.stderr or b"")
                raise
            (out / (name + ".stdout")).write_bytes(result.stdout)
            (out / (name + ".stderr")).write_bytes(result.stderr)
            return result

        t = time.monotonic()
        report["platform"] = preflight.collect_os_metadata(capture)
        report["os_metadata_seconds"] = round(time.monotonic() - t, 3)
        frozen = preflight.original_sources()
        preflight.fresh_application_state()
        report["probe_command"] = probe_command()
        report["entry_probe"] = observe_entry(capture)
        preflight.fresh_application_state()
        if preflight.original_sources() != frozen:
            raise RuntimeError("original launchers or environment helper changed")
        report.update(original_source_sha256=frozen, original_sources_unchanged=True, application_state_remained_absent=True)
        if report["entry_probe"]["status"] == "PASS_PS_ENTERED":
            report.update(status="PASS_POWERSHELL_ENTRY_ONLY", next_step="INTERNAL_FLUSH_STAGE_MARKERS_ELIGIBLE")
        else:
            report.update(status="FAIL_POWERSHELL_ENTRY_PROBE", next_step="NO_INTERNAL_MARKERS_BEFORE_ENTRY_IS_PROVEN")
    except BaseException as error:
        report.update(status="FAIL", error_type=type(error).__name__)
    report["seconds"] = round(time.monotonic() - started, 3)
    serialized = json.dumps(report, ensure_ascii=True)
    if out is not None:
        (out / "powershell-entry-result.json").write_text(serialized + "\n", encoding="ascii")
    print(serialized, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as stream:
            stream.write("```json\n" + serialized + "\n```\n")
    return 0 if report["status"] == "PASS_POWERSHELL_ENTRY_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
