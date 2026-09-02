import sqlite3
from config import Config
from werkzeug.security import generate_password_hash, check_password_hash



def get_db():
    """开一条数据库连接（每个函数自己开自己关，用完即还）"""
    conn = sqlite3.connect(Config.DB_FILE)
    conn.row_factory = sqlite3.Row # 查出来的行变成"按名字取值"的字典风格
    return conn


def init_db():
    """建两张表。IF NOT EXISTS = 已存在就跳过（migrate.py 那次的教训）"""
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
        
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
    ''')
    conn.commit()
    conn.close()


def add_message(user_id, username, content):
    """存一条新消息。user_id 可为 None（游客），username 是名字快照"""
    conn = get_db()
    cursor = conn.execute(
        'INSERT INTO messages (user_id, username, content) VALUES (?, ?, ?)',
        (user_id, username, content)
    )
    conn.commit()
    message_id = cursor.lastrowid
    row = conn.execute(
        'SELECT * FROM messages WHERE id = ?', (message_id,)
    ).fetchone()
    conn.close()
    return row


def get_recent_messages(limit=50, before_id=None):
    """拿消息。不传 before_id = 最新 limit 条；传了 = 比 before_id 更早的 limit 条（游标分页）"""
    conn = get_db()
    sql = 'SELECT * FROM messages'
    params = []
    if before_id is not None:
        sql += ' WHERE id < ?'
        params.append(before_id)
    sql += ' ORDER BY id DESC LIMIT ?'
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return list(reversed(rows))  # 先拿最新的，再整个翻过来


def create_user(username, password):
    """注册：把用户名和密码的哈希存进 users 表。返回新用户的 id"""
    conn = get_db()
    cursor = conn.execute(
        'INSERT INTO users (username, password_hash) VALUES (?, ?)',
        (username, generate_password_hash(password))   # 存的是哈希，不是密码！
    )
    conn.commit()
    conn.close()
    return cursor.lastrowid


def get_user_by_username(username):
    """按用户名找人。找到返回那一行，找不到返回 None"""
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM users WHERE username = ?', (username,)
    ).fetchone()
    conn.close()
    return row


def get_user_by_id(user_id):
    """按编号找人（session 里存的是 id，me 接口靠它认人）"""
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM users WHERE id = ?', (user_id,)
    ).fetchone()
    conn.close()
    return row


def get_last_message_time(user_id):
    """查某个用户最近一条消息的时间。游客(user_id=None)也支持"""
    conn = get_db()
    row = conn.execute(
        'SELECT created_at FROM messages WHERE user_id IS ? ORDER BY id DESC LIMIT 1',
        (user_id,)
    ).fetchone()
    conn.close()
    return row['created_at'] if row else None