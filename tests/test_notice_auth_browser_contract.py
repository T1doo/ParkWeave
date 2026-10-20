"""Bounded CI and fixture checks; never launches a browser or business backend."""
import http.client
import subprocess
import time
import unittest

from scripts.notice_auth_browser_once import A, BRANCH, Boundary, Fixture, require_hosted_once, serve


class NoticeBrowserContract(unittest.TestCase):
    def test_exact_public_first_attempt_and_reviewed_product(self):
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        valid = dict(NOTICE_REPOSITORY='T1doo/ParkWeave', NOTICE_REF=BRANCH, NOTICE_EVENT='push',
                     NOTICE_ATTEMPT='1', NOTICE_NUMBER='1', NOTICE_PUBLIC='true', NOTICE_SHA=head,
                     RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='Linux')
        self.assertEqual(require_hosted_once(valid), head)
        for key, value in [('NOTICE_REPOSITORY', 'other/repo'), ('NOTICE_REF', 'refs/heads/main'),
                           ('NOTICE_EVENT', 'workflow_dispatch'), ('NOTICE_ATTEMPT', '2'),
                           ('NOTICE_NUMBER', '2'), ('NOTICE_PUBLIC', 'false'), ('NOTICE_SHA', '0' * 40),
                           ('RUNNER_ENVIRONMENT', 'self-hosted'), ('PARKWEAVE_DSN', 'SYNTHETIC_FORBIDDEN')]:
            with self.assertRaises(RuntimeError):
                require_hosted_once({**valid, key: value})

    def test_exact_loopback_origin_existing_paths_and_one_post_budget(self):
        base = 'http://127.0.0.1:8123'
        boundary = Boundary(base, 'refusal', {})
        for method, url in [('GET', 'https://example.com/'), ('GET', 'http://127.0.0.1:8124/'),
                            ('POST', base + '/api/runs'), ('GET', base + '/api/dispatch-notices?cursor=x'),
                            ('DELETE', base + '/api/dispatch-notices/' + A),
                            ('POST', base + '/api/dispatch-notices/' + A + '/commands?retry=1')]:
            self.assertFalse(boundary.permit(method, url))
        path = base + '/api/dispatch-notices/' + A + '/commands'
        self.assertTrue(boundary.permit('POST', path))
        self.assertFalse(boundary.permit('POST', path))

    def test_headers_arrive_without_body_and_teardown_releases_owned_threads(self):
        fixture = Fixture('refusal', 403)
        started = time.monotonic()
        with serve(fixture) as base:
            conn = http.client.HTTPConnection(base.removeprefix('http://'), timeout=2)
            try:
                conn.request('POST', '/api/dispatch-notices/' + A + '/commands',
                             body='{"action":"MARK_READ","expected_revision":1}',
                             headers={'Content-Type': 'application/json'})
                response = conn.getresponse()
                self.assertEqual(response.status, 403)
                self.assertTrue(fixture.headers_sent.wait(1))
                self.assertEqual(response.getheader('Content-Length'), '1024')
                self.assertFalse(fixture.release_body.is_set())
                self.assertFalse(fixture.body_handler_done.is_set())
            finally:
                conn.close()
        self.assertTrue(fixture.release_body.is_set())
        self.assertTrue(fixture.body_handler_done.is_set())
        self.assertFalse(any(t.is_alive() for t in fixture.threads))
        self.assertLess(time.monotonic() - started, 4)


if __name__ == '__main__':
    unittest.main()
