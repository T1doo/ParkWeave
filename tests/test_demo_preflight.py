"""Stdlib tests: also runnable without repository pytest/database dependencies."""
import importlib.util
import importlib.metadata
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/demo_preflight.py'
spec = importlib.util.spec_from_file_location('demo_preflight', SCRIPT)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class DemoPreflightTests(unittest.TestCase):
    def test_complete_inventory_never_claims_business_or_runtime_success(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in demo.ASSETS:
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.touch()
            report = demo.inspect_demo(root, (3, 12), lambda name: '0.0-test')
        self.assertTrue(report['inventory_complete'])
        for field in ('runtime', 'database', 'authorization'):
            self.assertEqual(report[field], 'NOT_PROBED')
        self.assertIn('BLOCKED', report['cold_case_to_receipt'])
        self.assertEqual(report['formal_at_ex'], 'NOT_RUN')

    def test_missing_dependency_is_explicit_and_scan_does_not_read_files(self):
        def absent(name):
            raise importlib.metadata.PackageNotFoundError(name)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            secret = root / '.runtime/synthetic-sessions.json'
            secret.parent.mkdir()
            secret.write_text('DO-NOT-READ-THIS-SESSION')
            before = secret.read_bytes()
            with patch.object(Path, 'read_text', side_effect=AssertionError('file contents read')), patch.object(Path, 'read_bytes', side_effect=AssertionError('file contents read')):
                report = demo.inspect_demo(root, (3, 12), absent)
            self.assertEqual(secret.read_bytes(), before)
            self.assertEqual(sorted(p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()), ['.runtime/synthetic-sessions.json'])
        self.assertFalse(report['inventory_complete'])
        self.assertEqual(report['missing_dependencies'], list(demo.DEPENDENCIES))
        self.assertNotIn('DO-NOT-READ', str(report))

    def test_wrong_python_not_accepted_as_ready(self):
        self.assertFalse(demo.inspect_demo(Path('/nonexistent'), (3, 13), lambda name: 'test')['python_3_12'])

    def test_cli_works_from_other_directory_without_app_import(self):
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable, str(SCRIPT), '--json'], cwd=folder, capture_output=True, text=True, timeout=10)
        import json
        report = json.loads(result.stdout)
        self.assertIn(result.returncode, (0, 2))
        self.assertEqual(report['missing_assets'], [])
        self.assertEqual(report['model_calls_by_this_tool'], 0)
        self.assertEqual(report['runtime'], 'NOT_PROBED')


class DemoCardTests(unittest.TestCase):
    def test_offline_card_has_no_external_resources_or_credential_inputs(self):
        from html.parser import HTMLParser
        root = SCRIPT.parents[1]
        class CardParser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'input':
                    assert attrs.get('type') == 'checkbox', 'card must not collect private input'
                assert 'src' not in attrs, 'card must have no external resource'
                if tag == 'a':
                    target = attrs['href']
                    assert ':' not in target and not target.startswith('//')
                    assert (root / 'docs/demo' / target).is_file(), 'broken local reference'
        source = (root / 'docs/demo/AcceptanceWalk.html').read_text()
        CardParser().feed(source)
        self.assertIn("connect-src 'none'", source)
        for forbidden in ('localStorage', 'sessionStorage', 'fetch(', 'XMLHttpRequest'):
            self.assertNotIn(forbidden, source)

    def test_card_goal_and_reoffer_labels_match_actual_product(self):
        root = SCRIPT.parents[1]
        product = (root / 'src/parkweave/web.html').read_text()
        card = (root / 'docs/demo/AcceptanceWalk.html').read_text()
        for text in ('本地记录重验', '请原执行者重新确认新版材料', '开始资料准备', '核对此Case协作入口与已有Run访问'):
            self.assertIn(text, product)
            self.assertIn(text, card)


if __name__ == '__main__':
    unittest.main()
