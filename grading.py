import json
import re
import aiohttp
from config import OPENAI_API_KEY, MODEL, DEFAULT_PROMPTS, SPECIFIC_PROMPTS


class GradingService:
    def __init__(self, session):
        self.session = session

    async def call_openai(self, messages):
        """呼叫 OpenAI API 進行智慧評分"""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": MODEL, "messages": messages, "max_tokens": 600, "temperature": 0.2}

        async with self.session.post(url, headers=headers, json=payload) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"OpenAI API 錯誤 {resp.status}: {text}")
            return json.loads(text)

    def load_prompt_template(self, prompt_type, html_title=None):
        """根據作業標題和評分類型載入對應的評分模板"""
        prompt_file = None

        # 優先使用作業標題匹配特定評分模板
        if html_title and html_title in SPECIFIC_PROMPTS:
            if prompt_type.lower() == "stats":
                # 統計評分時，使用標題對應的專用模板
                prompt_file = SPECIFIC_PROMPTS[html_title]
                print(f"🎯 根據題目「{html_title}」使用專用統計評分模板: {prompt_file}")
            else:
                # 英語評分時，使用預設英語模板
                prompt_file = DEFAULT_PROMPTS.get("eng")
                print(f"📝 英語評分使用通用模板，題目: 「{html_title}」")
        else:
            # 使用預設評分模板
            prompt_file = DEFAULT_PROMPTS.get(prompt_type.lower())
            if html_title:
                print(f"📋 題目「{html_title}」未找到專用模板，使用 {prompt_type} 通用模板: {prompt_file}")
            else:
                print(f"📄 無題目資訊，使用 {prompt_type} 預設模板: {prompt_file}")

        # 如果還是沒有找到模板檔案，使用備用命名方式
        if not prompt_file:
            prompt_file = f"prompt_{prompt_type}.txt"
            print(f"🔄 使用備用評分模板: {prompt_file}")

        # 讀取評分模板檔案
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            print(f"⚠️ 警告：找不到評分模板檔案 {prompt_file}")
            return "None"

    async def grade_homework(self, answer_text, question_number, prompt_type, html_title=None):
        """使用 AI 進行作業智慧評分"""
        prompt_template = self.load_prompt_template(prompt_type, html_title)
        prompt = prompt_template.format(question_number=question_number, answer_text=answer_text)

        try:
            gpt_resp = await self.call_openai(
                [
                    {"role": "system", "content": f"您是專業的 {prompt_type} 評分專家，專門評估 EMI 課程中學生的寫作表現。"},
                    {"role": "user", "content": prompt},
                ]
            )
            reply = gpt_resp["choices"][0]["message"]["content"]
            return reply
        except Exception as e:
            return f"評分系統錯誤：{e}"

    def parse_grading_result(self, reply):
        """解析 AI 評分回覆，提取分數和評語內容"""
        print(f"🔍 開始解析 AI 評分結果...")
        print(f"📝 評分回覆內容:\n{reply}")
        print(f"📏 內容長度: {len(reply)} 字元")

        lines = reply.splitlines()
        score = 0
        band = ""
        feedback_lines = []
        feedback_started = False

        print(f"📋 逐行分析處理，共 {len(lines)} 行:")

        for i, line in enumerate(lines):
            line_clean = line.strip()
            print(f"  第{i+1}行: 「{line_clean}」")

            # 更靈活的分數識別
            if any(keyword in line.lower() for keyword in ["score:", "分數:", "總分:", "得分:"]):
                try:
                    # 提取冒號後的內容
                    score_part = line.split(":", 1)[1] if ":" in line else line
                    print(f"    🔍 發現分數行，提取部分: 「{score_part}」")

                    # 尋找數字
                    score_matches = re.findall(r"\d+", score_part)
                    if score_matches:
                        # 取第一個數字作為分數
                        score = int(score_matches[0])
                        print(f"    ✅ 成功提取分數: {score}")
                    else:
                        print(f"    ❌ 未找到有效數字")
                except Exception as e:
                    print(f"    ❌ 分數提取錯誤: {e}")

            # 更靈活的等級識別
            elif any(keyword in line.lower() for keyword in ["band:", "level:", "等級:", "級別:"]):
                try:
                    band_part = line.split(":", 1)[1] if ":" in line else line
                    band = band_part.strip()
                    print(f"    ✅ 成功提取等級: 「{band}」")
                except Exception as e:
                    print(f"    ❌ 等級提取錯誤: {e}")

            # 更靈活的評語識別
            elif any(keyword in line.lower() for keyword in ["feedback:", "回饋:", "建議:", "評語:"]):
                feedback_started = True
                print(f"    🎯 找到評語開始標記")
                # 如果同一行有內容，也加入評語
                feedback_part = line.split(":", 1)[1] if ":" in line else ""
                if feedback_part.strip():
                    feedback_lines.append(feedback_part.strip())
                # 添加後續所有行
                feedback_lines.extend([l.strip() for l in lines[i + 1 :] if l.strip()])
                break

        # 如果沒有找到明確的評語標記，將整個回覆作為評語
        if not feedback_started and not feedback_lines:
            print("    ⚠️ 未找到評語標記，使用完整回覆作為評語")
            feedback_lines = [line.strip() for line in lines if line.strip()]

        feedback = "\n".join(feedback_lines).strip()

        print(f"📊 評分解析結果:")
        print(f"  分數: {score}")
        print(f"  等級: 「{band}」")
        print(f"  評語長度: {len(feedback)} 字元")
        print(f"  評語預覽: {feedback[:100]}..." if len(feedback) > 100 else f"  評語內容: {feedback}")

        # 如果分數為0，嘗試更寬鬆的數字提取
        if score == 0:
            print("⚠️ 分數為0，嘗試使用更寬鬆的數字提取方法")
            all_numbers = re.findall(r"\d+", reply)
            if all_numbers:
                # 過濾合理的分數範圍 (0-100)
                valid_scores = [int(num) for num in all_numbers if 0 <= int(num) <= 100]
                if valid_scores:
                    score = valid_scores[0]
                    print(f"  🔄 使用寬鬆方法提取的分數: {score}")

        return score, band, feedback
