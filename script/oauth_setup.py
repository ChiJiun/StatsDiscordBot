import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

def get_oauth_creds():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # 固定 port=8080，授權 URI 在 GCP Console 裡只要加 http://localhost:8080/
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            # 添加 prompt='consent' 以確保獲取 refresh_token
            creds = flow.run_local_server(
                port=8080,                 # 你註解說固定 8080，就真的固定
                access_type="offline",     # ✅ 關鍵：拿 refresh_token
                prompt="consent"           # ✅ 強制再次同意，避免 Google 不發 refresh_token
            )
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

if __name__ == "__main__":
    print("🔐 開始 OAuth2 授權流程...")
    creds = get_oauth_creds()
    print("✅ OAuth2 授權完成，token.json 已保存")
