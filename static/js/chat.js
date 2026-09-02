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

    // 新增①：用户离底部超过 100px（正在翻历史）→ 这次轮询不打扰
    const nearBottom = messagesBox.scrollHeight - messagesBox.scrollTop
                     - messagesBox.clientHeight < 100;
    if (!nearBottom) return;

    messagesBox.innerHTML = '';
    for (const msg of messages) {
        renderMessage(msg);
    }
    // 新增②：书签 = 画面里最早一条（后端返回时间正序，第一条就是最早的）
    if (messages.length > 0) {
        earliestId = messages[0].id;
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
        loadMessages();                   // 立刻刷新
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
let earliestId = null;       // 书签：画面里最早一条消息的 id
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
    } else {
        whoami.textContent = '未登录';
        btnLogin.style.display = 'inline';
        btnRegister.style.display = 'inline';
        document.getElementById('btn-logout').style.display = 'none';
    }
}

document.getElementById('btn-logout').addEventListener('click', async function () {
    await fetch('/api/logout', { method: 'POST'});
    refreshUser();
});

refreshUser();   // 页面一打开先问一句"我是谁"


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
loadMessages();
setInterval(loadMessages, 2000);