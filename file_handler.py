import os
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
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
    # 類別層級的執行緒池（用於 Google Drive 操作）
    _executor = ThreadPoolExecutor(max_workers=3)
    
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

    def _get_or_create_folder_sync(self, folder_name, parent_id):
        """同步版本：獲取或創建資料夾（在執行緒池中執行）"""
        if not self.drive_service:
            return None

        try:
            # 搜尋現有資料夾
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
            results = self.drive_service.files().list(q=query, fields="files(id, name)").execute()
            items = results.get("files", [])

            if items:
                print(f"📁 找到現有資料夾: {folder_name}")
                return items[0]["id"]
            else:
                # 創建新資料夾
                file_metadata = {
                    "name": folder_name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id]
                }
                folder = self.drive_service.files().create(body=file_metadata, fields="id").execute()
                print(f"📁 已創建新資料夾: {folder_name}")
                return folder.get("id")
        except Exception as e:
            print(f"❌ 獲取或創建資料夾失敗: {e}")
            return None

    async def get_or_create_folder(self, folder_name, parent_id):
        """非同步版本：獲取或創建資料夾"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._get_or_create_folder_sync,
            folder_name,
            parent_id
        )

    def _upload_to_drive_sync(self, file_path, filename, question_title, class_name, student_id, base_folder_id):
        """同步版本：上傳檔案到 Google Drive（在執行緒池中執行）"""
        if not self.drive_service:
            print("❌ Google Drive 服務未初始化")
            return None

        try:
            # 1. 創建或獲取題目資料夾（第一層）
            question_folder_id = self._get_or_create_folder_sync(question_title, base_folder_id)
            if not question_folder_id:
                return None

            # 2. 創建或獲取班級資料夾（第二層）
            class_folder_id = self._get_or_create_folder_sync(class_name, question_folder_id)
            if not class_folder_id:
                return None

            # 3. 創建或獲取學號資料夾（第三層）
            student_folder_id = self._get_or_create_folder_sync(student_id, class_folder_id)
            if not student_folder_id:
                return None

            # 4. 上傳檔案到學號資料夾
            file_metadata = {"name": filename, "parents": [student_folder_id]}

            media = MediaFileUpload(file_path, mimetype="text/html", resumable=True)
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id"
            ).execute()

            file_id = file.get("id")
            print(f"✅ 檔案已上傳到 Google Drive: /{question_title}/{class_name}/{student_id}/{filename}")
            return file_id
        except Exception as e:
            print(f"❌ 上傳到 Google Drive 失敗: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def upload_to_drive(self, file_path, filename, question_title, class_name, student_id, is_report=False):
        """
        上傳檔案到 Google Drive
        
        Args:
            file_path: 本地檔案路徑
            filename: 檔案名稱
            question_title: 題目標題
            class_name: 班級名稱
            student_id: 學號
            is_report: 是否為報告檔案 (預設 False)
        
        Returns:
            str: 上傳後的檔案 ID
        """
        loop = asyncio.get_event_loop()
        
        try:
            # 在執行緒池中執行同步上傳
            file_id = await loop.run_in_executor(
                self._executor,
                self._upload_to_drive_sync,
                file_path,
                filename,
                question_title,
                class_name,
                student_id,
                REPORTS_FOLDER_ID
            )
            
            file_type = "報告" if is_report else "作業檔案"
            print(f"✅ {file_type}已上傳到 Google Drive: {file_id}")
            return file_id
            
        except Exception as e:
            file_type = "報告" if is_report else "作業檔案"
            print(f"❌ 上傳{file_type}到 Google Drive 失敗: {e}")
            raise

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
    async def save_upload_file(file, user_id, uploads_student_dir, filename, question_title, class_name, student_id, db_student_name, attempt_number):
        """保存上傳檔案到本地，然後上傳到 Google Drive"""
        try:
            # ✅ 修改：建立與雲端相同的目錄結構
            # UPLOADS_DIR / question_title / class_name / student_id
            safe_question = FileHandler.get_safe_filename(question_title)
            question_dir = os.path.join(UPLOADS_DIR, safe_question)
            class_dir = os.path.join(question_dir, class_name)
            uploads_student_dir = os.path.join(class_dir, student_id)
            
            # 確保本地目錄存在（包含題目和班級層級）
            os.makedirs(uploads_student_dir, exist_ok=True)

            # 生成新的檔案名稱：學號_班級_姓名_標題_次數
            new_filename = f"{student_id}_{class_name}_{db_student_name}_{safe_question}_第{attempt_number}次.html"
            local_path = os.path.join(uploads_student_dir, new_filename)

            # 保存到本地
            await file.save(local_path)
            print(f"✅ 檔案已保存到本地: {local_path}")

            # 上傳到 Google Drive（非同步）
            handler = FileHandler()
            drive_id = await handler.upload_to_drive(
                local_path,
                new_filename,
                question_title,  # ✅ 添加 question_title 參數
                class_name,
                student_id,
                UPLOADS_FOLDER_ID
            )
            
            return local_path, drive_id
        except Exception as e:
            print(f"❌ 檔案保存失敗: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    @staticmethod
    async def generate_and_save_report(
        db_student_name,
        student_number,
        student_id_from_html,
        question_title,
        attempt_number,
        answer_text,
        eng_feedback_clean,
        stats_feedback_clean,
        reports_student_dir,
        class_name,
        student_id,
    ):
        """生成並保存 HTML 報告到本地和 Google Drive"""
        try:
            # 確保本地目錄存在
            os.makedirs(reports_student_dir, exist_ok=True)

            # 生成 HTML 報告（在執行緒池中執行，避免阻塞）
            loop = asyncio.get_event_loop()
            html_report = await loop.run_in_executor(
                FileHandler._executor,
                generate_html_report,
                db_student_name,
                student_number or student_id_from_html,
                question_title,
                attempt_number,
                answer_text,
                eng_feedback_clean,
                stats_feedback_clean,
            )

            # 保存報告檔案到本地
            safe_question = FileHandler.get_safe_filename(question_title)
            report_filename = f"{student_number or student_id_from_html}_{db_student_name}_{safe_question}_第{attempt_number}次.html"
            local_path = os.path.join(reports_student_dir, report_filename)

            # 寫入檔案（非同步）
            def write_file():
                with open(local_path, "w", encoding="utf-8") as f:
                    f.write(html_report)
                return local_path

            local_path = await loop.run_in_executor(FileHandler._executor, write_file)
            print(f"✅ 報告已保存到本地: {local_path}")

            # 上傳到 Google Drive（非同步）
            handler = FileHandler()
            drive_id = await handler.upload_to_drive(
                local_path,
                report_filename,
                question_title,
                class_name,
                student_id,
                is_report=True
            )

            return local_path, report_filename, drive_id
        except Exception as e:
            print(f"❌ 生成或保存報告失敗: {e}")
            import traceback
            traceback.print_exc()
            return None, None, None

    @staticmethod
    async def download_attachment(attachment):
        """下載 Discord 附件到臨時檔案"""
        try:
            temp_path = os.path.join(UPLOADS_DIR, f"temp_{attachment.filename}")
            await attachment.save(temp_path)
            return temp_path
        except Exception as e:
            print(f"❌ 下載附件失敗: {e}")
            return None
