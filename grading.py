import json
import re
import aiohttp
from config import OPENAI_API_KEY, MODEL, ENG_PROMPT_FILE, STATS_PROMPT_FILE


class GradingService:
    def __init__(self, session):
        self.session = session

    async def call_openai(self, messages):
        """呼叫 OpenAI API 進行文字生成"""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": MODEL, "messages": messages, "max_tokens": 600, "temperature": 0.2}

        async with self.session.post(url, headers=headers, json=payload) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"OpenAI error {resp.status}: {text}")
            return json.loads(text)

    def load_prompt_template(self, prompt_type):
        """從 txt 檔案讀取評分提示模板"""
        # 根據 prompt_type 選擇對應的檔案路徑
        if prompt_type.lower() == "eng":
            prompt_file = ENG_PROMPT_FILE
        elif prompt_type.lower() == "stats":
            prompt_file = STATS_PROMPT_FILE
        else:
            # 如果是其他類型，使用舊的命名方式作為備用
            prompt_file = f"prompt_{prompt_type}.txt"

        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            default_prompt = f"""You are an expert {prompt_type} assessor specialized in evaluating student writing in EMI (English as a Medium of Instruction) contexts.

題號：第{{question_number}}題

學生答案：
{{answer_text}}

Feedback:  
<詳細回饋內容，使用 Markdown 格式>"""

            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(default_prompt)
            return default_prompt

    async def grade_homework(self, answer_text, question_number, prompt_type):
        """使用 GPT 評分作業"""
        prompt_template = self.load_prompt_template(prompt_type)
        prompt = prompt_template.format(question_number=question_number, answer_text=answer_text)

        try:
            gpt_resp = await self.call_openai(
                [
                    {"role": "system", "content": f"You are an expert {prompt_type} assessor specialized in evaluating student writing in EMI."},
                    {"role": "user", "content": prompt},
                ]
            )
            reply = gpt_resp["choices"][0]["message"]["content"]
            return reply
        except Exception as e:
            return f"評分錯誤：{e}"

    def parse_grading_result(self, reply):
        """解析 GPT 回覆，提取分數和回饋內容"""
        lines = reply.splitlines()
        score = 0
        band = ""
        feedback_lines = []
        feedback_started = False

        for i, line in enumerate(lines):
            if line.lower().startswith("score:"):
                try:
                    score_text = line.split(":", 1)[1].strip()
                    score_match = re.search(r"\d+", score_text)
                    if score_match:
                        score = int(score_match.group())
                except:
                    pass
            elif line.lower().startswith("band level:"):
                band = line.split(":", 1)[1].strip()
            elif line.lower().startswith("feedback:"):
                feedback_started = True
                feedback_lines = lines[i + 1 :]
                break
            elif feedback_started:
                feedback_lines.append(line)

        feedback = "\n".join(feedback_lines).strip()

        if not feedback and not feedback_started:
            feedback = reply.strip()

        return score, band, feedback
