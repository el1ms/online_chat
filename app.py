import sqlite3
from functools import wraps
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
    """查询参数：?limit=50&before_id=120（向上翻）/ &after_id=130（向下追）"""
    limit = request.args.get('limit', 50, type=int)
    before_id = request.args.get('before_id', type=int)
    after_id = request.args.get('after_id', type=int)

    if after_id is not None:
        rows = db.get_new_messages(after_id, limit)          # 增量：更新的
    else:
        rows = db.get_recent_messages(limit=limit, before_id=before_id)  # 全量/历史
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


@app.route('/api/users', methods=['GET'])
def list_users():
    """列出所有用户（不含自己，不含密码哈希）"""
    me_id = session.get('user_id')          # 从手环知道"我是谁"
    rows = db.list_users_except(me_id)      # 数据库层去查
    return jsonify([dict(row) for row in rows])


# ---------- 好友 API（好友系统：申请 → 验证通过 → 好友） ----------

def login_required(fn):
    """登录闸门：好友功能必须戴手环，游客一律 401。
    用法：@app.route(...) 下一行 @login_required，跟 @app.route 叠着写"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get('user_id') is None:
            return jsonify({'error': '请先登录'}), 401
        return fn(*args, **kwargs)
    return wrapper


@app.route('/api/friend_requests', methods=['POST'])
@login_required
def send_friend_request():
    """发起申请。前端传 {to_user_id: 对方编号}"""
    me_id = session.get('user_id')           # 我是谁（从手环拿，不信前端）
    data = request.get_json(silent=True) or {}
    to_user_id = data.get('to_user_id')

    if not isinstance(to_user_id, int) or isinstance(to_user_id, bool):
        return jsonify({'error': '参数不对'}), 400
    if to_user_id == me_id:
        return jsonify({'error': '不能加自己'}), 400
    if db.get_user_by_id(to_user_id) is None:
        return jsonify({'error': '这人不存在'}), 400
    if db.are_friends(to_user_id, me_id):
        return jsonify({'error': '你们已经是好友了'}), 400

    existing = db.get_pending_request_between(me_id, to_user_id)
    if existing is not None:
        if existing['from_user_id'] == me_id:
            return jsonify({'error': '已经申请过，等对方验证'}), 400
        else:
            return jsonify({'error': '对方已向你发出申请，请先处理'}), 400

    request_id = db.create_friend_request(me_id, to_user_id)
    return jsonify({'id': request_id}), 201


@app.route('/api/friend_requests', methods=['GET'])
@login_required
def list_friend_requests():
    """我的申请两本账：incoming = 发给我的（待验证）/ outgoing = 我发出的"""
    me_id = session.get('user_id')
    return jsonify({
        'incoming': [dict(r) for r in db.get_incoming_requests(me_id)],
        'outgoing': [dict(r) for r in db.get_outgoing_requests(me_id)]
    })


@app.route('/api/friend_requests/<int:request_id>/accept', methods=['POST'])
@login_required
def accept_request(request_id):
    """验证通过：只有收申请的人能点，且只能点一次"""
    me_id = session.get('user_id')
    req = db.get_friend_request_by_id(request_id)

    if req is None:
        return jsonify({'error': '申请不存在'}), 404
    if req['to_user_id'] != me_id:                       # 不是发给我的 → 越权
        return jsonify({'error': '只能处理发给你的申请'}), 403
    if req['status'] != 'pending':                       # 处理过了
        return jsonify({'error': '这条申请已经处理过'}), 400

    db.accept_friend_request(request_id)
    return jsonify({'ok': True})


@app.route('/api/friend_requests/<int:request_id>/reject', methods=['POST'])
@login_required
def reject_request(request_id):
    """拒绝：同样只有收申请的人能点，且只能点一次"""
    me_id = session.get('user_id')
    req = db.get_friend_request_by_id(request_id)

    if req is None:
        return jsonify({'error': '申请不存在'}), 404
    if req['to_user_id'] != me_id:
        return jsonify({'error': '只能处理发给你的申请'}), 403
    if req['status'] != 'pending':
        return jsonify({'error': '这条申请已经处理过'}), 400

    db.reject_friend_request(request_id)
    return jsonify({'ok': True})


@app.route('/api/friends', methods=['GET'])
@login_required
def list_friends():
    """我的好友列表（通过了验证的人）"""
    me_id = session.get('user_id')
    return jsonify([dict(r) for r in db.get_friends(me_id)])


@app.route('/api/friends/<int:friend_id>', methods=['DELETE'])
@login_required
def delete_friend(friend_id):
    """删除好友。DELETE 方法 = 语义上的"删资源"，跟 GET 拿 / POST 造对着记"""
    me_id = session.get('user_id')
    if friend_id == me_id:
        return jsonify({'error': '不能删自己'}), 400
    if not db.are_friends(me_id, friend_id):
        return jsonify({'error': '你们不是好友'}), 400
    db.remove_friend(me_id, friend_id)
    return jsonify({'ok': True})

@app.route('/api/users/search', methods=['GET'])
@login_required
def search_users_route():
    """按用户名搜人（添加好友用）。查询参数 ?q=关键词"""
    me_id = session.get('user_id')
    keyword = (request.args.get('q') or '').strip()
    if not keyword:
        return jsonify([])      # 空关键词不搜，直接回空列表
    rows = db.search_users(keyword, me_id)
    return jsonify([dict(row) for row in rows])


db.init_db()   # 挪出来：python app.py 和 gunicorn 都能触发

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)
