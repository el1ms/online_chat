import sqlite3
from flask import Flask, jsonify, request, render_template, session
from werkzeug.security import check_password_hash
from datetime import datetime


import db
from config import Config

app = Flask(__name__)
app.config.from_object(Config)  # 把 config.py 的配置一行全装上


# ---------- 页面（只此一处吐 HTML，就是个壳子） ----------

@app.route('/')
def index():
    return render_template('index.html')


# ---------- API（从此只吐 JSON，网页和未来 App 共用） ----------

@app.route('/api/messages', methods=['GET'])
def get_messages():
    """查询参数：?limit=50&before_id=120（都可省略）"""
    limit = request.args.get('limit', 50, type=int)
    before_id = request.args.get('before_id', type=int)
    rows = db.get_recent_messages(limit=limit, before_id=before_id)
    return jsonify([dict(row) for row in rows])


@app.route('/api/messages', methods=['POST'])
def send_message():
    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()

    # 后端校验：前端会拦，但这里必须再拦一遍（永不信任前端）
    if not content:
        return jsonify({'error': '消息不能为空'}), 400
    if len(content) > Config.MAX_MESSAGE_LEN:
        return jsonify({'error': f'消息最长 {Config.MAX_MESSAGE_LEN} 字'}), 400

    # 消息归属：身份从 session 拿，绝不信任前端传来的名字
    user_id = session.get('user_id')
    if user_id is None:
        username = '路人甲'                      # 真游客
    else:
        username = db.get_user_by_id(user_id)['username']   # 从数据库查真名

    # 冷却闸门：查上一条消息时间，5秒内拒绝（真保险，挡绕过页面的小人）
    last_time = db.get_last_message_time(user_id)
    if last_time is not None:
        last = datetime.strptime(last_time, '%Y-%m-%d %H:%M:%S')
        seconds_elapsed = (datetime.now() - last).total_seconds()
        if seconds_elapsed < Config.COOLDOWN_SECONDS:
            wait = Config.COOLDOWN_SECONDS - seconds_elapsed
            return jsonify({'error': f'太快了，请等 {wait:.0f} 秒'}), 429

    row = db.add_message(user_id, username, content)
    return jsonify(dict(row)), 201


# ---------- 用户 API（第 2 课：session 手环） ----------

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    # 后端校验（永不信任前端）
    if not username or not password:
        return jsonify({'error':'用户名和密码都不能为空'}), 400
    if len(username) > 20:
        return jsonify({'error':'用户名最长 20 字'}), 400
    if len(password) < 6:
        return jsonify({'error':'密码至少 6 位'}), 400

    try:
        user_id = db.create_user(username, password)
    except sqlite3.IntegrityError:
        return jsonify({'error':'这名字被抢了，换一个吧'}), 400

    session['user_id'] = user_id   # 注册成功 = 直接发手环（免二次登录）
    return jsonify({'id': user_id, 'username': username}), 201


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    user = db.get_user_by_username(username)
    # 人不存在 或 密码不对 → 同一个错误（不告诉坏人"这名字存在"）
    if user is None or not check_password_hash(user['password_hash'], password):
        return jsonify({'error':'用户名或密码不对'}), 400

    session['user_id'] = user['id']
    return jsonify({'id': user['id'], 'username': user['username']})


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()              # 手环作废
    return jsonify({'ok': True})


@app.route('/api/me', methods=['GET'])
def me():
    """当前是谁：登录了返回用户信息，游客返回 null"""
    user_id = session.get('user_id')
    if user_id is None:
        return jsonify(None)
    user = db.get_user_by_id(user_id)
    return jsonify({'id': user['id'], 'username': user['username']})


db.init_db()   # 挪出来：python app.py 和 gunicorn 都能触发

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)
