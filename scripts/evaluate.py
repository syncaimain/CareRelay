"""Run genuine local model extraction over the labeled synthetic corpus.

Metrics are strict, source-level micro precision/recall. A predicted item matches
the expected kind and exact source attribution; owner and date metrics are
reported separately. Change notices run without prior approved tasks and should
therefore remain unresolved until a reviewer selects a target.
"""
import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import ai
from backend.ai import extract, model_name, validate_evidence

ROOT = Path(__file__).resolve().parent.parent


def score_message(message, items):
    """Score fields independently of category; failed/missing predictions count as errors."""
    expected = message['kind']
    matches = [item for item in items if item['kind'] == expected]
    tp = int(bool(expected and matches))
    score = {'tp': tp, 'fp': len(items) - tp, 'fn': int(bool(expected and not matches))}
    # Each reference source has one obligation. Multiple predictions do not get
    # to cherry-pick a correct field from different records.
    item = items[0] if len(items) == 1 else None
    people = {'Alex': 1, 'Maya': 2, 'Sam': 3, 'Robin': 4}
    score['owner_correct'] = bool(item and item['owner_id'] == people[message['owner']]) if message.get('owner') else None
    explicit = re.search(r'(\d{4}-\d{2}-\d{2}) at (\d{2}:\d{2})', message['text'])
    score['date_correct'] = None
    if explicit and not message.get('change'):
        expected_date = datetime.fromisoformat(explicit[1] + 'T' + explicit[2] + ':00+05:00')
        score['date_correct'] = bool(item and item['due_at'] and datetime.fromisoformat(item['due_at']) == expected_date)
    score['change_correct'] = bool(item and item['change_type'] == message['change']) if message.get('change') else None
    return score


async def evaluate(limit=0, output='docs/evaluation-results.json'):
    dataset = json.loads((ROOT / 'demo/dataset.json').read_text(encoding='utf-8'))
    messages = dataset['messages'][:limit or None]
    people = [{'id': i + 1, 'name': n} for i, n in enumerate(['Alex', 'Maya', 'Sam', 'Robin'])]
    rows = []
    for index, message in enumerate(messages):
        started = time.perf_counter()
        source = {'id': index + 1, 'text': message['text'], 'reference_at': dataset['reference_at']}
        raw_items = []
        try:
            result = await extract(source, people, [])
            raw_items = result.model_dump(mode='json')['items']
            validated = [validate_evidence(item, source, people, []) for item in result.items]
            score = score_message(message, validated)
            rows.append({'id': message['id'], **score, 'quote_verified': True,
                         'seconds': round(time.perf_counter()-started, 3), 'raw_items': raw_items, 'items': validated})
            print(f"{message['id']}: tp={score['tp']} fp={score['fp']} fn={score['fn']}", flush=True)
        except Exception as exc:
            rows.append({'id': message['id'], **score_message(message, []), 'raw_items': raw_items, 'items': [],
                         'quote_verified': False, 'error': type(exc).__name__, 'seconds': round(time.perf_counter()-started, 3)})
            print(f"{message['id']}: failed ({type(exc).__name__})", flush=True)
    tp, fp, fn = (sum(row[k] for row in rows) for k in ('tp', 'fp', 'fn'))
    metric = lambda k: {'correct': sum(row.get(k) is True for row in rows), 'total': sum(row.get(k) is not None for row in rows)}
    report = {'model': model_name(), 'synthetic': True, 'dataset_use': 'development set; prompt tuned after baseline',
              'dataset_sha256': hashlib.sha256((ROOT / 'demo/dataset.json').read_bytes()).hexdigest(),
              'ai_code_sha256': hashlib.sha256(Path(ai.__file__).read_bytes()).hexdigest(),
              'scoring_version': 2, 'measured_at': datetime.now().astimezone().isoformat(),
              'messages': len(rows), 'precision': tp/(tp+fp) if tp+fp else 0,
              'recall': tp/(tp+fn) if tp+fn else 0, 'true_positives': tp, 'false_positives': fp,
              'false_negatives': fn, 'owner_attribution': metric('owner_correct'),
              'explicit_timestamps': metric('date_correct'),
              'change_operations': metric('change_correct'),
              'failed_messages': sum('error' in row for row in rows),
              'total_seconds': round(sum(row['seconds'] for row in rows), 3), 'results': rows}
    out = ROOT / output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'results'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--out', default='docs/evaluation-results.json')
    args = parser.parse_args()
    asyncio.run(evaluate(args.limit, args.out))
