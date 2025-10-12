import json
import re
import aiohttp
from config import OPENAI_API_KEY, MODEL, DEFAULT_PROMPTS, SPECIFIC_PROMPTS, PROMPT_MAPPING_FILE


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

    def load_prompt_template(self, prompt_type, html_title=None):
        """根據 HTML 標題和評分類型讀取對應的 prompt 模板"""
        prompt_file = None

        # 優先使用 HTML 標題匹配特定 prompt
        if html_title and html_title in SPECIFIC_PROMPTS:
            if prompt_type.lower() == "stats":
                # 統計評分時，使用標題對應的特定 prompt
                prompt_file = SPECIFIC_PROMPTS[html_title]
                print(f"根據標題 '{html_title}' 使用特定統計 prompt: {prompt_file}")
            else:
                # 英語評分時，使用預設英語 prompt
                prompt_file = DEFAULT_PROMPTS.get("eng")
                print(f"英語評分使用預設 prompt，標題: '{html_title}'")
        else:
            # 使用預設 prompt
            prompt_file = DEFAULT_PROMPTS.get(prompt_type.lower())
            if html_title:
                print(f"標題 '{html_title}' 未找到特定 prompt，使用預設 {prompt_type} prompt: {prompt_file}")
            else:
                print(f"無標題資訊，使用預設 {prompt_type} prompt: {prompt_file}")

        # 如果還是沒有找到 prompt 檔案，使用舊的命名方式作為備用
        if not prompt_file:
            prompt_file = f"prompt_{prompt_type}.txt"
            print(f"使用備用 prompt 檔案: {prompt_file}")

        # 讀取 prompt 檔案
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            print(f"警告：找不到提示檔案 {prompt_file}")
            return "None"

    async def grade_homework(self, answer_text, question_number, prompt_type, html_title=None):
        """使用 GPT 評分作業"""
        prompt_template = self.load_prompt_template(prompt_type, html_title)
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
