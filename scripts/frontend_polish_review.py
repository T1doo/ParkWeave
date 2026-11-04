"""Bounded loopback visual review; original HTML and historical synthetic DTOs only.

No authentication, database, model, reservation or mutation is provided.
8876..8879 serve live working-tree HTML with READY/EMPTY/ERROR/DENIED DTOs.
8880 serves immutable HTML from the reviewed main baseline for comparisons.
"""
import argparse
import importlib.util
from pathlib import Path
import subprocess
from threading import Thread
import time


ROOT = Path(__file__).resolve().parents[1]
BASE = 'c5d39569e0ee669196354ad97b8bc48099af2914'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=600)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 1800:
        parser.error('seconds must be 1..1800')
    spec = importlib.util.spec_from_file_location(
        'polish_fixture', ROOT / 'tests/test_frontend_preview_stdlib.py')
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    preview = fixture.preview
    names = {'workspace-design.css': 'workspace_design.css',
             'workspace-design.js': 'workspace_design.js',
             'parkweave-mark.png': 'assets/parkweave-mark-128.png',
             'web.html': 'web.html',
             'local_preparation_web.html': 'local_preparation_web.html',
             'local-command-pending.js': 'local_command_pending.js'}
    current = {name: (ROOT / 'src/parkweave' / source).read_bytes()
               for name, source in names.items()}
    baseline = {name: subprocess.check_output(
        ['git', 'show', BASE + ':src/parkweave/' + source], cwd=ROOT)
        for name, source in names.items() if name not in ('parkweave-mark.png','workspace-design.css','workspace-design.js')}
    for name in ('parkweave-mark.png','workspace-design.css','workspace-design.js'):
        baseline[name] = current[name]
    servers = []
    try:
        for port, state in [(8876, 'READY'), (8877, 'EMPTY'),
                            (8878, 'ERROR'), (8879, 'DENIED'), (8880, 'READY')]:
            handler = preview.handler_for({'source_commit': BASE},
                baseline if port == 8880 else current,
                fixture.historical_fixture(), state)
            if port != 8880:
                class Live(handler):
                    def do_GET(self):
                        if self.path in preview.STATIC:
                            name, kind = preview.STATIC[self.path]
                            return self.reply(200, kind,
                                (ROOT / 'src/parkweave' / names[name]).read_bytes())
                        return super().do_GET()
                handler = Live
            server = preview.LoopbackServer(('127.0.0.1', port), handler)
            servers.append(server)
            Thread(target=server.serve_forever, daemon=True).start()
        print('READ-ONLY REVIEW: http://127.0.0.1:8876/web.html ; '
              'immutable main: http://127.0.0.1:8880/web.html ; '
              f'expires after {args.seconds}s', flush=True)
        time.sleep(args.seconds)
    except KeyboardInterrupt:
        pass
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
