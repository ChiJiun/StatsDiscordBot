import os
from dotenv import load_dotenv

# 載入環境變數檔案
load_dotenv()

# Discord 和 OpenAI 設定
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = "gpt-4o-mini"

# Google Drive 設定（OAuth2）
UPLOADS_FOLDER_ID = os.getenv("UPLOADS_FOLDER_ID")
REPORTS_FOLDER_ID = os.getenv("REPORTS_FOLDER_ID")

# 檔案路徑設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# 確保目錄存在
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# Discord 頻道設定
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", 0))  # 歡迎頻道 ID
NCUFN_CHANNEL_ID = int(os.getenv("NCUFN_CHANNEL_ID", 0))  # 中央財金系頻道 ID
NCUEC_CHANNEL_ID = int(os.getenv("NCUEC_CHANNEL_ID", 0))  # 中央經濟系頻道 ID
CYCUIUBM_CHANNEL_ID = int(os.getenv("CYCUIUBM_CHANNEL_ID", 0))  # 中原國商頻道 ID

# 管理員通知設定
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID", 0))  # 管理員通知頻道 ID
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", 0))  # 管理員身分組 ID（用於提及）

# Discord 身分組設定
NCUFN_ROLE_NAME = "NCUFN"  # 中央大學財金系
NCUEC_ROLE_NAME = "NCUEC"  # 中央大學經濟系
CYCUIUBM_ROLE_NAME = "CYCUIUBM"  # 中原大學國際商學學士學位學程

# 可選：如果您有特定的身分組 ID，可以在這裡設定
NCUFN_ROLE_ID = int(os.getenv("NCUFN_ROLE_ID", 0))  # 可選：NCUFN 身分組 ID
NCUEC_ROLE_ID = int(os.getenv("NCUEC_ROLE_ID", 0))  # 可選：NCUEC 身分組 ID
CYCUIUBM_ROLE_ID = int(os.getenv("CYCUIUBM_ROLE_ID", 0))  # 可選：CYCUIUBM 身分組 ID

# 資料庫設定
DB_PATH = "homework.db"

# 目錄設定
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")

# 特定題目的 Prompt 檔案路徑配置（必須是字典格式，包含 english 和 statistics）
SPECIFIC_PROMPTS = {
    "Age and Viewing Habits 考卷": {
        "english": os.path.join(PROMPTS_DIR, "Eng_prompt.txt"),
        "statistics": os.path.join(PROMPTS_DIR, "Stats_prompt.txt")
    },
    "Typing Practice": {
        "english": os.path.join(PROMPTS_DIR, "Eng_prompt.txt"),
        "statistics": os.path.join(PROMPTS_DIR, "Typing Practice.txt")
    },
    "SOCS_S-M ratio": {
        "english": os.path.join(PROMPTS_DIR, "Eng_prompt.txt"),
        "statistics": os.path.join(PROMPTS_DIR, "S-M ratio.txt")
    },
    "SOCS_S-M ratio-2": {
        "english": os.path.join(PROMPTS_DIR, "Eng_prompt.txt"),
        "statistics": os.path.join(PROMPTS_DIR, "S-M ratio.txt")
    },
    "Four-Step_Simulation of random guessing": {
        "english": os.path.join(PROMPTS_DIR, "Eng_prompt.txt"),
        "statistics": os.path.join(PROMPTS_DIR, "Four-Step_Simulation.txt")
    },
    "Four-Step_Proportion_App or in-store": {
        "english": os.path.join(PROMPTS_DIR, "Eng_prompt.txt"),
        "statistics": os.path.join(PROMPTS_DIR, "Four-Step_Proportion.txt")
    }
}


def get_safe_filename(text):
    """將文字轉換為安全的檔案/資料夾名稱"""
    unsafe_chars = ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]
    safe_text = text
    for char in unsafe_chars:
        safe_text = safe_text.replace(char, "_")
    return safe_text


def get_student_upload_path(class_name, student_id, filename):
    """取得學生上傳檔案的完整路徑"""
    safe_class_name = get_safe_filename(class_name)
    upload_dir = os.path.join(UPLOADS_DIR, safe_class_name, str(student_id))
    os.makedirs(upload_dir, exist_ok=True)
    return os.path.join(upload_dir, filename)


def get_student_report_path(class_name, student_id, filename):
    """取得學生報告檔案的完整路徑"""
    safe_class_name = get_safe_filename(class_name)
    report_dir = os.path.join(REPORTS_DIR, safe_class_name, str(student_id))
    os.makedirs(report_dir, exist_ok=True)
    return os.path.join(report_dir, filename)
