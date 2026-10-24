"""Genuine Ollama structured-output check, with private-safe synthetic text."""
import asyncio
import json
import sys
import os
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.ai import extract, model_name, validate_evidence


async def main():
    started = time.perf_counter()
    source = {'id': 1, 'text': 'Alex will book transport to Oak Clinic on 2026-10-26 at 09:00.',
              'reference_at': '2026-10-24T09:00:00+05:00'}
    people = [{'id': 1, 'name': 'Alex'}]
    result = await extract(source, people, [])
    assert result.items, 'The real model returned no items.'
    validated = [validate_evidence(item, source, people, []) for item in result.items]
    assert any(item['kind'] == 'transport' for item in validated), validated
    async with httpx.AsyncClient(trust_env=False, timeout=15) as client:
        base = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434')
        version = (await client.get(base + '/api/version')).json()['version']
        tags = (await client.get(base + '/api/tags')).json()['models']
        metadata = next(m for m in tags if m['name'] == model_name())
        shown = (await client.post(base + '/api/show', json={'model': model_name()})).json()
    assert 'Apache' in shown.get('license', ''), 'Verify the model license before use.'
    report = {'model': model_name(), 'passed': True, 'synthetic': True, 'ollama_version': version,
              'digest': metadata['digest'], 'size_bytes': metadata['size'], 'details': metadata['details'],
              'license_verified': 'Apache 2.0', 'seconds': round(time.perf_counter()-started, 3),
              'items': validated}
    (Path(__file__).resolve().parent.parent / 'docs/model-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
