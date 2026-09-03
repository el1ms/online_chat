# 在线聊天室

一个基于 Flask + SQLite 的实时聊天 Web 应用。支持用户注册登录、消息实时同步、5 秒冷却、白天黑夜换肤、手机电脑响应式适配，前后端分离（JSON API），已适配局域网部署。

## 功能

- **用户系统**：密码哈希存储（werkzeug）+ Session 会话保持 + 防用户名探测
- **实时聊天**：轮询同步，双端 2 秒内互通
- **5 秒冷却**：前端倒计时 + 后端 429 限流双保险
- **白天黑夜换肤**：CSS 变量 + localStorage 记忆选择
- **响应式布局**：viewport + @media 手机电脑自适应
- **历史消息**：游标分页，上滑自动加载更早的消息
- **安全防护**：XSS 转义、永不信任前端校验、SECRET_KEY 环境变量注入

## 技术栈

- Python 3.9+ / Flask 3.1
- SQLite（Python 内置，无需额外安装）
- 原生 HTML / CSS / JavaScript（无前端框架）

## 项目结构

```
online_chat/
├── app.py            # 后端路由（页面壳 + JSON API）
├── db.py             # 数据库层（建表 + 增删改查）
├── config.py         # 配置中心（密钥/数据库/限制参数）
├── requirements.txt  # 依赖清单
├── static/
│   ├── css/style.css # 样式（含换肤变量 + 响应式）
│   └── js/chat.js    # 前端逻辑（轮询/冷却/分页）
└── templates/
    └── index.html    # 页面骨架
```

## 快速开始（本地运行）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动（首次运行自动创建 chat.db 数据库）
python app.py
```

浏览器打开 `http://localhost:5000` 即可使用。

> 数据库 `chat.db` 会在首次启动时自动建表，无需手动初始化。

## 部署（局域网：让手机/同 WiFi 设备访问）

**前提**：电脑与手机连接**同一个 WiFi**。

### 1. 配置 SECRET_KEY（生产必须，否则使用默认占位符）

`config.py` 优先读取环境变量，未设置时回落到不安全的默认值。上线前务必换成随机密钥：

**Windows（PowerShell）：**

```powershell
# 生成 64 位随机密钥
python -c "import secrets; print(secrets.token_hex(32))"

# 永久写入系统环境变量（把 xxxx 换成上一步的输出）
setx SECRET_KEY "xxxx"

# 重开一个终端窗口，验证
python -c "import os; print(os.environ.get('SECRET_KEY'))"
```

**Linux / macOS（bash）：**

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

> 换密钥后，所有已登录用户会**全部登出**（session 手环签名失效），这是正常的安全行为。

### 2. 启动服务

```bash
python app.py
```

启动后应看到 `Running on http://0.0.0.0:5000`。其中 `0.0.0.0` 表示对所有网卡开放，局域网内设备可访问；`debug=False` 已关闭调试后门。

### 3. 查询本机局域网 IP

```powershell
ipconfig
```

找到 **"IPv4 地址"**，形如 `192.168.x.x`，这就是你电脑在局域网内的地址。

### 4. 放行防火墙端口（首次运行通常自动弹窗）

首次启动若弹出 Windows 安全中心提示，勾选**专用网络**并允许。若未弹窗或已拒绝，用管理员身份运行：

```powershell
netsh advfirewall firewall add rule name="Flask 5000" dir=in action=allow protocol=TCP localport=5000
```

### 5. 手机访问

手机连同一 WiFi，浏览器输入：

```
http://192.168.x.x:5000
```

（把 `192.168.x.x` 换成第 3 步查到的 IP；注意是 `http` 不是 `https`）

### 排查清单

| 现象 | 原因 | 处理 |
|---|---|---|
| 电脑 `localhost:5000` 打不开 | 服务没启动 | 看终端报错 |
| 电脑能开、手机开不了 | 防火墙拦截 | 回第 4 步放行 |
| 手机显示无法连接 | 手机/电脑不同 WiFi | 确认连同一网络 |
| 以上都对仍不通 | 路由器 AP 隔离 | 关闭路由器的访客网络/设备隔离 |

## 部署到云服务器（公网）

生产环境使用 Gunicorn 作为 WSGI 服务器，Flask 内置服务器仅用于本地开发。

### 前置调整

Gunicorn 以 `import app` 方式加载应用，不会进入 `if __name__ == '__main__'` 分支。需将 `db.init_db()` 提升至模块顶层，确保建表逻辑在两种启动方式下均可执行：

```python
db.init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)
```

### 1. 获取代码

```bash
git clone https://github.com/el1ms/online_chat.git
cd online_chat
```

### 2. 安装依赖

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

### 3. 配置环境变量

```bash
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

生产环境建议通过 systemd 或 `/etc/environment` 持久化。

### 4. 启动服务

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

| 参数 | 说明 |
|---|---|
| `-w 4` | worker 进程数 |
| `-b 0.0.0.0:5000` | 监听地址与端口 |
| `app:app` | 模块 `app.py` 中的 Flask 实例 `app` |

### 5. 放行安全组

在云平台控制台的安全组中，添加入方向规则，放行 TCP 5000 端口。

### 6. 访问

```
http://<公网IP>:5000
```

### 进阶

- **systemd**：托管 Gunicorn 服务，实现开机自启与崩溃自动重启
- **Nginx**：反向代理，承载静态资源与 80/443 端口
- **HTTPS**：通过 Let's Encrypt 签发证书

## 安全说明

- `chat.db`（用户密码哈希 + 聊天记录）已通过 `.gitignore` 排除在版本控制外
- `SECRET_KEY` 存于环境变量，不进入代码仓库
- 上线前已将 `debug=False`，关闭 Werkzeug 调试器后门

## 许可

仅供学习交流使用。
