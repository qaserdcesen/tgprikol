import sqlite3, datetime, os
DB_PATH = "/app/data/users.db"
def init_db():
    with sqlite3.connect(DB_PATH) as c: c.execute('''CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY, secret TEXT UNIQUE, expires_at TEXT,
        link TEXT, created_at TEXT)''')
def add_user(tid, secret, expires_at, link):
    with sqlite3.connect(DB_PATH) as c: c.execute('INSERT OR REPLACE INTO users VALUES (?,?,?,?,?)',
        (tid, secret, expires_at, link, datetime.datetime.now().isoformat()))
def get_user(tid):
    with sqlite3.connect(DB_PATH) as c: return c.execute('SELECT * FROM users WHERE telegram_id = ?', (tid,)).fetchone()
def delete_user(tid):
    with sqlite3.connect(DB_PATH) as c: c.execute('DELETE FROM users WHERE telegram_id = ?', (tid,))
def update_expires(tid, new_expires):
    with sqlite3.connect(DB_PATH) as c: c.execute('UPDATE users SET expires_at = ? WHERE telegram_id = ?', (new_expires, tid))


# Возвращает список пользователей, срок которых истекает в указанную дату (YYYY-MM-DD)
def get_users_by_date(date_iso):
    with sqlite3.connect(DB_PATH) as c:
        return c.execute('SELECT * FROM users WHERE expires_at = ?', (date_iso,)).fetchall()
