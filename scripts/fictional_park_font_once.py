"""Only run48/attempt1: stage the explicitly approved original font and license."""
from hashlib import sha1, sha256
import json
import os
from pathlib import Path
import time
import urllib.request

from scripts import fictional_park_browser_once as base

COMMIT = 'f8d157532fbfaeda587e826d4cd5b21a49186f7c'
DIRECTORY = base.ROOT / '.runtime/approved-noto-run48'
ASSETS = (
    ('LICENSE', 'Sans/LICENSE', 4301, 'd952d62c065f3f35fb83a173496e90b21525aef3'),
    ('NotoSansCJKsc-Regular.otf', 'Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf',
        16437364, 'dc15562470b4f842321894787a0d066879ccff8b'),
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def inspect(path, size, blob):
    assert not path.is_symlink() and path.is_file() and path.stat().st_size == size
    git_hash, content_hash = sha1(f'blob {size}\0'.encode()), sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            git_hash.update(chunk); content_hash.update(chunk)
    assert git_hash.hexdigest() == blob, 'approved Git blob mismatch'
    return dict(file=path.name, size=size, git_blob_sha1=blob, sha256=content_hash.hexdigest())


def verified_font(*, required=False):
    if not DIRECTORY.exists() and not required:
        return None
    assert not DIRECTORY.is_symlink() and DIRECTORY.resolve() == DIRECTORY
    assert set(p.name for p in DIRECTORY.iterdir()) == {a[0] for a in ASSETS} | {'font-source.json'}
    receipt_path = DIRECTORY / 'font-source.json'
    assert not receipt_path.is_symlink() and receipt_path.is_file(), 'receipt must be a regular private file'
    receipt = json.loads(receipt_path.read_text())
    assert receipt['commit'] == COMMIT and receipt['license'] == 'SIL Open Font License 1.1'
    for name, relative, size, blob in ASSETS:
        actual = inspect(DIRECTORY / name, size, blob)
        assert receipt['assets'][name] == actual
    name = ASSETS[1][0]
    return dict(path=str(DIRECTORY / name), index=0, postscript_name='NotoSansCJKsc-Regular',
        directory=str(DIRECTORY), receipt=receipt)


def remaining(deadline):
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise TimeoutError('font/license staging exceeded shared45s allowance')
    return min(15, seconds)


def stage_asset(asset, directory, deadline):
    name, relative, size, blob = asset
    url = 'https://raw.githubusercontent.com/notofonts/noto-cjk/' + COMMIT + '/' + relative
    temporary = directory / (name + '.partial')
    count = 0
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(url, timeout=remaining(deadline)) as response, temporary.open('xb') as stream:
        assert response.geturl() == url, 'unapproved font redirect'
        # CPython hosted urllib HTTPS response: bound each blocking read by the
        # same remaining allowance, including the final one-byte size probe.
        connection = response.fp.raw._sock
        while not response.isclosed():
            connection.settimeout(remaining(deadline))
            chunk = response.read1(min(65536, size - count + 1))
            remaining(deadline)
            if not chunk:
                break
            count += len(chunk)
            assert count <= size, 'approved asset size exceeded'
            stream.write(chunk)
    remaining(deadline)
    actual = inspect(temporary, size, blob)
    remaining(deadline)
    temporary.rename(directory / name)
    remaining(deadline)
    actual['file'] = name
    return actual


def main():
    os.umask(0o077)
    report = dict(scope='APPROVED_RUN48_PRIVATE_FONT_STAGE', status='NOT_RUN',
        stage='FONT_STAGE_HOST_GATE', real_browser=False, real_model_calls=0, assets={})
    try:
        report['source_sha'] = base.require_hosted(os.environ, run_number='48')
        assert DIRECTORY.parent.resolve() == base.ROOT / '.runtime'
        DIRECTORY.mkdir(mode=0o700, exist_ok=False)
        started = time.monotonic()
        report['stage'] = 'APPROVED_OFFICIAL_FONT_AND_LICENSE_DOWNLOAD'
        for asset in ASSETS:
            report['assets'][asset[0]] = stage_asset(asset, DIRECTORY, started + 45)
        receipt = dict(commit=COMMIT, license='SIL Open Font License 1.1', assets=report['assets'])
        (DIRECTORY / 'font-source.json').write_text(json.dumps(receipt, indent=2) + '\n')
        verified_font(required=True)
        if time.monotonic() - started >= 45:
            raise TimeoutError('font staging and verification exceeded shared45s allowance')
        report.update(status='STAGED_VERIFIED', seconds=round(time.monotonic() - started, 3),
            scope='FONT_STAGING_ONLY_NOT_BROWSER_OR_BUSINESS_ACCEPTANCE')
        print(json.dumps(report), flush=True)
        return 0
    except BaseException as error:
        report.update(status='FAIL', error_type=type(error).__name__, error=str(error))
        public = None
        if report['stage'] != 'FONT_STAGE_HOST_GATE':
            public = Path(os.environ['RUNNER_TEMP']) / 'parkweave-fictional-browser-candidate'
            public.mkdir(mode=0o700, exist_ok=False)
        # Only result.json may publish. Font, license and partial bytes stay private.
        return base.finish_report(report, [], public, restart=True)


if __name__ == '__main__':
    raise SystemExit(main())
