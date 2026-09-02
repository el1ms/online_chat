import os

# 配置中心：全项目的"设置面板"，以后所有开关集中在这里
class Config:
    # session 的签名钥匙：上线时从环境变量读，本地开发用后备值
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-上线前换掉')

    # 数据库文件路径：跟着项目文件夹走，不写死盘符（行业惯例）
    DB_FILE = os.path.join(os.path.dirname(__file__), 'chat.db')

    # 业务规则：单条消息最长 200 字——前端会拦，后端也必须拦
    MAX_MESSAGE_LEN = 200

    # 冷却时间（秒）：同一个人两条消息之间至少隔这么久
    COOLDOWN_SECONDS = 5