import os
import re
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from config import UPLOADS_FOLDER_ID, REPORTS_FOLDER_ID, UPLOADS_DIR, REPORTS_DIR
from report_generator import generate_html_report

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_oauth_creds():
    """讀取現有的 token.json,並在過期時自動刷新"""
    creds = None
    token_updated = False
    
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                token_updated = True
                print("✅ Token 已自動刷新")
            except Exception as e:
                print(f"❌ Token 刷新失敗: {e}")
                raise
        
        # 保存刷新後的 token
        if token_updated:
            with open("token.json", "w") as token_file:
                token_file.write(creds.to_json())
                print("✅ 已保存更新的 token 到 token.json")
    else:
        raise FileNotFoundError("❌ token.json 不存在,請先運行 oauth_setup.py 獲取授權")
    
    return creds


class FileHandler:
    def __init__(self):
        self.drive_service = None
        self._init_drive_service()

    def _init_drive_service(self):
        """初始化 Google Drive 服務（OAuth2 Flow）"""
        try:
            creds = get_oauth_creds()
            self.drive_service = build("drive", "v3", credentials=creds)
            print("✅ Google Drive 服務初始化成功")
        except Exception as e:
            print(f"❌ Google Drive 服務初始化失敗: {e}")
            self.drive_service = None

    def get_or_create_folder(self, folder_name, parent_id):
        """獲取或創建資料夾，返回資料夾 ID"""
        if not self.drive_service:
            return None

        try:
            # 搜尋現有資料夾
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
            results = self.drive_service.files().list(q=query, fields="files(id, name)").execute()
            items = results.get("files", [])

            if items:
                return items[0]["id"]
            else:
                # 創建新資料夾
                file_metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
                folder = self.drive_service.files().create(body=file_metadata, fields="id").execute()
                return folder.get("id")
        except Exception as e:
            print(f"❌ 獲取或創建資料夾失敗: {e}")
            return None

    async def upload_to_drive(self, file_path, filename, class_name, student_id, base_folder_id):
        """上傳檔案到 Google Drive，支援 /班級/學號/ 結構"""
        if not self.drive_service:
            print("❌ Google Drive 服務未初始化")
            return None

        try:
            # 創建或獲取班級資料夾
            class_folder_id = self.get_or_create_folder(class_name, base_folder_id)
            if not class_folder_id:
                return None

            # 創建或獲取學號資料夾
            student_folder_id = self.get_or_create_folder(student_id, class_folder_id)
            if not student_folder_id:
                return None

            # 上傳檔案到學號資料夾
            file_metadata = {"name": filename, "parents": [student_folder_id]}

            with open(file_path, "rb") as f:
                media = MediaIoBaseUpload(f, mimetype="text/html", resumable=True)
                file = self.drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()

            print(f"✅ 檔案已上傳到 Google Drive: /{class_name}/{student_id}/{filename}")
            return file.get("id")
        except Exception as e:
            print(f"❌ 上傳到 Google Drive 失敗: {e}")
            return None

    @staticmethod
    def get_safe_filename(text):
        """生成安全的檔案名稱"""
        # 移除或替換不安全的字元
        safe_text = re.sub(r'[<>:"/\\|?*]', "_", text)
        # 限制長度
        if len(safe_text) > 100:
            safe_text = safe_text[:100]
        return safe_text

    @staticmethod
    async def save_upload_file(file, user_id, uploads_student_dir, filename, class_name, student_id, db_student_name, question_title, attempt_number):
        """保存上傳檔案到本地，然後上傳到 Google Drive"""
        try:
            # 確保本地目錄存在
            os.makedirs(uploads_student_dir, exist_ok=True)

            # 生成新的檔案名稱：學號_班級_姓名_標題_次數
            new_filename = f"{student_id}_{class_name}_{db_student_name}_{question_title}_第{attempt_number}次.html"
            local_path = os.path.join(uploads_student_dir, new_filename)

            # 保存到本地
            await file.save(local_path)
            print(f"✅ 檔案已保存到本地: {local_path}")

            # 上傳到 Google Drive（名稱與本地一致）
            drive_id = await FileHandler().upload_to_drive(local_path, new_filename, class_name, student_id, UPLOADS_FOLDER_ID)
            return local_path, drive_id
        except Exception as e:
            print(f"❌ 檔案保存失敗: {e}")
            return None, None

    @staticmethod
    async def process_html_file(message, file, user_id, class_name, student_id, db_student_name, question_title, attempt_number):
        """處理 HTML 檔案的上傳和保存"""
        try:
            # 確保本地目錄存在
            os.makedirs(UPLOADS_DIR, exist_ok=True)

            # 生成新的檔案名稱：學號_班級_姓名_標題_次數
            new_filename = f"{student_id}_{class_name}_{db_student_name}_{question_title}_第{attempt_number}次.html"
            local_path = os.path.join(UPLOADS_DIR, new_filename)

            # 保存到本地
            await file.save(local_path)

            # 上傳到 Google Drive
            drive_id = await FileHandler().upload_to_drive(local_path, new_filename, class_name, student_id, UPLOADS_FOLDER_ID)

            return local_path, new_filename, drive_id
        except Exception as e:
            print(f"❌ 檔案保存失敗: {e}")
            return None, None, None

    @staticmethod
    async def generate_and_save_report(
        db_student_name,
        student_number,
        student_id_from_html,
        question_title,
        attempt_number,
        answer_text,
        eng_score,
        eng_band,
        eng_feedback_clean,
        stats_score,
        stats_band,
        stats_feedback_clean,
        reports_student_dir,
        class_name,
        student_id,
    ):
        """生成並保存 HTML 報告到本地和 Google Drive"""
        try:
            # 生成 HTML 報告
            html_report = generate_html_report(
                student_name=db_student_name,
                student_id=student_number or student_id_from_html,
                question_number=question_title,
                attempt=attempt_number,
                answer_text=answer_text,
                eng_score=eng_score,
                eng_band=eng_band,
                eng_feedback=eng_feedback_clean,
                stats_score=stats_score,
                stats_band=stats_band,
                stats_feedback=stats_feedback_clean,
            )

            # 保存報告檔案到本地（學號_姓名_標題_次數）
            report_filename = f"{student_number or student_id_from_html}_{db_student_name}_{question_title}_第{attempt_number}次.html"
            local_path = os.path.join(reports_student_dir, report_filename)

            with open(local_path, "w", encoding="utf-8") as f:
                f.write(html_report)

            print(f"✅ 報告已保存到本地: {local_path}")

            # 上傳到 Google Drive
            drive_id = await FileHandler().upload_to_drive(local_path, report_filename, class_name, student_id, REPORTS_FOLDER_ID)

            return local_path, report_filename, drive_id
        except Exception as e:
            print(f"❌ 生成或保存報告失敗: {e}")
            return None, None, None
