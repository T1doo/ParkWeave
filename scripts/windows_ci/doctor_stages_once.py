"""One traced fresh Doctor call; original shell, environment and 25-second gate."""
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
BRANCH = "refs/heads/dev/windows-doctor-stages-20261020"
AUTHORIZED_BRANCHES = frozenset({BRANCH, "refs/heads/dev/windows-doctor-source-boundary-20261020",
                                 "refs/heads/dev/windows-doctor-joinpath-20261020"})
PROBE_TIMEOUT = 25


def probe_command(trace=True):
    command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-File",
               str(ROOT / "scripts/windows/Doctor.ps1"), "-Python", sys.executable]
    return command + ["-TraceStages"] if trace else command


def require_context(environment, branch=BRANCH, trace=True):
    if (branch not in AUTHORIZED_BRANCHES or type(trace) is not bool
            or trace != (branch != "refs/heads/dev/windows-doctor-joinpath-20261020")):
        raise RuntimeError("unapproved diagnostic branch refused")
    expected = dict(NATIVE_REPOSITORY="T1doo/ParkWeave", NATIVE_REF=branch, NATIVE_EVENT="push",
                    NATIVE_ATTEMPT="1", NATIVE_NUMBER="1", NATIVE_PUBLIC="true",
                    RUNNER_ENVIRONMENT="github-hosted", RUNNER_OS="Windows")
    if any(environment.get(k) != v for k, v in expected.items()) or any(k.startswith("PARKWEAVE_") for k in environment):
        raise RuntimeError("only the authorized public first hosted Windows Doctor diagnostic is allowed")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", environment.get("NATIVE_SHA", "")) or head != environment["NATIVE_SHA"]:
        raise RuntimeError("exact checked-out source required")
    return head


STAGES = (
    "PS_DOCTOR_ENTERED", "PS_COMMON_PATH_BEGIN", "PS_COMMON_PATH_READY", "PS_COMMON_ENTERED",
    "PS_RESOLVER_PATH_BEGIN", "PS_RESOLVER_PATH_READY", "PS_RESOLVER_FILE_ENTERED",
    "PS_RESOLVER_FILE_READY", "PS_RESOLVER_SOURCE_READY", "PS_COMMON_READY", "PS_INVOKE_ENTERED", "PS_REPO_READY",
    "PS_MANAGED_PATH_READY", "PS_GET_COMMAND_BEGIN", "PS_GET_COMMAND_RETURNED",
    "PS_TEST_PATH_READY", "PS_GET_ITEM_RETURNED", "PS_PYTHON_RESOLVED",
    "PS_LIFECYCLE_BEGIN", "PY_ENTERED", "PY_IMPORTS_READY", "PY_MAIN_ENTERED",
    "PY_WINDOWS_READY", "PY_DOCTOR_ENTERED", "PY_CHECK_PYTHON_BEGIN",
    "PY_CHECK_PYTHON_RETURNED", "PY_DOCTOR_OUTPUT_BEGIN", "PY_DOCTOR_OUTPUT_END",
    "PS_LIFECYCLE_RETURNED",
)
BOUNDARIES = (
    ("DOT_SOURCE_COMMON", "PS_DOCTOR_ENTERED", "PS_COMMON_READY"),
    ("COMMON_PATH_COMMAND", "PS_COMMON_PATH_BEGIN", "PS_COMMON_PATH_READY"),
    ("COMMON_FILE_ENTRY", "PS_COMMON_PATH_READY", "PS_COMMON_ENTERED"),
    ("RESOLVER_PATH_COMMAND", "PS_RESOLVER_PATH_BEGIN", "PS_RESOLVER_PATH_READY"),
    ("RESOLVER_FILE_ENTRY", "PS_RESOLVER_PATH_READY", "PS_RESOLVER_FILE_ENTERED"),
    ("RESOLVER_FILE_DEFINITION", "PS_RESOLVER_FILE_ENTERED", "PS_RESOLVER_FILE_READY"),
    ("RESOLVER_DOT_SOURCE", "PS_RESOLVER_PATH_READY", "PS_RESOLVER_SOURCE_READY"),
    ("GET_COMMAND", "PS_GET_COMMAND_BEGIN", "PS_GET_COMMAND_RETURNED"),
    ("GET_ITEM", "PS_TEST_PATH_READY", "PS_GET_ITEM_RETURNED"),
    ("LIFECYCLE_CALL", "PS_LIFECYCLE_BEGIN", "PS_LIFECYCLE_RETURNED"),
    ("PYTHON_PROCESS_ENTRY", "PS_LIFECYCLE_BEGIN", "PY_ENTERED"),
    ("PYTHON_IMPORTS", "PY_ENTERED", "PY_IMPORTS_READY"),
    ("CHECK_PYTHON_CHILD", "PY_CHECK_PYTHON_BEGIN", "PY_CHECK_PYTHON_RETURNED"),
)


def observe_doctor(capture, trace=True):
    started = time.monotonic()
    timed_out, exit_code = False, None
    try:
        result = capture(probe_command(trace), "DOCTOR_STAGES" if trace else "DOCTOR_DEFAULT", PROBE_TIMEOUT)
        stdout, stderr, exit_code = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout, stderr = error.output or b"", error.stderr or b""
    bounded = len(stdout) <= 65536 and len(stderr) <= 65536
    known = {("PW_STAGE:" + stage).encode(): stage for stage in STAGES}
    lines = stderr.splitlines()
    stages = [known[line] for line in lines if line in known] if bounded else []
    other = [line for line in lines if line not in known]
    unknown = any(line.startswith(b"PW_STAGE:") and line not in known for line in lines)
    ordered = all(STAGES.index(a) < STAGES.index(b) for a, b in zip(stages, stages[1:]))
    sys.path.insert(0, str(ROOT / "scripts/windows"))
    from lifecycle_diagnostics import parse
    diagnostic = parse(stdout.decode("utf-8-sig", errors="replace"), "doctor") if bounded else None
    safe_errors = [name for name in ("PSSecurityException", "UnauthorizedAccess", "CommandNotFoundException",
                                    "ParserError", "NativeCommandError", "ModuleNotFoundError", "ImportError")
                   if re.search(rb"\b" + name.encode() + rb"\b", stderr)] if bounded else []
    valid_doctor = False
    try:
        info = json.loads(stdout.decode("utf-8-sig")) if bounded else None
        valid_doctor = (isinstance(info, dict) and info.get("project") == "ParkWeave"
                        and info.get("platform") == "win32" and info.get("model") == "DISABLED"
                        and info.get("new_setup", {}).get("status") == "BLOCKED"
                        and info["new_setup"].get("reason") == "OWNER_MUTATION_PAUSED"
                        and info["new_setup"].get("native_acceptance") == "NOT_ACCEPTED")
    except (ValueError, UnicodeError, AttributeError, TypeError):
        pass
    passed = (not timed_out and exit_code == 0 and bounded and not other
              and not unknown and ordered and stages == (list(STAGES) if trace else []) and valid_doctor)
    success = "PASS_FRESH_DOCTOR_DIAGNOSTIC_ONLY" if trace else "PASS_FRESH_DOCTOR_DEFAULT_ONLY"
    return dict(status=success if passed else "FAIL_DOCTOR_DIAGNOSTIC",
                timed_out=timed_out, error_type="TimeoutExpired" if timed_out else None, exit_code=exit_code,
                stages=stages, last_stage=stages[-1] if stages else None,
                unreturned_boundaries=[name for name, begin, end in BOUNDARIES if begin in stages and end not in stages],
                stage_order_valid=ordered, unknown_stage_observed=unknown, doctor_output_valid=valid_doctor,
                original_diagnostic=diagnostic, safe_error_categories=safe_errors,
                bounded_output=bounded, stdout_bytes=len(stdout), stderr_bytes=len(stderr),
                stdout_sha256=sha256(stdout).hexdigest(), stderr_sha256=sha256(stderr).hexdigest(),
                nonstage_stderr_bytes=sum(len(line) for line in other),
                nonstage_stderr_sha256=sha256(b"\n".join(other)).hexdigest(),
                raw_streams_preserved_in_runner_temp=True,
                limit_seconds=PROBE_TIMEOUT, seconds=round(time.monotonic() - started, 3))


def main(branch=BRANCH, trace=True):
    report = dict(scope="WINDOWS_SERVER_DOCTOR_STAGES_DIAGNOSTIC_ONLY" if trace else "WINDOWS_SERVER_DOCTOR_DEFAULT_VERIFICATION_ONLY",
                  status="NOT_RUN", doctor_invoked=False,
                  internal_stage_markers_enabled=trace, original_doctor_limit_seconds=25,
                  real_model_calls=0, database_calls=0, owner_ACL_security_mutations=0,
                  whole_AT01="NOT_RUN", Win11="NOT_RUN", native_wrapper_acceptance="NOT_RUN")
    out = None
    started = time.monotonic()
    try:
        report["source_sha"] = require_context(os.environ, branch, trace)
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
        report["doctor_command_attempted"] = True
        report["doctor_probe"] = observe_doctor(capture, trace)
        report["doctor_invoked"] = ("PS_DOCTOR_ENTERED" in report["doctor_probe"]["stages"]
                                    or report["doctor_probe"]["doctor_output_valid"])
        preflight.fresh_application_state()
        if preflight.original_sources() != frozen:
            raise RuntimeError("original launchers or environment helper changed")
        report.update(original_source_sha256=frozen, original_sources_unchanged=True, application_state_remained_absent=True)
        report["status"] = report["doctor_probe"]["status"]
    except BaseException as error:
        report.update(status="FAIL", error_type=type(error).__name__)
    report["seconds"] = round(time.monotonic() - started, 3)
    serialized = json.dumps(report, ensure_ascii=True)
    if out is not None:
        (out / "doctor-stages-result.json").write_text(serialized + "\n", encoding="ascii")
    print(serialized, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as stream:
            stream.write("```json\n" + serialized + "\n```\n")
    success = "PASS_FRESH_DOCTOR_DIAGNOSTIC_ONLY" if trace else "PASS_FRESH_DOCTOR_DEFAULT_ONLY"
    return 0 if report["status"] == success else 1


if __name__ == "__main__":
    raise SystemExit(main())
