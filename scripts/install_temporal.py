"""Install the verified Windows x64 Temporal CLI locally, without changing PATH."""
import hashlib
import io
import platform
import zipfile
from pathlib import Path

import httpx

VERSION = '1.9.1'
NAME = f'temporal_cli_{VERSION}_windows_amd64.zip'
SHA256 = 'babb65844835045c91fb98930fe10b81de28db80c8c609180473d2c0b18c7589'
BASE = f'https://github.com/temporalio/cli/releases/download/v{VERSION}/'


def main():
    if platform.system() != 'Windows' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise SystemExit('Use the official installation guide for this platform: https://docs.temporal.io/cli/setup-cli')
    with httpx.Client(trust_env=False, follow_redirects=True, timeout=120) as client:
        response = client.get(BASE + 'checksums.txt')
        response.raise_for_status()
        upstream = next(line.split()[0] for line in response.text.splitlines() if line.split()[-1] == NAME)
        if upstream != SHA256:
            raise SystemExit('Upstream checksum differs from the verified release. No executable was installed.')
        response = client.get(BASE + NAME)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != SHA256:
            raise SystemExit('Download checksum failed. No executable was installed.')
    target = Path(__file__).resolve().parent.parent / '.tools' / 'temporal'
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        name = next(n for n in archive.namelist() if n.split('/')[-1] == 'temporal.exe')
        (target / 'temporal.exe').write_bytes(archive.read(name))
    print(f'Temporal CLI {VERSION} installed at {target / "temporal.exe"}; upstream SHA-256 matched.')


if __name__ == '__main__':
    main()
