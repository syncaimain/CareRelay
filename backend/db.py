import hashlib
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


@contextmanager
def connect():
    path = os.getenv('CARERELAY_DB', 'data/carerelay.sqlite3')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS circles (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, synthetic INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS caregivers (
          id INTEGER PRIMARY KEY, circle_id INTEGER NOT NULL REFERENCES circles(id),
          name TEXT NOT NULL, role TEXT NOT NULL, token_hash TEXT UNIQUE NOT NULL,
          can_import INTEGER NOT NULL, can_review INTEGER NOT NULL, can_brief INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS availability (
          id INTEGER PRIMARY KEY, caregiver_id INTEGER NOT NULL REFERENCES caregivers(id),
          start_at TEXT NOT NULL, end_at TEXT NOT NULL, note TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sources (
          id INTEGER PRIMARY KEY, circle_id INTEGER NOT NULL REFERENCES circles(id),
          author_id INTEGER NOT NULL REFERENCES caregivers(id), label TEXT NOT NULL,
          text TEXT NOT NULL, reference_at TEXT NOT NULL, synthetic INTEGER NOT NULL,
          visibility TEXT NOT NULL, fingerprint TEXT NOT NULL, created_at TEXT NOT NULL,
          UNIQUE(circle_id, author_id, visibility, fingerprint)
        );
        CREATE TABLE IF NOT EXISTS tasks (
          id INTEGER PRIMARY KEY, circle_id INTEGER NOT NULL REFERENCES circles(id),
          source_id INTEGER NOT NULL REFERENCES sources(id), quote TEXT NOT NULL,
          title TEXT NOT NULL, kind TEXT NOT NULL, due_at TEXT, owner_id INTEGER REFERENCES caregivers(id),
          location TEXT NOT NULL DEFAULT '', uncertainty TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'suggested', change_type TEXT NOT NULL DEFAULT 'new',
          related_task_id INTEGER REFERENCES tasks(id), accepted INTEGER NOT NULL DEFAULT 0,
          model TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY, circle_id INTEGER NOT NULL REFERENCES circles(id),
          actor_id INTEGER NOT NULL REFERENCES caregivers(id), source_id INTEGER NOT NULL REFERENCES sources(id),
          status TEXT NOT NULL, error TEXT, item_count INTEGER NOT NULL DEFAULT 0,
          model TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS drafts (
          id INTEGER PRIMARY KEY, circle_id INTEGER NOT NULL REFERENCES circles(id),
          author_id INTEGER NOT NULL REFERENCES caregivers(id), day TEXT NOT NULL,
          text TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0, snapshot TEXT NOT NULL,
          model TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit (
          id INTEGER PRIMARY KEY, circle_id INTEGER NOT NULL REFERENCES circles(id),
          actor_id INTEGER NOT NULL REFERENCES caregivers(id), action TEXT NOT NULL,
          target TEXT NOT NULL, created_at TEXT NOT NULL
        );
        ''')
        # Existing local databases keep their original inline jobs. New imports
        # select their engine explicitly; migrations never rewrite demo history.
        columns = {row['name'] for row in db.execute('PRAGMA table_info(jobs)')}
        for name, declaration in {
            'engine': "TEXT NOT NULL DEFAULT 'inline'",
            'workflow_id': 'TEXT',
            'dispatched': 'INTEGER NOT NULL DEFAULT 0',
            'attempts': 'INTEGER NOT NULL DEFAULT 0',
        }.items():
            if name not in columns:
                db.execute(f'ALTER TABLE jobs ADD COLUMN {name} {declaration}')


def audit(db, actor, action, target):
    db.execute('INSERT INTO audit(circle_id,actor_id,action,target,created_at) VALUES(?,?,?,?,?)',
               (actor['circle_id'], actor['id'], action, str(target), now()))


def make_token():
    return secrets.token_urlsafe(32)
