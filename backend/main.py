import hashlib
import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from . import ai
from .db import audit, connect, digest, initialize, make_token, now
from .schemas import AvailabilityRequest, DraftRequest, ImportRequest, PermissionRequest, ReviewRequest

load_dotenv()


@asynccontextmanager
async def lifespan(app):
    initialize()
    with connect() as db:
        db.execute("UPDATE jobs SET status='failed',error='Server restarted; retry the import.' WHERE status='processing'")
    yield


app = FastAPI(title='CareRelay', version='0.1.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3104', 'http://127.0.0.1:3104'],
                   allow_methods=['GET', 'POST', 'PATCH', 'DELETE'], allow_headers=['Authorization', 'Content-Type'])


def actor(authorization: str = Header(default='')):
    if not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Sign in with your caregiver access token.')
    with connect() as db:
        row = db.execute('SELECT * FROM caregivers WHERE token_hash=?', (digest(authorization[7:]),)).fetchone()
    if not row:
        raise HTTPException(401, 'Access token is invalid or revoked.')
    return dict(row)


def require(user, permission):
    if not user[permission]:
        raise HTTPException(403, 'Your caregiver profile does not have this permission.')


def sources_for(db, user):
    return [dict(x) for x in db.execute(
        "SELECT * FROM sources WHERE circle_id=? AND (visibility='circle' OR author_id=?) ORDER BY id DESC",
        (user['circle_id'], user['id']))]


def tasks_for(db, user):
    return [dict(x) for x in db.execute('''SELECT t.*,s.label AS source_label,s.text AS source_text,
        s.synthetic,s.visibility FROM tasks t JOIN sources s ON s.id=t.source_id
        WHERE t.circle_id=? AND (s.visibility='circle' OR s.author_id=?) ORDER BY t.id DESC''',
        (user['circle_id'], user['id']))]


def task_for(db, user, task_id):
    task = next((t for t in tasks_for(db, user) if t['id'] == task_id), None)
    if not task:
        raise HTTPException(404, 'Task not found.')
    return task


def conflicts(tasks, availability):
    warnings = []
    active = [t for t in tasks if t['status'] == 'confirmed']
    for task in active:
        if task['kind'] in ('transport', 'pickup') and not (task['owner_id'] and task['accepted']):
            warnings.append({'task_id': task['id'], 'type': 'transport', 'message': 'Travel has no consenting caregiver.'})
        if not task['due_at']:
            warnings.append({'task_id': task['id'], 'type': 'date', 'message': 'Date/time needs clarification.'})
            continue
        start = datetime.fromisoformat(task['due_at'])
        end = start + timedelta(hours=1)
        for slot in availability:
            if task['owner_id'] == slot['caregiver_id'] and start < datetime.fromisoformat(slot['end_at']) and end > datetime.fromisoformat(slot['start_at']):
                warnings.append({'task_id': task['id'], 'type': 'availability', 'message': 'Proposed caregiver is unavailable during this one-hour planning window.'})
        for other in active:
            if other['id'] < task['id'] and task['owner_id'] and task['owner_id'] == other['owner_id'] and other['due_at']:
                if abs((start - datetime.fromisoformat(other['due_at'])).total_seconds()) < 3600:
                    warnings.append({'task_id': task['id'], 'type': 'overlap', 'message': f"Caregiver overlaps with task #{other['id']} (one-hour planning window)."})
    return warnings


@app.get('/api/health')
async def health():
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            r = await client.get(os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434') + '/api/tags')
            r.raise_for_status()
        names = [m['name'] for m in r.json()['models']]
        available = ai.model_name() in names
        return {'status': 'ready' if available else 'model_missing', 'model': ai.model_name(), 'local': True}
    except Exception:
        return {'status': 'offline', 'model': os.getenv('OLLAMA_MODEL', 'ministral-3:14b'), 'local': True}


@app.post('/api/demo')
def demo(request: Request):
    if os.getenv('CARERELAY_DEMO', 'true').lower() != 'true' or request.client.host not in ('127.0.0.1', '::1', 'testclient'):
        raise HTTPException(403, 'Synthetic demo setup is available only on loopback when enabled.')
    with connect() as db:
        # Every call creates an isolated fictional circle. Existing data is never reset.
        circle_id = db.execute('INSERT INTO circles(name) VALUES(?)', ('The Morgan family',)).lastrowid
        profiles = []
        for name, role, review in [('Alex', 'Coordinator', 1), ('Maya', 'Caregiver', 0), ('Sam', 'Caregiver', 0), ('Robin', 'Caregiver', 0)]:
            token = make_token()
            pk = db.execute('''INSERT INTO caregivers(circle_id,name,role,token_hash,can_import,can_review,can_brief)
                VALUES(?,?,?,?,1,?,1)''', (circle_id, name, role, digest(token), review)).lastrowid
            profiles.append({'id': pk, 'name': name, 'role': role, 'token': token})
        for profile, start, end, note in [(profiles[1], '2026-10-26T08:00:00+05:00', '2026-10-26T13:00:00+05:00', 'Work shift'),
                                          (profiles[2], '2026-10-27T09:00:00+05:00', '2026-10-27T17:00:00+05:00', 'Out of town'),
                                          (profiles[3], '2026-10-28T08:00:00+05:00', '2026-10-28T12:00:00+05:00', 'School run')]:
            db.execute('INSERT INTO availability(caregiver_id,start_at,end_at,note) VALUES(?,?,?,?)',
                       (profile['id'], start, end, note))
        audit(db, {'id': profiles[0]['id'], 'circle_id': circle_id}, 'demo_created', circle_id)
    return {'circle_id': circle_id, 'profiles': profiles, 'synthetic': True}


@app.get('/api/state')
def state(user=Depends(actor)):
    with connect() as db:
        circle = dict(db.execute('SELECT * FROM circles WHERE id=?', (user['circle_id'],)).fetchone())
        caregivers = [dict(x) for x in db.execute('SELECT id,name,role,can_import,can_review,can_brief FROM caregivers WHERE circle_id=?', (user['circle_id'],))]
        availability = [dict(x) for x in db.execute('SELECT a.* FROM availability a JOIN caregivers c ON c.id=a.caregiver_id WHERE c.circle_id=?', (user['circle_id'],))]
        tasks = tasks_for(db, user)
        sources = sources_for(db, user)
        drafts = [dict(x) for x in db.execute('SELECT * FROM drafts WHERE circle_id=? AND author_id=? ORDER BY id DESC', (user['circle_id'], user['id']))]
        events = [dict(x) for x in db.execute('SELECT * FROM audit WHERE circle_id=? AND actor_id=? ORDER BY id DESC LIMIT 100', (user['circle_id'], user['id']))]
        jobs = [dict(x) for x in db.execute('SELECT * FROM jobs WHERE circle_id=? AND actor_id=? ORDER BY created_at DESC LIMIT 20', (user['circle_id'], user['id']))]
    return {'circle': circle, 'me': {k: v for k, v in user.items() if k != 'token_hash'}, 'caregivers': caregivers,
            'availability': availability, 'tasks': tasks, 'sources': sources, 'drafts': drafts,
            'audit': events, 'jobs': jobs, 'conflicts': conflicts(tasks, availability)}


async def process_job(job_id, source_id, user):
    try:
        with connect() as db:
            source = dict(db.execute('SELECT * FROM sources WHERE id=?', (source_id,)).fetchone())
            caregivers = [dict(x) for x in db.execute('SELECT id,name FROM caregivers WHERE circle_id=?', (user['circle_id'],))]
            existing = [t for t in tasks_for(db, user) if t['status'] == 'confirmed']
        result = await ai.extract(source, caregivers, existing)
        verified = [ai.validate_evidence(i, source, caregivers, existing) for i in result.items]
        with connect() as db:
            # Permission may have been revoked while inference was running.
            current = db.execute('SELECT can_import FROM caregivers WHERE id=?', (user['id'],)).fetchone()
            if not current or not current['can_import']:
                raise ValueError('Import permission was revoked during extraction.')
            for item in verified:
                duplicate = db.execute('SELECT id FROM tasks WHERE source_id=? AND quote=? AND kind=? AND title=?',
                                       (source_id, item['quote'], item['kind'], item['title'])).fetchone()
                if duplicate:
                    continue
                db.execute('''INSERT INTO tasks(circle_id,source_id,quote,title,kind,due_at,owner_id,location,
                    uncertainty,change_type,related_task_id,model,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (user['circle_id'], source_id, item['quote'], item['title'], item['kind'], item['due_at'],
                     item['owner_id'], item['location'], item['uncertainty'], item['change_type'], item['related_task_id'], ai.model_name(), now()))
            db.execute("UPDATE jobs SET status='completed',item_count=? WHERE id=?", (len(verified), job_id))
            audit(db, user, 'extraction_completed', source_id)
    except Exception as exc:
        # No source text or credentials in error/log output.
        message = str(exc) if isinstance(exc, ValueError) else 'Local model inference failed. Check Ollama and retry.'
        with connect() as db:
            db.execute("UPDATE jobs SET status='failed',error=? WHERE id=?", (message[:300], job_id))


@app.post('/api/imports', status_code=202)
def import_text(payload: ImportRequest, background: BackgroundTasks, user=Depends(actor)):
    require(user, 'can_import')
    fingerprint = hashlib.sha256((payload.text.strip() + payload.reference_at.isoformat()).encode()).hexdigest()
    with connect() as db:
        source = db.execute('SELECT * FROM sources WHERE circle_id=? AND author_id=? AND visibility=? AND fingerprint=?',
                            (user['circle_id'], user['id'], payload.visibility, fingerprint)).fetchone()
        if source:
            job = db.execute('SELECT * FROM jobs WHERE source_id=? ORDER BY created_at DESC LIMIT 1', (source['id'],)).fetchone()
            if job and job['status'] != 'failed':
                return {'job_id': job['id'], 'duplicate': True}
            source_id = source['id']
        else:
            source_id = db.execute('''INSERT INTO sources(circle_id,author_id,label,text,reference_at,synthetic,visibility,fingerprint,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)''', (user['circle_id'], user['id'], payload.label, payload.text.strip(),
                    payload.reference_at.isoformat(), payload.synthetic, payload.visibility, fingerprint, now())).lastrowid
        job_id = secrets.token_hex(12)
        db.execute("INSERT INTO jobs(id,circle_id,actor_id,source_id,status,model,created_at) VALUES(?,?,?,?,'processing',?,?)",
                   (job_id, user['circle_id'], user['id'], source_id, ai.model_name(), now()))
        audit(db, user, 'import_started', source_id)
    background.add_task(process_job, job_id, source_id, user)
    return {'job_id': job_id, 'duplicate': False}


@app.get('/api/jobs/{job_id}')
def job_status(job_id: str, user=Depends(actor)):
    with connect() as db:
        job = db.execute('SELECT * FROM jobs WHERE id=? AND actor_id=?', (job_id, user['id'])).fetchone()
        if not job:
            raise HTTPException(404, 'Job not found.')
        return dict(job)


@app.post('/api/tasks/{task_id}/review')
def review(task_id: int, payload: ReviewRequest, user=Depends(actor)):
    require(user, 'can_review')
    with connect() as db:
        task = task_for(db, user, task_id)
        if task['status'] != 'suggested' or task['version'] != payload.version:
            raise HTTPException(409, 'This suggestion changed. Refresh before reviewing.')
        if payload.decision == 'reject':
            db.execute("UPDATE tasks SET status='rejected',version=version+1 WHERE id=?", (task_id,))
        else:
            if (task['uncertainty'] or payload.uncertainty) and not payload.acknowledge_uncertainty:
                raise HTTPException(422, 'Review and acknowledge the source uncertainties first.')
            if payload.owner_id and not db.execute('SELECT id FROM caregivers WHERE id=? AND circle_id=?', (payload.owner_id, user['circle_id'])).fetchone():
                raise HTTPException(422, 'Caregiver is not in this circle.')
            related_id = payload.related_task_id or task['related_task_id']
            if task['change_type'] != 'new':
                if related_id is None:
                    raise HTTPException(422, 'Select the original approved task.')
                old = task_for(db, user, related_id)
                if old['status'] != 'confirmed' or old['visibility'] != task['visibility']:
                    raise HTTPException(422, 'Change target must be an approved task with the same visibility.')
                if task['change_type'] == 'reschedule' and payload.due_at is None:
                    raise HTTPException(422, 'A reschedule needs a confirmed date and time.')
                db.execute("UPDATE tasks SET status='cancelled',accepted=0,version=version+1 WHERE id=?", (related_id,))
            status = 'cancelled' if task['change_type'] == 'cancel' else 'confirmed'
            db.execute('''UPDATE tasks SET title=?,kind=?,due_at=?,owner_id=?,location=?,uncertainty=?,status=?,
                related_task_id=?,accepted=0,version=version+1 WHERE id=?''',
                (payload.title, payload.kind or task['kind'], payload.due_at.isoformat() if payload.due_at else None, payload.owner_id,
                 payload.location, payload.uncertainty, status, related_id, task_id))
        audit(db, user, payload.decision, task_id)
    return {'ok': True}


@app.post('/api/tasks/{task_id}/accept')
def accept(task_id: int, user=Depends(actor)):
    with connect() as db:
        task = task_for(db, user, task_id)
        if task['status'] != 'confirmed':
            raise HTTPException(409, 'Only approved active tasks can be accepted.')
        if task['owner_id'] not in (None, user['id']):
            raise HTTPException(403, 'Only the proposed caregiver may accept this assignment.')
        db.execute('UPDATE tasks SET owner_id=?,accepted=1,version=version+1 WHERE id=?', (user['id'], task_id))
        audit(db, user, 'assignment_accepted', task_id)
    return {'ok': True}


@app.post('/api/tasks/{task_id}/done')
def done(task_id: int, user=Depends(actor)):
    with connect() as db:
        task = task_for(db, user, task_id)
        if task['owner_id'] != user['id'] or not task['accepted']:
            raise HTTPException(403, 'Only the consenting owner can complete this task.')
        if task['status'] != 'confirmed':
            raise HTTPException(409, 'Task is not active.')
        db.execute("UPDATE tasks SET status='done',version=version+1 WHERE id=?", (task_id,))
        audit(db, user, 'task_completed', task_id)
    return {'ok': True}


@app.post('/api/availability')
def availability(payload: AvailabilityRequest, user=Depends(actor)):
    if payload.start_at.utcoffset() is None or payload.end_at.utcoffset() is None or payload.end_at <= payload.start_at:
        raise HTTPException(422, 'Provide a timezone-aware end time after the start time.')
    with connect() as db:
        pk = db.execute('INSERT INTO availability(caregiver_id,start_at,end_at,note) VALUES(?,?,?,?)',
                       (user['id'], payload.start_at.isoformat(), payload.end_at.isoformat(), payload.note)).lastrowid
        audit(db, user, 'availability_added', pk)
    return {'id': pk}


@app.delete('/api/availability/{slot_id}')
def delete_availability(slot_id: int, user=Depends(actor)):
    with connect() as db:
        result = db.execute('DELETE FROM availability WHERE id=? AND caregiver_id=?', (slot_id, user['id']))
        if not result.rowcount:
            raise HTTPException(404, 'Availability block not found.')
        audit(db, user, 'availability_removed', slot_id)
    return {'ok': True}


@app.patch('/api/caregivers/{caregiver_id}/permissions')
def permissions(caregiver_id: int, payload: PermissionRequest, user=Depends(actor)):
    if user['role'] != 'Coordinator':
        raise HTTPException(403, 'Only the coordinator can manage permissions.')
    if caregiver_id == user['id']:
        raise HTTPException(422, 'The demo coordinator cannot remove their own access.')
    with connect() as db:
        result = db.execute('UPDATE caregivers SET can_import=?,can_review=?,can_brief=? WHERE id=? AND circle_id=?',
                           (payload.can_import, payload.can_review, payload.can_brief, caregiver_id, user['circle_id']))
        if not result.rowcount:
            raise HTTPException(404, 'Caregiver not found.')
        audit(db, user, 'permissions_changed', caregiver_id)
    return {'ok': True}


def render_brief(tasks, caregivers, warnings, day):
    names = {c['id']: c['name'] for c in caregivers}
    lines = [f'CareRelay · {day}', 'Approved coordination plan (organizational only):']
    verified = [t for t in tasks if t['due_at'] and t['owner_id'] and t['accepted'] and not t['uncertainty']]
    unresolved = [t for t in tasks if t not in verified]
    for heading, group in [('Verified and accepted', verified), ('Unresolved / needs a check', unresolved)]:
        lines.append('\n' + heading)
        if not group:
            lines.append('None.')
        for t in group:
            who = names.get(t['owner_id'], 'Unassigned')
            consent = 'accepted' if t['accepted'] else 'not accepted'
            lines.append(f"• {t['title']} | {t['due_at'] or 'Time unresolved'} | {who} ({consent}) [task #{t['id']}; source #{t['source_id']}]")
            if t['uncertainty']:
                lines.append('  Check: ' + t['uncertainty'])
            lines.extend('  Check: ' + w['message'] for w in warnings if w['task_id'] == t['id'])
    lines.append('\nDraft for human review. No message has been sent.')
    return '\n'.join(lines)


@app.post('/api/drafts')
async def draft(payload: DraftRequest, user=Depends(actor)):
    require(user, 'can_brief')
    try:
        datetime.strptime(payload.day, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(422, 'Invalid calendar day.')
    with connect() as db:
        # Circle-visible evidence only: private material must never enter a shareable handoff.
        candidates = [t for t in tasks_for(db, user) if t['visibility'] == 'circle' and t['status'] == 'confirmed'
                      and (not t['due_at'] or t['due_at'][:10] == payload.day)]
        caregivers = [dict(c) for c in db.execute('SELECT id,name FROM caregivers WHERE circle_id=?', (user['circle_id'],))]
        slots = [dict(a) for a in db.execute('SELECT a.* FROM availability a JOIN caregivers c ON c.id=a.caregiver_id WHERE c.circle_id=?', (user['circle_id'],))]
    if not candidates:
        raise HTTPException(422, 'No approved shared tasks for this day. Approve suggestions first.')
    try:
        selection = await ai.select_brief_tasks([{'id': t['id'], 'title': t['title'], 'due_at': t['due_at']} for t in candidates], payload.day)
    except Exception:
        raise HTTPException(502, 'Local model could not generate the handoff. Check Ollama and retry.')
    supplied = {t['id'] for t in candidates}
    if set(selection.task_ids) - supplied:
        raise HTTPException(502, 'Model returned an unsupported task reference. No draft saved.')
    # Inclusion is deterministic to prevent model omissions; prose comes only from approved records.
    text = render_brief(candidates, caregivers, conflicts(candidates, slots), payload.day)
    snapshot = json.dumps({str(t['id']): t['version'] for t in candidates}, sort_keys=True)
    with connect() as db:
        pk = db.execute('INSERT INTO drafts(circle_id,author_id,day,text,snapshot,model,created_at) VALUES(?,?,?,?,?,?,?)',
                        (user['circle_id'], user['id'], payload.day, text, snapshot, ai.model_name(), now())).lastrowid
        audit(db, user, 'draft_generated', pk)
    return {'id': pk, 'text': text, 'approved': False}


@app.post('/api/drafts/{draft_id}/approve')
def approve_draft(draft_id: int, user=Depends(actor)):
    require(user, 'can_brief')
    with connect() as db:
        draft = db.execute('SELECT * FROM drafts WHERE id=? AND author_id=?', (draft_id, user['id'])).fetchone()
        if not draft:
            raise HTTPException(404, 'Draft not found.')
        current = {str(t['id']): t['version'] for t in tasks_for(db, user)
                   if t['visibility'] == 'circle' and t['status'] == 'confirmed' and (not t['due_at'] or t['due_at'][:10] == draft['day'])}
        if current != json.loads(draft['snapshot']):
            raise HTTPException(409, 'The plan changed. Generate a fresh handoff before approving.')
        db.execute('UPDATE drafts SET approved=1 WHERE id=?', (draft_id,))
        audit(db, user, 'draft_approved', draft_id)
    return {'ok': True, 'text': draft['text']}


@app.get('/api/demo/messages')
def demo_messages(user=Depends(actor)):
    return json.loads((Path(__file__).parent.parent / 'demo' / 'dataset.json').read_text(encoding='utf-8'))
