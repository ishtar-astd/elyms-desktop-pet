import sqlite3
from contextlib import closing, contextmanager


RECENT_TURNS = 8
NOTES_LIMIT = 2000


class MemoryStoreError(Exception):
    pass


class MemoryStore:
    def __init__(self, path):
        self.path = path

    @contextmanager
    def connect(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=0.5)) as db, db:
                db.executescript('''
                    CREATE TABLE IF NOT EXISTS turns (
                        id INTEGER PRIMARY KEY,
                        base TEXT NOT NULL,
                        model TEXT NOT NULL,
                        message TEXT NOT NULL,
                        reply TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS turns_by_model ON turns (base, model, id);
                    CREATE TABLE IF NOT EXISTS memory (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        notes TEXT NOT NULL
                    );
                ''')
                yield db
        except (OSError, sqlite3.Error) as exc:
            raise MemoryStoreError('无法访问本机记忆。') from exc

    def history(self, base, model):
        with self.connect() as db:
            turns = db.execute(
                'SELECT message, reply FROM turns WHERE base = ? AND model = ? ORDER BY id',
                (base, model),
            ).fetchall()
        messages = []
        for message, reply in turns:
            messages.extend(({'role': 'user', 'content': message},
                             {'role': 'assistant', 'content': reply}))
        return messages

    def append_turn(self, base, model, message, reply):
        with self.connect() as db:
            db.execute('INSERT INTO turns (base, model, message, reply) VALUES (?, ?, ?, ?)',
                       (base, model, message, reply))
            db.execute('''
                DELETE FROM turns WHERE base = ? AND model = ? AND id IN (
                    SELECT id FROM turns WHERE base = ? AND model = ?
                    ORDER BY id DESC LIMIT -1 OFFSET ?
                )
            ''', (base, model, base, model, RECENT_TURNS))

    def clear_history(self, base, model):
        with self.connect() as db:
            db.execute('DELETE FROM turns WHERE base = ? AND model = ?', (base, model))

    @staticmethod
    def read_notes(db):
        row = db.execute('SELECT notes FROM memory WHERE id = 1').fetchone()
        return row[0] if row else ''

    def notes(self):
        with self.connect() as db:
            return self.read_notes(db)

    @staticmethod
    def write_notes(db, notes):
        if len(notes) > NOTES_LIMIT:
            raise MemoryStoreError(f'长期记忆最多可保存 {NOTES_LIMIT} 个字符。')
        db.execute('INSERT OR REPLACE INTO memory (id, notes) VALUES (1, ?)', (notes,))

    def save_notes(self, notes):
        with self.connect() as db:
            self.write_notes(db, notes.strip())

    def remember(self, note):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            notes = self.read_notes(db).splitlines()
            if note not in notes:
                notes.append(note)
                self.write_notes(db, '\n'.join(notes))
