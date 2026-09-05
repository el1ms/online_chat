// ===== 0. 工具：把页面上的元素抓到手里 =====
const messagesBox = document.getElementById('messages');
const sendForm = document.getElementById('send-form');
const contentInput = document.getElementById('content');
const whoami = document.getElementById('whoami');
const btnLogin = document.getElementById('btn-login');
const btnRegister = document.getElementById('btn-register');
const modal = document.getElementById('auth-modal');
const modalTitle = document.getElementById('modal-title');
const authUsername = document.getElementById('auth-username');
const authPassword = document.getElementById('auth-password');
const authSubmit = document.getElementById('auth-submit');
const authCancel = document.getElementById('auth-cancel');
const sendBtn = document.getElementById('send-btn');
const userList =document.getElementById('user-list');
const btnFriends = document.getElementById('btn-friends');
const friendBadge = document.getElementById('friend-badge');
const friendsModal = document.getElementById('friends-modal');
const friendsClose = document.getElementById('friends-close');
const friendRequestsBox = document.getElementById('friend-requests');
const friendListBox = document.getElementById('friend-list');
const addFriendListBox = document.getElementById('add-friend-list');
const friendSearchInput = document.getElementById('friend-search');
const btnSearch = document.getElementById('btn-search');


let currentUser = null;
let myFriendIds = [];
let outgoingIds = [];


// ===== 1. 画一条消息 =====
function renderMessage(msg, prepend){
    const div = document.createElement('div');
    div.className = 'message';

    const name = document.createElement('span');
    name.className = 'message-name';
    name.textContent = msg.username;      // textContent：只当纯文本，不当HTML

    const time = document.createElement('span');
    time.className = 'message-time';
    time.textContent = msg.created_at;

    const text = document.createElement('div');
    text.className = 'message-text';
    text.textContent = msg.content;

    div.appendChild(name);
    div.appendChild(time);
    div.appendChild(text);
    if (prepend) {
        messagesBox.insertBefore(div, messagesBox.firstChild);
    } else {
        messagesBox.appendChild(div);
    }
}


// ===== 2. 拉最新消息，刷新整个消息区 =====
async function loadMessages(){
    const resp = await fetch('/api/messages');
    const messages = await resp.json();

    messagesBox.innerHTML = '';
    for (const msg of messages) {
        renderMessage(msg);
    }
    // 新增②：书签 = 画面里最早一条（后端返回时间正序，第一条就是最早的）
    if (messages.length > 0) {
        earliestId = messages[0].id;                  // 最早一条（上滑历史用）
        lastId = messages[messages.length - 1].id;    // 最新一条（增量轮询用）← 新增
    }
    messagesBox.scrollTop = messagesBox.scrollHeight;   // 自动滚到最底
}


// ===== 3. 发消息 =====
sendForm.addEventListener('submit', async function (event){
    event.preventDefault();               // 掐断表单默认的"整页跳转"，改走fetch


    const content = contentInput.value.trim();
    if (!content) {
        alert('消息不能为空');
        return;
    }

    const resp = await fetch('/api/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: content })
    });

    if (resp.status === 201) {
        contentInput.value = '';          // 清空输入框
        loadNew();          // 原 loadMessages() → 改增量，不再整屏重画
        startCooldown();                  // 启动 5 秒倒计时（按钮变灰）
    } else {
        const data = await resp.json();
        alert(data.error);                // 后端400的error信息显示给用户
    }
})


// ===== 4. 冷却倒计时（挡君子：按钮变灰 + 数字倒数） =====
let cooldownLeft = 0;          // 剩余秒数

function startCooldown() {
    cooldownLeft = 5;          // 从 5 开始倒
    sendBtn.disabled = true;   // 按钮变灰，点不动
    sendBtn.textContent = `请等待 ${cooldownLeft} 秒`;   // 按钮上显示倒数

    const timer = setInterval(function () {
        cooldownLeft--;
        if (cooldownLeft <= 0) {
            clearInterval(timer);          // 倒计时结束，停表
            sendBtn.disabled = false;      // 按钮恢复可点
            sendBtn.textContent = `发送`;  // 按钮文字还原
        } else {
            sendBtn.textContent = `请等待 ${cooldownLeft} 秒`;
        }
    }, 1000);   // 每 1000 毫秒（=1秒）跳一下
}


// ===== 4.5 上滑加载历史（游标分页前端） =====
let earliestId = null;   // 书签：画面最早一条（上滑历史用）
let lastId = null;       // 书签：画面最新一条（增量轮询用）← 新增
let loadingHistory = false;  // 正在拉？防抖
let noMore = false;          // 历史拉光了？

async function loadHistory() {
    if (loadingHistory || noMore || earliestId === null) return;
    loadingHistory = true;

    const resp = await fetch('/api/messages?before_id=' + earliestId);
    const older = await resp.json();

    if (older.length === 0) {
        noMore = true;                             // 拉空 = 翻到头了
    } else {
        earliestId = older[0].id;                  // 书签前移
        const oldHeight = messagesBox.scrollHeight;    // 插入前的总高
        for (let i = older.length - 1; i >= 0; i--) {  // 倒序！插队头专用
            renderMessage(older[i], true);
        }
        // 补偿：把长出来的高度补回滚动条，视觉不跳
        messagesBox.scrollTop += messagesBox.scrollHeight - oldHeight;
    }
    loadingHistory = false;
}

// ===== 4.6 轮询增量：只拉比 lastId 新的消息，append 队尾，永不重画 =====
async function loadNew() {
    if (lastId === null) {
        return loadMessages();   // 画面还是空的 → 退化成全量拉（防止永远拉不到第一条）
    }

    const resp = await fetch('/api/messages?after_id=' + lastId);
    const fresh = await resp.json();
    if (fresh.length === 0) return;   // 没新消息，啥也不干

    // 拉之前先看：我现在在底部吗？（决定拉完要不要跟着滚）
    const nearBottom = messagesBox.scrollHeight - messagesBox.scrollTop
                     - messagesBox.clientHeight < 100;

    for (const msg of fresh) {
        renderMessage(msg);          // append 队尾（不带 prepend = 默认 appendChild）
    }
    lastId = fresh[fresh.length - 1].id   // 书签前移

    if (nearBottom) {
        messagesBox.scrollTop = messagesBox.scrollHeight;   // 在底部 → 跟着滚到底
    }
    // 不在底部（正在翻历史）→ 不动，新消息静静躺在下面，不打扰你
}

// 消息区滚到顶 → 自动加载更早的
messagesBox.addEventListener('scroll', function () {
    if (messagesBox.scrollTop === 0) {
        loadHistory();
    }
});


// ===== 5. 登录 / 注册 / 登出 =====
let authMode = 'login';            // 当前弹窗是"登录"还是"注册"

function showModal(mode){
    authMode = mode;
    modalTitle.textContent = (mode === 'login') ? '登录' : '注册';
    authUsername.value = '';
    authPassword.value = '';
    modal.classList.remove('hidden');
}

function hideModal(){
    modal.classList.add('hidden');
}

btnLogin.addEventListener('click', () => showModal('login'));
btnRegister.addEventListener('click', () => showModal('register'));
authCancel.addEventListener('click', hideModal);

authSubmit.addEventListener('click', async function (){
    const username = authUsername.value.trim();
    const password = authPassword.value;

    const url = (authMode === 'login') ? '/api/login' : '/api/register';
    const resp = await fetch(url,{
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username, password: password })
    });

    if (resp.ok) {
        hideModal();
        refreshUser();              // 重新读"我是谁"
    } else {
        const data = await resp.json();
        alert(data.error);
    }
});


async function refreshUser() {
    const resp = await fetch('/api/me');
    const me = await resp.json();
    if (me) {
        whoami.textContent = '😊 ' + me.username;
        // 登录后显示登出按钮，藏起登录/注册
        btnLogin.style.display = 'none';
        btnRegister.style.display = 'none';
        document.getElementById('btn-logout').style.display = 'inline';
        currentUser = me;
        btnFriends.style.display = 'inline';
        updateFriendBadge();
        loadUsers();               // ← 登录成功，拉好友列表
    } else {
        whoami.textContent = '未登录';
        btnLogin.style.display = 'inline';
        btnRegister.style.display = 'inline';
        document.getElementById('btn-logout').style.display = 'none';
        currentUser = null;
        btnFriends.style.display = 'none';
        friendsModal.classList.add('hidden');
        userList.innerHTML = '';   // ← 登出，清空列表
    }
}

document.getElementById('btn-logout').addEventListener('click', async function () {
    await fetch('/api/logout', { method: 'POST'});
    refreshUser();
});

refreshUser();   // 页面一打开先问一句"我是谁"


// 渲染用户列表
async function loadUsers() {
    const resp = await fetch('/api/users');
    const users = await resp.json();

    userList.innerHTML = '';
    for (const u of users) {
        const chip = document.createElement('span');
        chip.className = 'user-chip';
        chip.textContent = u.username;
        chip.dataset.id = u.id;          // 把 id 藏进 data 属性，点击时读
        chip.addEventListener('click', function () {
            // 选中高亮（真正私聊在后面课接入）
            document.querySelectorAll('.user-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
        });
        userList.appendChild(chip);
    }
}


// ===== 主题切换：一键换肤 + localStorage 记住选择 =====
const btnTheme = document.getElementById('btn-theme');

function applyTheme(theme) {
    document.body.className = theme;                    // 切换 body 的 class = 换肤
    localStorage.setItem('theme', theme);                // 写便签：记住这次的选择
    btnTheme.textContent = (theme === 'dark') ? '☀️ 白天' : '🌙 黑夜';   // 按钮显示"下一步去哪"
}

btnTheme.addEventListener('click', function () {
    const isDark = document.body.classList.contains('dark');
    applyTheme(isDark ? 'light' : 'dark');
});

// 页面加载：先读便签本，有记录就恢复上次的皮肤，没有就用默认白天
const savedTheme = localStorage.getItem('theme') || 'light';
applyTheme(savedTheme);



// ===== 6. 轮询：页面打开先拉一次，之后每2秒拉一次 =====
loadMessages();               // 页面打开：首载一次（全量）
setInterval(loadNew, 2000);   // 之后每 2 秒：只补新增（原 setInterval(loadMessages, ...)）


// ===== 7. 好友系统：申请 → 验证通过 → 好友 =====

// 打开 / 关闭好友弹窗
btnFriends.addEventListener('click', function () {
    friendsModal.classList.remove('hidden');
    loadFriendsPanel();
});
friendsClose.addEventListener('click', function () {
    friendsModal.classList.add('hidden');
})

// 弹窗三块一起刷（有先后：先拿申请和好友，"添加好友"才知道谁该藏谁该灰）
async function loadFriendsPanel() {
    await loadFriendRequests();   //  记下 outgoingIds
    await loadFriendList();      //  记下 outgoingIds
    friendSearchInput.value = '';
    addFriendListBox.innerHTML = '<span class="muted">输入用户名搜索，回车或点搜索按钮</span>';
}

// ① 待处理申请（发给我的，带"通过/拒绝"按钮）
async function loadFriendRequests() {
    const resp = await fetch('/api/friend_requests');
    if (!resp.ok) return;
    const data = await resp.json();   // {incoming: 发给我的, outgoing: 我发出的}

    outgoingIds = data.outgoing.map(r => r.to_user_id);   // 记下我申请过谁

    friendRequestsBox.innerHTML = '';
    if (data.incoming.length === 0) {
        friendRequestsBox.innerHTML = '<span class="muted">暂无申请</span>';
        updateFriendBadge(0);
        return;
    }
    for (const r of data.incoming) {
        const row = document.createElement('div');
        row.className = 'friend-row';

        const label = document.createElement('span');
        label.textContent = r.username + ' 申请加你为好友';

        const btns = document.createElement('span');
        const btnAccept = document.createElement('button');
        btnAccept.className = 'btn-mini btn-accept';
        btnAccept.textContent = '通过';
        btnAccept.addEventListener('click', () => resolveRequest(r.id, 'accept'));

        const btnReject = document.createElement('button');
        btnReject.className = 'btn-mini btn-reject';
        btnReject.textContent = '拒绝';
        btnReject.addEventListener('click', () => resolveRequest(r.id, 'reject'));

        btns.appendChild(btnAccept);
        btns.appendChild(btnReject);
        row.appendChild(label);
        row.appendChild(btns);
        friendRequestsBox.appendChild(row);
    }
    updateFriendBadge(data.incoming.length);   // 顺手刷新红点
}

// 通过 / 拒绝（action = 'accept' 或 'reject'）
async function resolveRequest(requestId, action) {
    const resp = await fetch('/api/friend_requests/' + requestId + '/' + action, { method: 'POST'});
    if (resp.ok) {
        loadFriendsPanel();   // 三块全刷（通过后对方立刻出现在好友列表里）
    } else {
        const data = await resp.json();
        alert(data.error);
    }
}

// ② 我的好友（通过了验证的人）
async function loadFriendList() {
    const resp = await fetch('/api/friends');
    if (!resp.ok) return;
    const friends = await resp.json();

    myFriendIds = friends.map(f => f.id);   // 记下编号，给"添加好友"过滤用

    friendListBox.innerHTML = '';
    if (friends.length === 0) {
        friendListBox.innerHTML = '<span class="muted">还没有好友，去下面加一个</span>';
        return;
    }
    for (const f of friends) {
        const row = document.createElement('div');
        row.className = 'friend-row';

        const name = document.createElement('span');
        name.textContent = f.username;

        const btnDel = document.createElement('button');
        btnDel.className = 'btn-mini btn-reject';
        btnDel.textContent = '✕';
        btnDel.addEventListener('click', async function () {
            // confirm = 浏览器自带的确认弹窗，点取消返回 false
            if (!confirm('确定删除好友' + f.username + '吗')) return;
            const r = await fetch('/api/friends/' + f.id, { method: 'DELETE' });
            if (r.ok) {
                loadFriendsPanel();          // 删完三块全刷
            } else {
                const d =await r.json();
                alert(d.error);
            }
        });

        row.appendChild(name);
        row.appendChild(btnDel);
        friendListBox.appendChild(row);
    }
}

// ③ 添加好友（搜索版：输用户名 → 回车/点按钮 → 后端搜，最多画 20 条）
async function searchUsers() {
    const keyword = friendSearchInput.value.trim();
    if (!keyword) return;              // 空关键词不搜

    const resp = await fetch('/api/users/search?q=' + encodeURIComponent(keyword));
    if (!resp.ok) return;
    const users = await resp.json();

    addFriendListBox.innerHTML = '';
    if (users.length === 0) {
        addFriendListBox.innerHTML = '<span class="muted">没找到这个人</span>';
        return;
    }
    for (const u of users) {
        const row = document.createElement('div');
        row.className = 'friend-row';

        const name = document.createElement('span');
        name.textContent = u.username;

        const btn = document.createElement('button');
        if (myFriendIds.includes(u.id)) {
            btn.className = 'btn-mini';
            btn.textContent = '已好友';
            btn.disabled = true;
        } else if (outgoingIds.includes(u.id)) {
            btn.className = 'btn-mini';
            btn.textContent = '已申请';
            btn.disabled = true;
        } else {
            btn.className = 'btn-mini btn-accept';
            btn.textContent = '加好友';
            btn.addEventListener('click', async function () {
                const r = await fetch('/api/friend_requests', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ to_user_id: u.id })
                });
                if (r.ok) {
                    loadFriendsPanel();
                } else {
                    const d = await r.json();
                    alert(d.error);
                }
            });
        }

        row.appendChild(name);
        row.appendChild(btn);
        addFriendListBox.appendChild(row);
    }
}

// 搜索的两个触发方式：点按钮、按回车
btnSearch.addEventListener('click', searchUsers);
friendSearchInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') searchUsers();
});

// 红点：有人申请加我时亮。传了 count 直接用，没传就去后端查
async function updateFriendBadge(count) {
    if (count === undefined) {
        if (currentUser === null) {          // 游客不查（会 401）
            friendBadge.style.display = 'none';
            return;
        }
        const resp = await fetch('/api/friend_requests');
        if (!resp.ok) return;
        const data = await resp.json();
        count = data.incoming.length;
    }
    friendBadge.style.display = (count > 0) ? 'inline-block' : 'none';
}

// 每 5 秒查一次红点（别人申请加你，不开弹窗也能看到提醒）
setInterval(updateFriendBadge, 5000);