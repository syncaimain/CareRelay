"""Shared extraction boundary for inline execution and Temporal Activities."""
import os

from . import ai
from .db import audit, connect, now


def import_engine():
    engine = os.getenv('CARERELAY_IMPORT_ENGINE', 'temporal')
    if engine not in ('temporal', 'inline'):
        raise ValueError('CARERELAY_IMPORT_ENGINE must be temporal or inline.')
    return engine


def prepare_import(job_id, attempt=1):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        job = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            raise ValueError('Import job does not exist.')
        if job['status'] in ('completed', 'failed') or job['attempts'] > attempt:
            return None
        user = db.execute('SELECT * FROM caregivers WHERE id=? AND circle_id=?',
                          (job['actor_id'], job['circle_id'])).fetchone()
        source = db.execute('SELECT * FROM sources WHERE id=? AND circle_id=? AND author_id=?',
                            (job['source_id'], job['circle_id'], job['actor_id'])).fetchone()
        if not user or not user['can_import'] or not source:
            raise ValueError('Import permission or source access is no longer available.')
        if job['model'] != ai.model_name():
            raise ValueError('Worker model differs from this import. Restore the model configuration and retry.')
        caregivers = [dict(x) for x in db.execute(
            'SELECT id,name FROM caregivers WHERE circle_id=?', (job['circle_id'],))]
        existing = [dict(x) for x in db.execute('''SELECT t.* FROM tasks t
            JOIN sources s ON s.id=t.source_id WHERE t.circle_id=? AND t.status='confirmed'
            AND (s.visibility='circle' OR s.author_id=?)''', (job['circle_id'], job['actor_id']))]
        db.execute("UPDATE jobs SET status='processing',attempts=?,error=NULL WHERE id=?", (attempt, job_id))
    return dict(user), dict(source), caregivers, existing


def save_import(job_id, context, result, attempt=1):
    user, source, caregivers, existing = context
    verified = [ai.validate_evidence(item, source, caregivers, existing) for item in result.items]
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        job = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if job['status'] == 'completed':
            return job['item_count']
        # A timed-out attempt may still return after its replacement starts.
        # Only the current attempt may write, even if its model output differs.
        if job['status'] == 'failed' or job['attempts'] != attempt:
            return 0
        current = db.execute('SELECT can_import FROM caregivers WHERE id=? AND circle_id=?',
                             (user['id'], user['circle_id'])).fetchone()
        if not current or not current['can_import']:
            raise ValueError('Import permission was revoked during extraction.')
        for item in verified:
            duplicate = db.execute('SELECT id FROM tasks WHERE source_id=? AND quote=? AND kind=? AND title=?',
                                   (source['id'], item['quote'], item['kind'], item['title'])).fetchone()
            if duplicate:
                continue
            db.execute('''INSERT INTO tasks(circle_id,source_id,quote,title,kind,due_at,owner_id,location,
                uncertainty,change_type,related_task_id,model,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (user['circle_id'], source['id'], item['quote'], item['title'], item['kind'], item['due_at'],
                 item['owner_id'], item['location'], item['uncertainty'], item['change_type'],
                 item['related_task_id'], job['model'], now()))
        db.execute("UPDATE jobs SET status='completed',item_count=?,error=NULL WHERE id=?", (len(verified), job_id))
        audit(db, user, 'extraction_completed', source['id'])
    return len(verified)


def fail_import(job_id, message, attempt=None):
    with connect() as db:
        query = "UPDATE jobs SET status='failed',error=? WHERE id=? AND status NOT IN ('completed','failed')"
        values = [message[:300], job_id]
        if attempt is not None:
            query += ' AND attempts<=?'
            values.append(attempt)
        db.execute(query, values)


async def run_inline(job_id):
    try:
        context = prepare_import(job_id)
        if context is not None:
            _, source, caregivers, existing = context
            result = await ai.extract(source, caregivers, existing)
            save_import(job_id, context, result)
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else 'Local model inference failed. Check Ollama and retry.'
        fail_import(job_id, message)
