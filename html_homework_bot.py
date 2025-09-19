import os
import asyncio
import sqlite3
import json
from bs4 import BeautifulSoup
import markdown
import discord
import aiohttp
from dotenv import load_dotenv
from datetime import datetime

# ===== Discord Bot 設定 =====

# 載入環境變數檔案
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")  # Discord 機器人 Token
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # OpenAI API 金鑰
MODEL = "gpt-4o-mini"  # 使用的 OpenAI 模型

# 設定 Discord 機器人權限
intents = discord.Intents.default()
intents.message_content = True  # 允許讀取訊息內容
client = discord.Client(intents=intents)

# SQLite 資料庫設定
DB_PATH = "homework.db"  # 資料庫檔案路徑
conn = sqlite3.connect(DB_PATH, check_same_thread=False)  # 建立資料庫連線
cur = conn.cursor()  # 建立資料庫游標

# 建立作業提交記錄資料表
cur.execute(
    """
CREATE TABLE IF NOT EXISTS homework_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,    -- 主鍵，自動遞增
    user_id TEXT,                           -- Discord 使用者 ID
    student_name TEXT,                      -- 學生姓名
    student_id TEXT,                        -- 學生學號
    question_number INTEGER,                -- 題號
    attempt_number INTEGER,                 -- 嘗試次數
    html_path TEXT,                         -- HTML 檔案路徑
    score INTEGER,                          -- 分數
    feedback TEXT,                          -- 評分回饋
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP  -- 建立時間
)
"""
)
conn.commit()

# 全域變數儲存 HTTP 連線會話
session = None


@client.event
async def on_ready():
    """機器人啟動時執行的事件處理器"""
    global session
    session = aiohttp.ClientSession()  # 建立 HTTP 連線會話
    print(f"✅ HTML作業處理機器人已啟動: {client.user}")


async def call_openai(messages):
    """
    呼叫 OpenAI API 進行文字生成

    Args:
        messages (list): 對話訊息列表

    Returns:
        dict: OpenAI API 回應的 JSON 資料

    Raises:
        RuntimeError: 當 API 呼叫失敗時拋出例外
    """
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": MODEL, "messages": messages, "max_tokens": 600, "temperature": 0.2}  # 最大回應長度  # 回應的隨機性（較低值更一致）

    async with session.post(url, headers=headers, json=payload) as resp:
        text = await resp.text()
        if resp.status != 200:
            raise RuntimeError(f"OpenAI error {resp.status}: {text}")
        return json.loads(text)


def extract_html_content(file_path):
    """
    解析 HTML 檔案，提取學生資訊和作答內容

    Args:
        file_path (str): HTML 檔案路徑

    Returns:
        tuple: (學生姓名, 學生學號, 作答內容)
    """
    with open(file_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # 提取姓名與學號 - 尋找特定的 label 標籤
    name_label = soup.find("label", string="姓名：")
    id_label = soup.find("label", string="學號：")

    # 獲取 label 後面的 span 標籤內容
    student_name = name_label.find_next("span").get_text(strip=True) if name_label else "未知"
    student_id = id_label.find_next("span").get_text(strip=True) if id_label else "未知"

    # 提取作答內容 - 尋找作答區域
    answer_label = soup.find("label", string="作答區：")
    if answer_label:
        answer_tag = answer_label.find_next("p")
        # 將 <br> 標籤轉換為換行符號以保留格式
        for br in answer_tag.find_all("br"):
            br.replace_with("\n")
        answer_text = answer_tag.get_text("\n", strip=True)
    else:
        answer_text = ""

    return student_name, student_id, answer_text


def load_prompt_template(prompt_type):
    """
    從 txt 檔案讀取評分提示模板

    Args:
        prompt_type (str): 提示類型（如 'eng' 或 'stats'）

    Returns:
        str: 提示模板內容
    """
    prompt_file = f"prompt_{prompt_type}.txt"
    try:
        # 嘗試讀取現有的提示檔案
        with open(prompt_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        # 如果檔案不存在，建立預設模板
        default_prompt = f"""You are an expert {prompt_type} assessor specialized in evaluating student writing in EMI (English as a Medium of Instruction) contexts.

題號：第{{question_number}}題

學生答案：
{{answer_text}}

請回覆格式：
Score: <0-100>  
Band Level: <CEFR 等級>  
Feedback:  
<詳細回饋內容，使用 Markdown 格式>"""

        # 創建預設檔案供未來使用
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(default_prompt)
        return default_prompt


async def grade_homework(answer_text, question_number, prompt_type):
    """
    使用 GPT 評分作業

    Args:
        answer_text (str): 學生的作答內容
        question_number (int): 題號
        prompt_type (str): 評分類型（eng 或 stats）

    Returns:
        str: GPT 的評分回應
    """
    # 載入並格式化提示模板
    prompt_template = load_prompt_template(prompt_type)
    prompt = prompt_template.format(question_number=question_number, answer_text=answer_text)

    try:
        # 建立對話訊息並呼叫 OpenAI API
        gpt_resp = await call_openai(
            [
                {"role": "system", "content": f"You are an expert {prompt_type} assessor specialized in evaluating student writing in EMI."},
                {"role": "user", "content": prompt},
            ]
        )
        reply = gpt_resp["choices"][0]["message"]["content"]
        return reply
    except Exception as e:
        return f"評分錯誤：{e}"


def parse_grading_result(reply):
    """
    解析 GPT 回覆，提取分數和回饋內容

    Args:
        reply (str): GPT 的完整回應

    Returns:
        tuple: (分數, 等級, 回饋內容)
    """
    lines = reply.splitlines()
    score = 0
    band = ""
    feedback_lines = []
    feedback_started = False

    # 逐行解析回應內容
    for i, line in enumerate(lines):
        if line.lower().startswith("score:"):
            try:
                score_text = line.split(":", 1)[1].strip()
                # 使用正規表達式提取數字
                import re

                score_match = re.search(r"\d+", score_text)
                if score_match:
                    score = int(score_match.group())
            except:
                pass
        elif line.lower().startswith("band level:"):
            # 提取等級資訊
            band = line.split(":", 1)[1].strip()
        elif line.lower().startswith("feedback:"):
            # 標記回饋內容開始，收集後續所有行
            feedback_started = True
            feedback_lines = lines[i + 1 :]
            break
        elif feedback_started:
            feedback_lines.append(line)

    # 組合回饋內容
    feedback = "\n".join(feedback_lines).strip()

    # 如果沒有找到明確的 feedback 標記，將整個回覆當作回饋
    if not feedback and not feedback_started:
        feedback = reply.strip()

    return score, band, feedback


def generate_html_report(
    student_name, student_id, question_number, attempt, answer_text, eng_score, eng_band, eng_feedback, stats_score, stats_band, stats_feedback
):
    """
    生成 HTML 格式的評分報告

    Args:
        student_name (str): 學生姓名
        student_id (str): 學生學號
        question_number (int): 題號
        attempt (int): 嘗試次數
        answer_text (str): 原始作答內容
        eng_score (int): 英語評分分數
        eng_band (str): 英語評分等級
        eng_feedback (str): 英語評分回饋
        stats_score (int): 統計評分分數
        stats_band (str): 統計評分等級
        stats_feedback (str): 統計評分回饋

    Returns:
        str: 完整的 HTML 報告內容
    """
    import html

    def escape_with_br(text: str) -> str:
        """處理文字中的換行符號，轉換為 HTML 格式"""
        placeholder = "__BR__"
        # 將各種換行標籤統一處理
        for br_tag in ["<br>", "<br/>", "\n", "<BR/>"]:
            text = text.replace(br_tag, placeholder)
        escaped = html.escape(text)  # HTML 轉義
        return escaped.replace(placeholder, "<br>")

    # 處理作答內容的 HTML 轉義
    safe_answer_text = escape_with_br(answer_text)

    # 確保回饋內容不為空，並轉換為 HTML
    eng_feedback_clean = eng_feedback.strip() if eng_feedback else "無回饋內容"
    stats_feedback_clean = stats_feedback.strip() if stats_feedback else "無回饋內容"

    # 根據回饋內容長度選擇顯示格式
    # 短內容或錯誤訊息使用 pre 標籤，長內容使用 Markdown 轉換
    if len(eng_feedback_clean) < 100 or "評分錯誤" in eng_feedback_clean:
        eng_feedback_html = f"<pre>{html.escape(eng_feedback_clean)}</pre>"
    else:
        eng_feedback_html = markdown.markdown(eng_feedback_clean, extensions=["tables", "fenced_code"])

    if len(stats_feedback_clean) < 100 or "評分錯誤" in stats_feedback_clean:
        stats_feedback_html = f"<pre>{html.escape(stats_feedback_clean)}</pre>"
    else:
        stats_feedback_html = markdown.markdown(stats_feedback_clean, extensions=["tables", "fenced_code"])

    # 除錯資訊輸出
    print(f"生成HTML報告 - 英語回饋長度: {len(eng_feedback_clean)}, 統計回饋長度: {len(stats_feedback_clean)}")

    # 完整的 HTML 報告模板
    html_report = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>作業評分報告</title>
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
}}

/* 標題樣式 */
h1, h2 {{
    color: #1f3a93;
    margin-bottom: 0.75em;
    font-weight: 700;
    letter-spacing: 0.03em;
}}

h1 {{
    border-bottom: 3px solid #2980b9;
    padding-bottom: 0.3em;
    font-size: 2.6rem;
}}

h2 {{
    border-bottom: 2px solid #3498db;
    padding-bottom: 0.35em;
    margin-top: 2.5em;
    font-size: 1.9rem;
}}

/* 區塊樣式 */
section {{
    background-color: #fff;
    border-radius: 16px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.1);
    padding: 35px 40px;
    margin-bottom: 50px;
}}

/* 原始作答區域樣式 */
.original-answer {{
    font-family: Consolas, "Courier New", monospace;
    font-size: 1rem;
    color: #34495e;
    white-space: pre-wrap;
    border-left: 8px solid #2980b9;
    padding-left: 20px;
    background-color: #f8f9fa;
}}

/* 回饋內容樣式 */
.feedback-content {{
    background-color: #f8f9fa;
    border-radius: 8px;
    padding: 20px;
    margin-top: 15px;
    border-left: 4px solid #3498db;
    word-wrap: break-word;
    overflow-wrap: break-word;
}}

.feedback-content p {{
    margin-bottom: 10px;
    line-height: 1.6;
}}

.feedback-content pre {{
    background-color: #f4f4f4;
    padding: 10px;
    border-radius: 4px;
    white-space: pre-wrap;
    font-family: monospace;
}}

/* 英語評分區域樣式 */
.grading-section.eng .feedback-content {{
    border-left-color: #3498db;
    background-color: #f0f7ff;
}}

/* 統計評分區域樣式 */
.grading-section.stats .feedback-content {{
    border-left-color: #e67e22;
    background-color: #fff8f0;
}}

/* 評分區域基礎樣式 */
.grading-section {{
    border-left: 6px solid #e74c3c;
    padding-left: 20px;
    margin-bottom: 30px;
}}

.grading-section.eng {{
    border-left-color: #3498db;
}}

.grading-section.stats {{
    border-left-color: #e67e22;
}}
</style>
</head>
<body>
    <!-- 報告標題 -->
    <h1>{student_name}_{student_id}_第{question_number}題_第{attempt}次</h1>
    
    <!-- 原始作答內容區域 -->
    <section class="original-answer">
        <h2>原始作答資料</h2>
        <div>{safe_answer_text}</div>
    </section>
    
    <!-- 英語評分區域 -->
    <section class="grading-section eng">
        <h2>🔤 英語評分</h2>
        <div class="feedback-content">{eng_feedback_html}</div>
    </section>
    
    <!-- 統計評分區域 -->
    <section class="grading-section stats">
        <h2>📊 統計評分</h2>
        <div class="feedback-content">{stats_feedback_html}</div>
    </section>
</body>
</html>"""

    return html_report


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

    user_id = str(message.author.id)  # 獲取使用者 ID

    # === 處理幫助指令 ===
    if message.content.lower() == "!help":
        help_text = "📚 **HTML作業處理機器人指令**:\n" "1. 直接上傳 `.html` 檔案 - 系統會自動處理並評分\n" "2. `!help` - 顯示此幫助訊息\n"
        # 將幫助訊息私訊給使用者
        await message.author.send(help_text)

        # 刪除伺服器中的原始訊息以保持頻道整潔
        try:
            await message.delete()
        except discord.Forbidden:
            print("無權限刪除訊息")
        except discord.NotFound:
            print("訊息已被刪除")
        except Exception as e:
            print(f"刪除訊息時發生錯誤: {e}")
        return

    # === 處理 HTML 檔案上傳 ===
    if message.attachments:
        for file in message.attachments:
            # 檢查是否為 HTML 檔案
            if file.filename.lower().endswith(".html"):
                # 通知使用者開始處理
                await message.author.send("📝 收到HTML檔案，正在處理中...")

                # 建立上傳目錄
                os.makedirs("uploads", exist_ok=True)
                save_path = f"uploads/{user_id}_{file.filename}"

                try:
                    # 儲存上傳的檔案
                    await file.save(save_path)

                    # 檔案保存成功後，刪除伺服器中的原始訊息
                    try:
                        await message.delete()
                    except discord.Forbidden:
                        print("無權限刪除訊息")
                    except discord.NotFound:
                        print("訊息已被刪除")
                    except Exception as e:
                        print(f"刪除訊息時發生錯誤: {e}")

                    # 解析 HTML 檔案內容
                    student_name, student_id, answer_text = extract_html_content(save_path)

                    # 設定題號（這裡可以從檔案內容或檔名解析獲得）
                    question_number = 1

                    # 查詢該使用者對此題目的當前嘗試次數
                    cur.execute(
                        """
                        SELECT MAX(attempt_number) FROM homework_submissions
                        WHERE user_id = ? AND question_number = ?
                        """,
                        (user_id, question_number),
                    )
                    # 計算新的嘗試次數
                    attempt = (cur.fetchone()[0] or 0) + 1

                    # === 進行英語評分 ===
                    await message.author.send("🔍 正在進行英語評分...")
                    eng_result = await grade_homework(answer_text, question_number, "eng")
                    eng_score, eng_band, eng_feedback = parse_grading_result(eng_result)
                    print(f"英語評分結果: Score={eng_score}, Band={eng_band}, Feedback前50字={eng_feedback[:50]}...")

                    # === 進行統計評分 ===
                    await message.author.send("📊 正在進行統計評分...")
                    stats_result = await grade_homework(answer_text, question_number, "stats")
                    stats_score, stats_band, stats_feedback = parse_grading_result(stats_result)
                    print(f"統計評分結果: Score={stats_score}, Band={stats_band}, Feedback前50字={stats_feedback[:50]}...")

                    # === 生成 HTML 評分報告 ===
                    html_report = generate_html_report(
                        student_name,
                        student_id,
                        question_number,
                        attempt,
                        answer_text,
                        eng_score,
                        eng_band,
                        eng_feedback,
                        stats_score,
                        stats_band,
                        stats_feedback,
                    )

                    # 儲存 HTML 報告到檔案
                    os.makedirs("reports", exist_ok=True)
                    report_path = f"reports/{user_id}_{student_id}_{question_number}_{attempt}.html"
                    with open(report_path, "w", encoding="utf-8") as f:
                        f.write(html_report)

                    # === 將評分結果儲存到資料庫 ===
                    # 注意：這裡使用英語評分作為主要記錄
                    cur.execute(
                        """
                        INSERT INTO homework_submissions (
                            user_id, student_name, student_id, question_number,
                            attempt_number, html_path, score, feedback
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (user_id, student_name, student_id, question_number, attempt, save_path, eng_score, eng_feedback),
                    )
                    conn.commit()  # 提交資料庫異動

                    # === 發送評分結果給使用者 ===
                    result_text = (
                        f"✅ **評分完成**\n"
                        f"學生: {student_name} ({student_id})\n"
                        f"第{question_number}題 第{attempt}次嘗試\n"
                        f"已完成英語與統計雙重評分\n"
                    )

                    # 私訊發送結果文字和 HTML 報告檔案
                    await message.author.send(content=result_text, file=discord.File(report_path))

                except Exception as e:
                    # 處理過程中發生錯誤時的處理
                    await message.author.send(f"❌ 處理檔案時發生錯誤: {e}")
                    # 如果檔案處理失敗，仍然嘗試刪除訊息
                    try:
                        await message.delete()
                    except:
                        pass

                return  # 處理完畢後返回


@client.event
async def on_close():
    """機器人關閉時的清理工作"""
    global session
    if session:
        await session.close()  # 關閉 HTTP 連線會話
    conn.close()  # 關閉資料庫連線


# === 程式主入口點 ===
if __name__ == "__main__":
    client.run(DISCORD_TOKEN)  # 啟動 Discord 機器人
    # 注意：session.close() 應該在異步環境中等待，這裡只關閉資料庫連線
    conn.close()
