import sqlite3
from config import Config
from werkzeug.security import generate_password_hash, check_password_hash


def get_db():
    """开一条数据库连接（每个函数自己开自己关，用完即还）"""
    conn = sqlite3.connect(Config.DB_FILE)
    conn.row_factory = sqlite3.Row # 查出来的行变成"按名字取值"的字典风格
    return conn


def init_db():
    """建四张表。IF NOT EXISTS = 已存在就跳过（migrate.py 那次的教训）"""
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
            
        CREATE TABLE IF NOT EXISTS friend_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER NOT NULL,            -- 申请人
            to_user_id   INTEGER NOT NULL,            -- 被申请人
            status TEXT NOT NULL DEFAULT 'pending',   -- pending / accepted / rejected
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
            
        CREATE TABLE IF NOT EXISTS friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,                 -- 我
            friend_id INTEGER NOT NULL,               -- 好友（A→B、B→A 各存一行，查谁的都简单）
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),  
            UNIQUE(user_id, friend_id)                -- 同一对好友只许存一次  
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


def get_new_messages(after_id, limit=50):
    """拿比 after_id 更新的消息（轮询增量用）。正序返回，最多 limit 条。"""
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM messages WHERE id > ? ORDER BY id ASC LIMIT ?',
        (after_id, limit)
    ).fetchall()
    conn.close()
    return rows   # ORDER BY id 默认从小到大 = 已经正序，不用 reversed


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


def list_users_except (user_id):
    """列除自己外的所有用户。游客返回空列表"""
    if user_id is None:
        return []
    conn = get_db()
    rows = conn.execute(
        'SELECT id, username FROM users WHERE id != ? ORDER BY id',
        (user_id,)
    ).fetchall()
    conn.close()
    return rows

# ---------- 好友系统：申请 → 验证通过 → 好友 ----------

def create_friend_request(from_user_id, to_user_id):
    """发起好友申请（status 默认 pending，等对方验证）。返回新申请的编号"""
    conn = get_db()
    cursor = conn.execute(
        'INSERT INTO friend_requests (from_user_id, to_user_id) VALUES (?, ?)',
        (from_user_id, to_user_id)
    )
    conn.commit()
    conn.close()
    return cursor.lastrowid

def get_pending_request_between(user_a, user_b):
    """查两人之间有没有 pending 的申请（双向查：A→B 或 B→A 都算）。
    有 → 返回那行；没有 → 返回 None"""
    conn = get_db()
    row = conn.execute(
        """SELECT * FROM friend_requests
            WHERE status = 'pending'
             AND ((from_user_id = ? AND to_user_id = ?)
              OR (from_user_id = ? AND to_user_id = ?))""",
        (user_a, user_b, user_b, user_a)
    ).fetchone()
    conn.close()
    return row

def get_incoming_requests(user_id):
    """发给我的待处理申请（JOIN users 拿申请人名字）"""
    conn = get_db()
    rows = conn.execute(
        """SELECT fr.id, fr.from_user_id, u.username, fr.created_at
            FROM friend_requests fr JOIN users u ON fr.from_user_id = u.id
            WHERE fr.to_user_id = ? AND fr.status = 'pending'
            ORDER BY fr.id""",
        (user_id,)
    ).fetchall()
    conn.close()
    return rows

def get_outgoing_requests(user_id):
    """我发出去、还没被处理的申请（JOIN users 拿对方名字）"""
    conn = get_db()
    rows = conn.execute(
        """SELECT fr.id, fr.to_user_id, u.username, fr.created_at
            FROM friend_requests fr JOIN users u ON fr.to_user_id = u.id
            WHERE fr.from_user_id = ? AND fr.status = 'pending'
            ORDER BY fr.id""",
        (user_id,)
    ).fetchall()
    conn.close()
    return rows

def are_friends(user_id, friend_id):
    """两人是否已经是好友"""
    conn = get_db()
    row = conn.execute(
        'SELECT id FROM friends WHERE user_id = ? AND friend_id = ?',
        (user_id, friend_id)
    ).fetchone()
    conn.close()
    return row is not None

def get_friend_request_by_id(request_id):
    """按编号拿一张申请单（通过/拒绝前先验：存不存在？是发给谁的？）"""
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM friend_requests WHERE id = ?', (request_id,)
    ).fetchone()
    conn.close()
    return row

def accept_friend_request(request_id):
    """验证通过：申请单改 accepted + 写两行好友关系（A→B 和 B→A）"""
    conn = get_db()
    conn.execute(
        "UPDATE friend_requests SET status = 'accepted' WHERE id = ?",
        (request_id,)
    )
    req = conn.execute(
        'SELECT from_user_id, to_user_id FROM friend_requests WHERE id = ?',
        (request_id,)
    ).fetchone()
    conn.execute(
        'INSERT INTO friends (user_id, friend_id) VALUES (?, ?)',
        (req['from_user_id'], req['to_user_id'])
    )
    conn.execute(
        'INSERT INTO friends (user_id, friend_id) VALUES (?, ?)',
        (req['to_user_id'], req['from_user_id'])
    )
    conn.commit()
    conn.close()

def reject_friend_request(request_id):
    """拒绝：申请单改 rejected，不建好友关系（但不删记录，留痕）"""
    conn = get_db()
    conn.execute(
        "UPDATE friend_requests SET status = 'rejected' WHERE id = ?",
        (request_id,)
    )
    conn.commit()
    conn.close()

def get_friends(user_id):
    """我的好友列表（JOIN users 拿名字，只挑 id 和 username）"""
    conn = get_db()
    rows =conn.execute(
        """SELECT f.friend_id AS id, u.username
            FROM friends f JOIN users u ON f.friend_id = u.id
            WHERE f.user_id = ? ORDER BY u.username""",
        (user_id,)
    ).fetchall()
    conn.close()
    return rows
