# ===== 匯入必要的模組 =====
import os  # 作業系統相關操作
import asyncio  # 非同步程式設計
import sqlite3  # SQLite 資料庫操作
import json  # JSON 資料處理
from bs4 import BeautifulSoup  # HTML 解析
import markdown  # Markdown 轉 HTML
import discord  # Discord API
import aiohttp  # 非同步 HTTP 請求
from dotenv import load_dotenv  # 載入環境變數
from datetime import datetime  # 日期時間處理
from fuzzywuzzy import process, fuzz  # 模糊字串比對
from discord.ui import View, Button  # Discord UI 元件
import requests  # HTTP 請求

# ===== Discord Bot 設定 =====


def get_wiki_definition(term):
    """
    從維基百科 API 獲取術語定義

    Args:
        term (str): 要查詢的術語

    Returns:
        str or None: 維基百科的定義文字，若失敗則回傳 None
    """
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{term}"
    try:
        r = requests.get(url, timeout=10)  # 設定 10 秒超時
        if r.status_code == 200:
            data = r.json()
            # 檢查是否為標準頁面（非消歧義或重定向）
            if data.get("type") == "standard":
                extract = data.get("extract")
                # 確保內容有意義且足夠長
                if extract and len(extract.strip()) > 50:
                    return extract
        elif r.status_code == 404:
            print(f"Wikipedia: 找不到 '{term}' 的頁面")
        else:
            print(f"Wikipedia API錯誤: {r.status_code}")
    except requests.RequestException as e:
        print(f"維基百科請求失敗: {e}")
    except Exception as e:
        print(f"維基百科處理錯誤: {e}")
    return None


def add_definition_to_db(cur, keyword, definition, contributor_id=None):
    """
    新增定義到資料庫（避免重複）

    Args:
        cur: 資料庫游標
        keyword (str): 關鍵字
        definition (str): 定義內容
        contributor_id (str): 貢獻者 ID

    Returns:
        bool: 成功新增回傳 True，已存在回傳 False
    """
    # 先檢查關鍵字是否已存在
    cur.execute("SELECT keyword FROM stats_definitions WHERE keyword = ?", (keyword,))
    exists = cur.fetchone()
    if exists:
        return False  # 已存在，不重複新增

    # 新增到資料庫
    cur.execute(
        """
        INSERT INTO stats_definitions (keyword, definition, contributor, search_count)
        VALUES (?, ?, ?, 0)
        """,
        (keyword, definition, contributor_id),
    )
    return True  # 新增成功


# ===== 環境變數載入 =====
load_dotenv()  # 載入 .env 檔案
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")  # Discord 機器人 Token
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # OpenAI API 金鑰
MODEL = "gpt-4o-mini"  # 使用的 OpenAI 模型
MAX_HISTORY = 6  # 保留的對話歷史輪數
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")  # 管理員 Discord ID

# ===== JSON 檔案路徑設定 =====
STUDENTS_DB = "students.json"  # 已批准學生資料
APPLICANTS_DB = "applicants.json"  # 申請中學生資料


# ===== 學生資料管理函數 =====


def load_students():
    """載入已批准的學生資料"""
    if os.path.exists(STUDENTS_DB):
        with open(STUDENTS_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_students(students):
    """儲存學生資料到 JSON 檔案"""
    with open(STUDENTS_DB, "w", encoding="utf-8") as f:
        json.dump(students, f, ensure_ascii=False, indent=2)


def load_applicants():
    """載入申請中的學生資料"""
    if os.path.exists(APPLICANTS_DB):
        with open(APPLICANTS_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_applicants(applicants):
    """儲存申請者資料到 JSON 檔案"""
    with open(APPLICANTS_DB, "w", encoding="utf-8") as f:
        json.dump(applicants, f, ensure_ascii=False, indent=2)


# ===== 載入資料 =====
students = load_students()  # 載入學生資料
applicants = load_applicants()  # 載入申請者資料

# ===== Discord 機器人初始化 =====
intents = discord.Intents.default()
intents.message_content = True  # 允許讀取訊息內容
client = discord.Client(intents=intents)

# ===== 資料庫設定 =====
DB_PATH = "chatlogs.db"  # 資料庫檔案路徑
conn = sqlite3.connect(DB_PATH, check_same_thread=False)  # 建立資料庫連線
cur = conn.cursor()  # 建立資料庫游標

# ===== 檢查並更新統計定義資料表結構 =====
cur.execute("PRAGMA table_info(stats_definitions)")
columns = [row[1] for row in cur.fetchall()]

# 如果缺少 search_count 欄位則新增
if "search_count" not in columns:
    cur.execute("ALTER TABLE stats_definitions ADD COLUMN search_count INTEGER DEFAULT 0")

# 如果缺少 contributor 欄位則新增
if "contributor" not in columns:
    cur.execute("ALTER TABLE stats_definitions ADD COLUMN contributor TEXT")

conn.commit()

# ===== 建立資料表 =====

# 建立對話訊息記錄表
cur.execute(
    """
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 主鍵，自動遞增
  user_id TEXT,                           -- Discord 使用者 ID
  student_id TEXT,                        -- 學生學號
  dialogue_round INTEGER,                 -- 對話輪次
  role TEXT,                              -- 角色（user/assistant）
  content TEXT,                           -- 訊息內容
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP  -- 建立時間
);
"""
)
conn.commit()

# 建立練習題作答記錄表
cur.execute(
    """
CREATE TABLE IF NOT EXISTS exercise_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 主鍵，自動遞增
    user_id TEXT,                         -- Discord 使用者 ID
    student_id TEXT,                      -- 學生學號
    question_number INTEGER,              -- 題號
    attempt_number INTEGER,               -- 嘗試次數
    html_path TEXT,                       -- HTML 檔案路徑
    score INTEGER,                        -- 分數
    feedback TEXT,                        -- 評分回饋
    completed INTEGER DEFAULT 0,          -- 是否完成（0=未完成，1=已完成）
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP  -- 建立時間
)
"""
)
conn.commit()

# 建立練習題題庫表
cur.execute(
    """
CREATE TABLE IF NOT EXISTS exercise_questions (
    question_number INTEGER PRIMARY KEY,  -- 題號（主鍵）
    category TEXT,                       -- 題目分類
    question_text TEXT NOT NULL,         -- 題目內容
    correct_answer TEXT NOT NULL         -- 標準答案
)
"""
)
conn.commit()

# 建立人工問題單表
cur.execute(
    """
CREATE TABLE IF NOT EXISTS manual_questions (
    number_manua INTEGER PRIMARY KEY,    -- 主鍵，自動遞增
    student_id TEXT,                    -- 學生學號
    question_text TEXT NOT NULL         -- 問題內容
)
"""
)
conn.commit()

# ===== 全域變數 =====
current_question = {}  # 儲存每個使用者目前的題號
session = None  # HTTP 會話物件
semaphore = asyncio.Semaphore(5)  # 限制同時處理的請求數量


def increment_search_count(keyword):
    """
    增加關鍵字的搜尋計數

    Args:
        keyword (str): 要增加計數的關鍵字
    """
    cur.execute(
        """
        UPDATE stats_definitions
        SET search_count = search_count + 1
        WHERE keyword = ?
        """,
        (keyword,),
    )
    conn.commit()


@client.event
async def on_ready():
    """機器人啟動時執行的事件處理器"""
    global session
    session = aiohttp.ClientSession()  # 建立 HTTP 會話
    print(f"✅ Logged in as {client.user}")


async def call_openai(messages):
    """
    呼叫 OpenAI API 進行對話

    Args:
        messages (list): 對話訊息列表

    Returns:
        dict: OpenAI API 回應的 JSON 資料

    Raises:
        RuntimeError: 當 API 呼叫失敗時拋出例外
    """
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": MODEL, "messages": messages, "max_tokens": 600, "temperature": 0.2}  # 最大回應 Token 數  # 回應隨機性（較低值更一致）

    async with session.post(url, headers=headers, json=payload) as resp:
        text = await resp.text()
        if resp.status != 200:
            raise RuntimeError(f"OpenAI error {resp.status}: {text}")
        return json.loads(text)


def get_student_id_by_discord(user_id):
    """
    根據 Discord ID 獲取學生學號

    Args:
        user_id (str): Discord 使用者 ID

    Returns:
        str or None: 學生學號，若找不到則回傳 None
    """
    for student_id, info in students.items():
        if info.get("discord_id") == user_id:
            return student_id
    return None


def get_latest_dialogue_round(user_id, student_id):
    """
    獲取使用者最新的對話輪次

    Args:
        user_id (str): Discord 使用者 ID
        student_id (str): 學生學號

    Returns:
        int: 最新的對話輪次，若無則回傳 0
    """
    cur.execute(
        """
        SELECT MAX(dialogue_round) FROM messages
        WHERE user_id = ? AND student_id = ?
        """,
        (user_id, student_id),
    )
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else 0


def get_recent_history(user_id, student_id, limit=MAX_HISTORY):
    """
    獲取使用者最近的對話歷史

    Args:
        user_id (str): Discord 使用者 ID
        student_id (str): 學生學號
        limit (int): 要取得的輪次數量

    Returns:
        list: 對話訊息列表，格式為 [{"role": "user", "content": "..."}]
    """
    # 取得最大輪次
    cur.execute(
        """
        SELECT MAX(dialogue_round) FROM messages
        WHERE user_id = ? AND student_id = ?
        """,
        (user_id, student_id),
    )
    row = cur.fetchone()
    max_round = row[0] if row and row[0] is not None else 0

    # 計算要取的輪次範圍
    start_round = max(1, max_round - limit + 1)
    messages = []

    # 按輪次順序取得訊息
    for r in range(start_round, max_round + 1):
        cur.execute(
            """
            SELECT role, content FROM messages
            WHERE user_id = ? AND student_id = ? AND dialogue_round = ?
            ORDER BY id ASC
            """,
            (user_id, student_id, r),
        )
        rows = cur.fetchall()
        for role, content in rows:
            messages.append({"role": role, "content": content})

    return messages


def generate_stats_feedback_from_db(text: str, conn) -> str:
    """
    根據文字內容從資料庫生成統計定義補充

    Args:
        text (str): 要分析的文字內容
        conn: 資料庫連線物件

    Returns:
        str: HTML 格式的統計定義補充內容
    """
    text_lower = text.lower()
    cur = conn.cursor()
    cur.execute("SELECT keyword, definition FROM stats_definitions")
    rows = cur.fetchall()

    matched_defs = []
    # 檢查文字中包含的關鍵字
    for keyword, definition in rows:
        if keyword.lower() in text_lower:
            matched_defs.append(f"<p><b>{keyword.title()}</b>: {definition}</p>")
            increment_search_count(keyword)  # 增加搜尋計數

    return "\n".join(matched_defs) if matched_defs else "<p>No related statistical definitions found.</p>"


class PagedEmbedView(View):
    """分頁顯示的 Discord View 類別"""

    def __init__(self, pages):
        """
        初始化分頁 View

        Args:
            pages (list): 要顯示的頁面列表
        """
        super().__init__(timeout=180)  # 設定 3 分鐘超時
        self.pages = pages
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        """更新按鈕的啟用/禁用狀態"""
        if len(self.children) >= 2:
            self.children[0].disabled = self.current_page == 0  # 第一頁時禁用上一頁
            self.children[1].disabled = self.current_page == len(self.pages) - 1  # 最後一頁時禁用下一頁

    @discord.ui.button(label="⬅ 上一頁", style=discord.ButtonStyle.primary)
    async def previous_page(self, interaction: discord.Interaction, button: Button):
        """上一頁按鈕的事件處理器"""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="下一頁 ➡", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        """下一頁按鈕的事件處理器"""
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)


def insert_wiki_definition(keyword, definition, contributor="Wikipedia"):
    """
    插入維基百科定義到資料庫

    Args:
        keyword (str): 關鍵字
        definition (str): 定義內容
        contributor (str): 貢獻者，預設為 "Wikipedia"
    """
    # 檢查是否已存在
    cur.execute("SELECT keyword FROM stats_definitions WHERE keyword = ?", (keyword,))
    if not cur.fetchone():
        cur.execute(
            """
            INSERT INTO stats_definitions (keyword, definition, contributor, search_count)
            VALUES (?, ?, ?, 0)
            """,
            (keyword, definition, contributor),
        )
        conn.commit()


def has_wikipedia_result(results):
    """
    檢查結果中是否包含維基百科來源

    Args:
        results (list): 搜尋結果列表

    Returns:
        bool: 如果包含維基百科結果則回傳 True
    """
    return any(r[1] == "Wikipedia" for r in results)


async def handle_need_def(message):
    """
    處理定義查詢請求

    Args:
        message (discord.Message): Discord 訊息物件
    """
    content = message.content
    user_text = content[len("!need_def ") :].strip()

    if not user_text:
        await message.channel.send("⚠ 請輸入要查詢的關鍵字，例如：`!need_def 平均數, 標準差`")
        return

    # 解析多個關鍵字（支援逗號分隔）
    keywords = [kw.strip() for kw in user_text.replace("，", ",").split(",") if kw.strip()]

    # 取得資料庫中所有關鍵字
    cur.execute("SELECT keyword, definition FROM stats_definitions")
    db_entries = cur.fetchall()
    db_keywords = [row[0] for row in db_entries]

    all_results = []

    # 對每個關鍵字進行模糊比對
    for kw in keywords:
        matches = process.extract(kw, db_keywords, scorer=fuzz.partial_ratio, limit=5)
        found = False

        # 檢查是否有高相似度的匹配
        for matched_keyword, score in matches:
            if score >= 90:  # 相似度門檻 90%
                cur.execute("SELECT definition, contributor FROM stats_definitions WHERE keyword = ?", (matched_keyword,))
                row = cur.fetchone()
                if row:
                    definition, contributor = row
                else:
                    definition, contributor = "無定義", "未知"
                all_results.append((kw, matched_keyword, score, definition, contributor))
                increment_search_count(matched_keyword)
                found = True

        # 如果沒找到相似定義，嘗試從維基百科獲取
        if not found:
            wiki_def = get_wiki_definition(kw)
            if wiki_def:
                contributor = "Wikipedia"
                all_results.append((kw, "Wikipedia", 100, wiki_def, contributor))
                insert_wiki_definition(kw, wiki_def, contributor)
            else:
                all_results.append((kw, "無相關定義", 0, "找不到相關定義，Wikipedia 也查無資料。", "無"))

    if not all_results:
        await message.channel.send("❌ 找不到相似的定義。")
        return

    # 建立分頁顯示
    pages = []
    for i in range(0, len(all_results), 5):  # 每頁顯示 5 筆結果
        embed = discord.Embed(title="📚 定義查詢結果", description=f"搜尋關鍵字: `{', '.join(keywords)}`", color=discord.Color.blue())
        for kw, matched, score, definition, contributor in all_results[i : i + 5]:
            embed.add_field(
                name=f"{matched} (相似度 {score}%)", value=f"💡{definition[:1000]}\n\n貢獻者：{contributor}\n————————————————\n", inline=False
            )
        pages.append(embed)

    # 發送分頁結果
    view = PagedEmbedView(pages)
    await message.channel.send(embed=pages[0], view=view)


@client.event
async def on_message(message):
    """
    處理收到的 Discord 訊息事件

    Args:
        message (discord.Message): Discord 訊息物件
    """
    # 忽略機器人自己發送的訊息
    if message.author.bot:
        return

    # 處理定義查詢指令
    if message.content.lower().startswith("!need_def "):
        await handle_need_def(message)
        return

    user_id = str(message.author.id)
    content = message.content.strip()

    # === 處理幫助指令 ===
    if content.lower() == "!help":
        base_help = (
            "📚 **一般指令列表**:\n"
            "1. `!join <學號> <名字>` - 申請加入\n"
            "2. `!ask <問題>` - 問問題（需先通過審核）\n"
            "3. `!help` - 顯示指令清單\n"
            "4. `!pro_sta` - 實體上課進度\n"
            "5. `!need_teacher` - 需要人工老師檢閱問題\n"
            "6. `!need_def` - 查詢統計定義\n"
            "7. `!add_def` - 新增統計定義\n"
        )
        admin_help = "\n🔧 **管理員專用指令**:\n" "8. `!approve <學號>` - 批准學生申請\n" "9. `!listapplicants` - 查看待審核申請名單\n"

        # 根據使用者身份顯示不同的幫助內容
        if user_id == ADMIN_USER_ID:
            help_text = base_help + admin_help
        else:
            help_text = base_help

        await message.channel.send(help_text)
        return

    # === 管理員專用指令 ===

    # 查詢申請名單
    if user_id == ADMIN_USER_ID and content.lower() == "!listapplicants":
        if not applicants:
            await message.channel.send("目前沒有待審核的申請。")
            return

        lines = ["📋 目前待審核申請名單："]
        for discord_uid, info in applicants.items():
            lines.append(f"學號：{info['student_id']}，姓名：{info['name']}，Discord ID：{discord_uid}")

        # 分批私訊給管理員（避免訊息過長）
        chunk_size = 10
        for i in range(0, len(lines), chunk_size):
            chunk = "\n".join(lines[i : i + chunk_size])
            try:
                await message.author.send(chunk)
            except Exception:
                await message.channel.send("無法私訊管理員，請確認機器人權限。")
                break
        else:
            await message.channel.send("已私訊你所有待審核申請名單。")
        return

    # 批准學生申請
    if user_id == ADMIN_USER_ID and content.lower().startswith("!approve"):
        parts = content.split(maxsplit=1)
        if len(parts) < 2:
            await message.channel.send("用法：`!approve <學號>`")
            return

        student_id_to_approve = parts[1].strip()
        if student_id_to_approve in students:
            await message.channel.send(f"學號 {student_id_to_approve} 已經是授權學生。")
            return

        # 尋找對應的申請者
        applicant_discord_id = None
        applicant_name = None
        for discord_uid, info in applicants.items():
            if info.get("student_id") == student_id_to_approve:
                applicant_discord_id = discord_uid
                applicant_name = info.get("name")
                break

        if not applicant_discord_id:
            await message.channel.send(f"找不到學號 {student_id_to_approve} 的申請紀錄。")
            return

        # 新增學生到授權名單
        students[student_id_to_approve] = {"discord_id": applicant_discord_id, "name": applicant_name}
        save_students(students)

        # 從申請名單中移除
        del applicants[applicant_discord_id]
        save_applicants(applicants)

        await message.channel.send(f"成功批准學號 {student_id_to_approve}，姓名 {applicant_name}。")

        # 通知學生申請已被批准
        user = client.get_user(int(applicant_discord_id))
        if user:
            try:
                await user.send("你的申請已被批准，現在可以開始使用服務囉！")
            except Exception:
                pass
        return

    # === 學生申請加入系統 ===
    if content.lower().startswith("!join"):
        parts = content.split(maxsplit=2)
        if len(parts) < 3:
            await message.channel.send("請輸入格式：`!join 學號 你的名字`")
            return

        student_id = parts[1].strip()
        name = parts[2].strip()

        # 檢查是否已經是授權學生
        if get_student_id_by_discord(user_id):
            await message.channel.send("你已經是授權學生，可以直接使用服務囉！")
            return

        # 直接批准加入（跳過申請審核流程）
        students[student_id] = {"discord_id": user_id, "name": name}
        save_students(students)

        await message.channel.send(f"學號 {student_id}，姓名 {name}，已自動批准為授權學生！")
        return

    # === 驗證學生身份 ===
    student_id = get_student_id_by_discord(user_id)
    if not student_id:
        await message.channel.send("❌ 你不在授權學生名單內，請先用 `!join 學號 你的名字` 申請加入。")
        return

    # === 處理新增定義指令 ===
    if message.content.startswith("!add_def "):
        content = message.content[len("!add_def ") :].strip()
        if "|" in content:
            keyword, definition = content.split("|", 1)
            keyword = keyword.strip()
            definition = definition.strip()
            contributor_id = str(student_id)

            added = add_definition_to_db(cur, keyword, definition, contributor_id)
            if added:
                conn.commit()
                await message.channel.send(f"✅ 已新增「{keyword}」定義，感謝貢獻！")
            else:
                await message.channel.send(f"⚠ 「{keyword}」已存在於資料庫中，請避免重複新增。")
        else:
            await message.channel.send("⚠ 格式錯誤，請使用 `!add_def 關鍵字|定義內容`")
        return

    # === 處理 HTML 檔案上傳 ===
    if message.attachments:
        for file in message.attachments:
            if file.filename.lower().endswith(".html"):
                await message.channel.send("收到 HTML 檔案，珊瑩老師正在批改中...")

                # 儲存上傳的檔案
                os.makedirs("uploads", exist_ok=True)
                save_path = f"uploads/{user_id}_{file.filename}"
                await file.save(save_path)

                # === 解析 HTML 檔案 ===
                with open(save_path, encoding="utf-8") as f:
                    soup = BeautifulSoup(f, "html.parser")

                # 提取學生資訊
                name_label = soup.find("label", string="姓名：")
                id_label = soup.find("label", string="學號：")
                student_name_from_html = name_label.find_next("span").get_text(strip=True) if name_label else None
                student_id_from_html = id_label.find_next("span").get_text(strip=True) if id_label else None

                # 提取作答內容
                answer_label = soup.find("label", string="作答區：")
                if answer_label:
                    answer_tag = answer_label.find_next("p")
                    # 將 <br> 標籤轉換為換行符號
                    for br in answer_tag.find_all("br"):
                        br.replace_with("\n")
                    all_text = answer_tag.get_text("\n", strip=True)
                else:
                    all_text = ""

                # === 獲取題目資訊 ===
                q_num = current_question.get(user_id, 1)  # 預設第 1 題

                # 從資料庫獲取題目和標準答案
                cur.execute(
                    """
                    SELECT question_text, correct_answer
                    FROM exercise_questions
                    WHERE question_number=?
                    """,
                    (q_num,),
                )
                row = cur.fetchone()
                question_text = row[0] if row else "(無題目資料)"
                correct_answer = row[1] if row else "(無標準答案)"

                # 查詢嘗試次數
                cur.execute(
                    """
                    SELECT MAX(attempt_number) FROM exercise_answers
                    WHERE user_id=? AND question_number=?
                    """,
                    (user_id, q_num),
                )
                attempt = (cur.fetchone()[0] or 0) + 1

                # === 建立 GPT 評分 Prompt ===
                prompt = f"""
You are an expert English language assessor specialized in evaluating student writing in EMI (English as a Medium of Instruction) contexts.

題號：第{q_num}題

學生答案：
{all_text}

請回覆格式：
Score: <0-100>  
Band Level: <CEFR 等級>  
Feedback:  
<詳細回饋內容，使用 Markdown 格式>
"""

                # === 呼叫 GPT 進行評分 ===
                try:
                    gpt_resp = await call_openai(
                        [
                            {
                                "role": "system",
                                "content": "You are an expert English language assessor specialized in evaluating student writing in EMI.",
                            },
                            {"role": "user", "content": prompt},
                        ]
                    )
                    reply = gpt_resp["choices"][0]["message"]["content"]
                except Exception as e:
                    await message.channel.send(f"GPT 評分出錯：{e}")
                    return

                # === 解析 GPT 回覆 ===
                lines = reply.splitlines()
                score = 0
                band = ""
                feedback_lines = []

                # 逐行解析回覆內容
                for line in lines:
                    if line.lower().startswith("score:"):
                        try:
                            score = int(line.split(":", 1)[1].strip())
                        except:
                            pass
                    elif line.lower().startswith("band level:"):
                        band = line.split(":", 1)[1].strip()
                    elif line.lower().startswith("feedback:"):
                        idx = lines.index(line)
                        feedback_lines = lines[idx + 1 :]
                        break

                feedback = "\n".join(feedback_lines).strip()

                # === 生成 HTML 評分報告 ===
                import html

                def escape_with_br(text: str) -> str:
                    """處理文字中的換行符號，轉換為 HTML 格式"""
                    placeholder = "__BR__"
                    for br_tag in ["<br>", "<br/>", "\n", "<BR/>"]:
                        text = text.replace(br_tag, placeholder)
                    escaped = html.escape(text)
                    return escaped.replace(placeholder, "<br>")

                safe_all_text = escape_with_br(all_text)
                feedback_html = markdown.markdown(feedback, extensions=["tables", "fenced_code"])

                # 從資料庫生成統計定義補充
                stats_feedback_html = generate_stats_feedback_from_db(feedback_html, conn)

                # 完整的 HTML 報告模板
                html_report = f"""
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>學生英文統計解答評分報告</title>
<style>
/* 基礎樣式設定 */
body {{
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    background: linear-gradient(135deg, #e0eafc, #cfdef3);
    color: #2c3e50;
    margin: 40px auto;
    max-width: 960px;
    line-height: 1.75;
    padding: 0 20px;
    transition: background-color 0.5s ease;
}}

/* 標題樣式 */
h1, h2 {{
    color: #1f3a93;
    margin-bottom: 0.75em;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
}}

h1 {{
    border-bottom: 3px solid #2980b9;
    padding-bottom: 0.3em;
    font-size: 2.6rem;
    position: relative;
    animation: slideInFromLeft 0.8s ease forwards;
}}

h2 {{
    border-bottom: 2px solid #3498db;
    padding-bottom: 0.35em;
    margin-top: 2.5em;
    font-size: 1.9rem;
    position: relative;
    animation: fadeInUp 1s ease forwards;
}}

/* 分數樣式 */
.score {{
    font-size: 2.2rem;
    font-weight: 700;
    color: #27ae60;
    margin-top: 1.2em;
    margin-bottom: 0.5em;
    text-shadow: 0 2px 5px rgba(39, 174, 96, 0.6);
    animation: pulse 2s infinite;
}}

/* 等級樣式 */
.band {{
    font-size: 1.4rem;
    font-weight: 600;
    color: #2980b9;
    margin-bottom: 2em;
    animation: fadeIn 2s ease forwards;
}}

/* 區塊樣式 */
section {{
    background-color: #fff;
    border-radius: 16px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.1), 0 0 12px rgba(41, 128, 185, 0.2);
    padding: 35px 40px;
    margin-bottom: 50px;
    transition: box-shadow 0.4s ease, transform 0.3s ease;
}}

section:hover {{
    box-shadow: 0 16px 48px rgba(0,0,0,0.15), 0 0 20px rgba(41, 128, 185, 0.35);
    transform: translateY(-8px);
}}

/* 原始作答區域樣式 */
.original-answer {{
    font-family: Consolas, "Courier New", monospace;
    font-size: 1rem;
    color: #34495e;
    white-space: pre-wrap;
    border-left: 8px solid #2980b9;
    box-shadow: inset 4px 0 10px rgba(41, 128, 185, 0.3);
    padding-left: 20px;
    transition: background-color 0.3s ease;
}}

.original-answer:hover {{
    background-color: #d6e9fb;
}}

/* 回饋內容樣式 */
.feedback, .stats-feedback {{
    font-size: 1.1rem;
    color: #34495e;
    line-height: 1.65;
    animation: fadeIn 1.5s ease forwards;
}}

/* 表格樣式 */
table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 1.8em;
    font-size: 1rem;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    border-radius: 12px;
    overflow: hidden;
    animation: fadeInUp 1.5s ease forwards;
}}

th, td {{
    border: none;
    padding: 16px 20px;
    text-align: left;
}}

th {{
    background: linear-gradient(90deg, #3498db, #2980b9);
    color: white;
    font-weight: 700;
    box-shadow: inset 0 -3px 6px rgba(0,0,0,0.15);
}}

tr:nth-child(even) {{
    background-color: #f6f9fc;
}}

tr:hover {{
    background-color: #d0e7fc;
    transition: background-color 0.3s ease;
}}

/* 段落樣式 */
p {{
    margin: 0.8em 0;
}}

/* TTS 按鈕樣式 */
button.tts-button {{
    background-color: #2980b9;
    border: none;
    color: white;
    padding: 10px 18px;
    font-size: 1rem;
    border-radius: 6px;
    cursor: pointer;
    box-shadow: 0 4px 10px rgba(41, 128, 185, 0.6);
    margin-top: 10px;
    transition: background-color 0.3s ease;
}}

button.tts-button:hover {{
    background-color: #3498db;
}}

/* 動畫效果 */
@keyframes slideInFromLeft {{
    0% {{
        opacity: 0;
        transform: translateX(-50px);
    }}
    100% {{
        opacity: 1;
        transform: translateX(0);
    }}
}}

@keyframes fadeInUp {{
    0% {{
        opacity: 0;
        transform: translateY(20px);
    }}
    100% {{
        opacity: 1;
        transform: translateY(0);
    }}
}}

@keyframes pulse {{
    0%, 100% {{
        text-shadow: 0 0 6px #27ae60;
    }}
    50% {{
        text-shadow: 0 0 16px #27ae60;
    }}
}}

@keyframes fadeIn {{
    from {{ opacity: 0; }}
    to {{ opacity: 1; }}
}}

/* 響應式設計 */
@media screen and (max-width: 600px) {{
    body {{
        padding: 0 15px;
        margin: 20px auto;
    }}
    h1 {{
        font-size: 1.8rem;
    }}
    h2 {{
        font-size: 1.4rem;
    }}
    section {{
        padding: 25px 30px;
        margin-bottom: 30px;
    }}
    table th, table td {{
        padding: 12px 10px;
    }}
}}
</style>
</head>
<body>
    <!-- 報告標題 -->
    <h1>{student_name_from_html}_{student_id_from_html}_第{q_num}題_第{attempt}次</h1>
    <h1>學生英文統計解答評分報告</h1>

    <!-- 原始作答內容 -->
    <section class="original-answer">
        <h2>原始作答資料</h2>
        <div>{safe_all_text}</div>
    </section>

    <!-- 評分結果 -->
    <section class="score-section">
        <div class="score">總分：{score} / 100</div>
        <div class="band">CEFR 等級：{band}</div>
    </section>

    <!-- 回饋內容 -->
    <section class="feedback">
        <h2>回饋內容</h2>
        <button class="tts-button" onclick="playTTS('feedback')">播放回饋內容</button>
        <div id="feedback">{feedback_html}</div>
    </section>

    <!-- 統計定義補充 -->
    <section class="stats-feedback">
        <h2>統計定義補充</h2>
        <button class="tts-button" onclick="playTTS('stats-feedback')">播放統計定義補充</button>
        <div id="stats-feedback">{stats_feedback_html}</div>
    </section>

    <script>
        // 文字轉語音功能
        let synth = window.speechSynthesis;
        let utterance = null;

        function stripHTML(html) {{
            let div = document.createElement("div");
            div.innerHTML = html;
            return div.textContent || div.innerText || "";
        }}

        function playTTS(sectionId) {{
            if (synth.speaking) {{
                synth.cancel();  // 停止先前的語音
            }}
            let text = stripHTML(document.getElementById(sectionId).innerHTML);
            if (text !== "") {{
                utterance = new SpeechSynthesisUtterance(text);
                utterance.lang = 'en-US';  // 設定語音語言
                synth.speak(utterance);
            }}
        }}
    </script>
</body>
</html>
"""

                # === 儲存並發送報告 ===
                os.makedirs("response", exist_ok=True)
                save_path = os.path.join("response", f"{user_id}_{student_id}_{q_num}_{attempt}.html")
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(html_report)

                # 發送評分報告給使用者
                await message.channel.send(content=f"第{q_num}題第{attempt}次評分報告，請下載查看。", file=discord.File(save_path))

                # === 儲存評分結果到資料庫 ===
                completed = 1 if score >= 60 else 0  # 60分以上算通過
                cur.execute(
                    """
                    INSERT INTO exercise_answers (
                        user_id, student_id, question_number, attempt_number,
                        html_path, score, feedback, completed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, student_id_from_html or student_id, q_num, attempt, save_path, score, feedback, completed),
                )
                conn.commit()

                # 回覆評分結果
                await message.channel.send(f"第{q_num}題第{attempt}次嘗試評分：{score}分，{'已通過' if completed else '未通過'}")

                # 更新題號（通過才能進入下一題）
                current_question[user_id] = q_num + 1 if completed else q_num
                return

    # === 處理對話指令 ===

    # 判斷是私訊還是指令
    if isinstance(message.channel, discord.DMChannel):
        user_text = content
    elif content.lower().startswith("!ask "):
        user_text = content[len("!ask ") :].strip()
    elif content.lower().startswith("!pro_sta"):
        await message.channel.send("上課不專心喔，珊瑩老師很難過！")
        return
    elif content.lower().startswith("!need_teacher "):
        # 儲存需要人工回覆的問題
        user_text = content[len("!need_teacher ") :].strip()
        cur.execute(
            """
            INSERT INTO manual_questions (student_id, question_text)
            VALUES (?, ?)
            """,
            (student_id, user_text),
        )
        conn.commit()
        await message.channel.send("收到會於上課時回覆")
        return
    else:
        # 顯示幫助訊息
        base_help = (
            "📚 **一般指令列表**:\n"
            "1. `!join <學號> <名字>` - 申請加入\n"
            "2. `!ask <問題>` - 問問題（需先通過審核）\n"
            "3. `!help` - 顯示指令清單\n"
            "4. `!pro_sta` - 實體上課進度\n"
            "5. `!need_teacher` - 需要人工老師檢閱問題\n"
            "6. `!need_def` - 查詢統計定義\n"
            "7. `!add_def` - 新增統計定義\n"
        )
        admin_help = "\n🔧 **管理員專用指令**:\n" "8. `!approve <學號>` - 批准學生申請\n" "9. `!listapplicants` - 查看待審核申請名單\n"

        if user_id == ADMIN_USER_ID:
            help_text = base_help + admin_help
        else:
            help_text = base_help

        await message.channel.send(help_text)
        return

    # === 處理對話邏輯 ===

    # 獲取當前對話輪次
    current_round = get_latest_dialogue_round(user_id, student_id) + 1

    # 檢查是否有相同的問題
    cur.execute(
        """
        SELECT dialogue_round FROM messages
        WHERE user_id = ? AND student_id = ? AND role = 'user' AND content = ?
        ORDER BY id DESC LIMIT 1
        """,
        (user_id, student_id, user_text),
    )
    row = cur.fetchone()

    if row:
        # 找到相同問題，回傳之前的答案
        existing_round = row[0]
        cur.execute(
            """
            SELECT content FROM messages
            WHERE user_id = ? AND student_id = ? AND role = 'assistant' AND dialogue_round = ?
            ORDER BY id DESC LIMIT 1
            """,
            (user_id, student_id, existing_round),
        )
        reply_row = cur.fetchone()
        if reply_row:
            reply = reply_row[0]
            await message.channel.send(reply)
            return

    # 儲存使用者訊息
    cur.execute(
        "INSERT INTO messages (user_id, student_id, dialogue_round, role, content) VALUES (?, ?, ?, ?, ?)",
        (user_id, student_id, current_round, "user", user_text),
    )
    conn.commit()

    # 顯示思考中訊息
    waiting_msg = await message.channel.send(f"{students[student_id]['name']}，我正在思考...")

    try:
        # 使用信號量限制併發請求
        async with semaphore:
            # 獲取對話歷史並加入當前問題
            history_msgs = get_recent_history(user_id, student_id, MAX_HISTORY)
            history_msgs.append({"role": "user", "content": user_text})

            # 呼叫 OpenAI API
            data = await call_openai(history_msgs)
            reply = data["choices"][0]["message"]["content"]
    except Exception as e:
        await waiting_msg.edit(content=f"發生錯誤：{e}")
        return

    # 儲存 GPT 回覆
    cur.execute(
        "INSERT INTO messages (user_id, student_id, dialogue_round, role, content) VALUES (?, ?, ?, ?, ?)",
        (user_id, student_id, current_round, "assistant", reply),
    )
    conn.commit()

    # 更新等待訊息為實際回覆
    await waiting_msg.edit(content=reply)


@client.event
async def on_close():
    """機器人關閉時的清理工作"""
    global session
    if session:
        await session.close()  # 關閉 HTTP 會話
    conn.close()  # 關閉資料庫連線


# ===== 程式主入口點 =====
if __name__ == "__main__":
    client.run(DISCORD_TOKEN)  # 啟動 Discord 機器人
