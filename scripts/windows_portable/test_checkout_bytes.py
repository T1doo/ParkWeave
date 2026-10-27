"""Exercise real Git checkout filters; no network or system configuration."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ('scripts/windows_portable/build.py', 'scripts/windows_portable/payload.py', 'scripts/windows_portable/runtime-assets.json')


class WindowsFrozenCheckout(unittest.TestCase):
    def test_crlf_checkout_keeps_lf_bytes(self):
        self.check_checkout(b"\n")

    def test_crlf_checkout_keeps_crlf_bytes(self):
        self.check_checkout(b"\r\n")

    def check_checkout(self, newline):
        executable = shutil.which("git")
        if executable is None:
            self.skipTest("Git is required for the candidate assembler")
        with tempfile.TemporaryDirectory(prefix="frozen-checkout-") as directory:
            base = Path(directory)
            repository, output, template = (base / name for name in ("repository", "output", "template"))
            repository.mkdir()
            output.mkdir()
            template.mkdir()
            environment = {key: value for key, value in os.environ.items()
                           if not key.upper().startswith("GIT_")}
            environment.update(GIT_CONFIG_NOSYSTEM="1",
                               GIT_CONFIG_GLOBAL=str(base / "absent-global-config"),
                               GIT_TERMINAL_PROMPT="0")
            def git(*arguments):
                return subprocess.run([executable, "-c", "core.autocrlf=true", "-c", "core.eol=crlf",
                    "-C", str(repository), *arguments], env=environment, check=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            git("init", "--quiet", "--template=" + str(template))
            (repository / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
            frozen = b"first line" + newline + b"second line" + newline
            for name in SAMPLES:
                path = repository / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(frozen)
            git("add", ".")
            git("checkout-index", "--all", "--prefix=" + str(output).replace("\\", "/") + "/")
            for name in SAMPLES:
                self.assertEqual((output / name).read_bytes(), frozen, name)


if __name__ == "__main__":
    unittest.main()
