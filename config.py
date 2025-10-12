import os
from dotenv import load_dotenv

# 載入環境變數檔案
load_dotenv()

# Discord 和 OpenAI 設定
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = "gpt-4o-mini"

# Discord 頻道設定
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", 0))  # 歡迎頻道 ID

# Discord 身分組設定
NCUFN_ROLE_NAME = "NCUFN"  # 中央大學財金系
NCUEC_ROLE_NAME = "NCUEC"  # 中央大學經濟系
CYCUIUBM_ROLE_NAME = "CYCUIUBM"  # 中原大學國際商學學士學位學程

# 可選：如果您有特定的身分組 ID，可以在這裡設定
NCUFN_ROLE_ID = int(os.getenv("NCUFN_ROLE_ID", 0))  # 可選：NCUFN 身分組 ID
NCUEC_ROLE_ID = int(os.getenv("NCUEC_ROLE_ID", 0))  # 可選：NCUEC 身分組 ID
CYCUIUBM_ROLE_ID = int(os.getenv("CYCUIUBM_ROLE_ID", 0))  # 可選：CYCUIUBM 身分組 ID

# 向後相容的舊身分組名稱（如果其他地方還在使用）
STUDENT_ROLE_NAME = "學生"
TEACHER_ROLE_NAME = "教師"

# 資料庫設定
DB_PATH = "homework.db"

# 目錄設定
UPLOADS_DIR = "uploads"
REPORTS_DIR = "reports"
PROMPTS_DIR = "."  # 提示檔案存放目錄

# Grading 系統設定
ENG_PROMPT_FILE = os.path.join(PROMPTS_DIR, "Eng_prompt.txt")
STATS_PROMPT_FILE = os.path.join(PROMPTS_DIR, "Stats_prompt.txt")  # 預設統計 prompt
PROMPT_MAPPING_FILE = os.path.join(PROMPTS_DIR, "prompt.json")  # Prompt 映射檔案

# 預設 Prompt 檔案路徑配置
DEFAULT_PROMPTS = {"eng": ENG_PROMPT_FILE, "stats": STATS_PROMPT_FILE}

# 特定 Prompt 檔案路徑配置（根據您的 prompt.json）
SPECIFIC_PROMPTS = {
    "Age and Viewing Habits 考卷": os.path.join(PROMPTS_DIR, "Stats_prompt.txt"),
    "Typing Practice": os.path.join(PROMPTS_DIR, "prompts/Typing Practice.txt"),
    "SOCS_S-M ratio": os.path.join(PROMPTS_DIR, "prompts/S-M ratio_Stats Rubric.txt"),
    "SOCS_S-M ratio-2": os.path.join(PROMPTS_DIR, "prompts/S-M ratio_Stats Rubric.txt"),
}
