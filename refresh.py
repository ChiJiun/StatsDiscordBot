import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

with open("token.json", "r", encoding="utf-8") as f:
    data = json.load(f)

creds = Credentials.from_authorized_user_info(data, SCOPES)

print("refresh_token 存在嗎？", bool(creds.refresh_token))

try:
    creds.refresh(Request())
    print("✅ refresh 成功")
    print("新的 access token 前 20 字:", creds.token[:20])
except Exception as e:
    print("❌ refresh 失敗：", repr(e))