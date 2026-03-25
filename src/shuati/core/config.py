import os

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CORE_DIR, "..", "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
DB_PATH = os.path.join(DATA_DIR, "questions.db")
TOKEN_PATH = os.path.join(DATA_DIR, "token.json")

# 接龙管家 API
JIELONG_API_BASE = "https://i-api.jielong.com/api"
JIELONG_WEB_BASE = "https://i.jielong.com"

# 固定请求头（除 authorization 外）
BASE_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "origin": "https://i.jielong.com",
    "referer": "https://i.jielong.com/",
    "x-api-request-mode": "cors",
    "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Mobile Safari/537.36",
}

# Flask
FLASK_PORT = 8080
FLASK_SECRET = "math-collector-secret-2026"

# 定时采集（24小时制，每天几点跑）
SYNC_HOUR = 7
SYNC_MINUTE = 0

# 收藏列表 listType
FAVORITE_LIST_TYPE = 5
PAGE_SIZE = 50
