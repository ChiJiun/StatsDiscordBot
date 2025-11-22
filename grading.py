import json
import re
import openai
import os
import datetime
import docx
import markdown
import asyncio
from concurrent.futures import ThreadPoolExecutor
from config import OPENAI_API_KEY, MODEL, SPECIFIC_PROMPTS


class GradingService:
    # 添加線程池執行器（類別層級）
    _executor = ThreadPoolExecutor(max_workers=2)
    
    @staticmethod
    def get_grading_prompts(question_title=None):
        """
        Get grading prompts from config.py based on question title
        Returns: 
            (eng_prompt, stat_prompt) or (None, None) if not found
        """
        # 如果沒有提供題目標題，直接返回 None
        if not question_title:
            return None, None
        
        # ✅ 修改：嚴格檢查，只有在 SPECIFIC_PROMPTS 有定義時才回傳
        if question_title in SPECIFIC_PROMPTS:
            prompt_config = SPECIFIC_PROMPTS[question_title]
            
            # 確保 prompt_config 是字典
            if isinstance(prompt_config, dict):
                eng_prompt_file = prompt_config.get("english")
                stat_prompt_file = prompt_config.get("statistics")
                print(f"🎯 題目 '{question_title}' 找到專屬 Prompt")
            else:
                print(f"⚠️ 警告：題目 '{question_title}' 的 prompt 配置格式錯誤")
                return None, None
        else:
            # ❌ 如果找不到特定 prompt，直接返回 None，不使用預設值
            print(f"ℹ️ 題目 '{question_title}' 尚未設定 Prompt，停止評分")
            return None, None
        
        # 讀取 prompt 檔案內容
        eng_prompt = GradingService._read_prompt_file(eng_prompt_file)
        stat_prompt = GradingService._read_prompt_file(stat_prompt_file)
        
        if not eng_prompt or not stat_prompt:
            print(f"❌ 無法讀取 prompt 檔案: {eng_prompt_file}, {stat_prompt_file}")
            return None, None
        
        return eng_prompt, stat_prompt

    @staticmethod
    def _read_prompt_file(file_path):
        """
        Read prompt content from file
        Args:
            file_path (str): Path to the prompt file
        Returns:
            str: Content of the prompt file
        """
        if not file_path or not os.path.exists(file_path):
            print(f"❌ Prompt 檔案不存在: {file_path}")
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # print(f"✅ 成功讀取 prompt 檔案: {file_path}")
                return content
        except Exception as e:
            print(f"❌ 讀取 prompt 檔案失敗: {file_path}, 錯誤: {e}")
            return None

    # ---------- Student Data Extraction ----------
    @staticmethod
    def extract_student_data(file_path):
        """
        Read .docx file: first line is student name, subsequent lines are answer.
        """
        doc = docx.Document(file_path)
        paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        if paras:
            name = paras[0]
            answer = "\n".join(paras[1:])
        else:
            name, answer = "Unknown", ""
        return name, answer

    # ---------- OpenAI Interaction ----------
    @staticmethod
    def create_messages(prompt, student_name, student_answer):
        """
        Construct messages for ChatGPT: system prompt + student data.
        """
        user_msg = (
            f"Student Name: {student_name}\n"
            f"Student Answer:\n{student_answer}\n"
            "Please evaluate the student's performance according to the system instructions."
        )
        return [
            {"role": "system", "content": prompt},
            {"role": "user",   "content": user_msg}
        ]

    @staticmethod
    def _generate_feedback_sync(messages, model=None, temperature=1.0):
        """同步呼叫 OpenAI API（在執行緒池中執行）"""
        import openai
        
        if model is None:
            model = MODEL
        
        openai.api_key = OPENAI_API_KEY
        
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ OpenAI API 呼叫失敗: {e}")
            raise

    @staticmethod
    async def generate_feedback(messages, model=None, temperature=1.0):
        """
        非同步生成評分反饋
        """
        loop = asyncio.get_event_loop()
        
        feedback = await loop.run_in_executor(
            GradingService._executor,
            GradingService._generate_feedback_sync,
            messages,
            model,
            temperature
        )
        
        return feedback

    # ---------- Report Generation ----------
    @staticmethod
    def create_html_report(feedback, student_name, output_file):
        """
        Generate an HTML report with embedded CSS styling.
        """
        css = """
        <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f8f9fa; }
        .report-container { background-color: #fff; border: 1px solid #ccc; padding: 20px; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        table, th, td { border: 1px solid #000; }
        th { background-color: #D9E1F2; padding: 8px; text-align: center; }
        td { background-color: #F2F2F2; padding: 8px; text-align: left; }
        </style>
        """
        html_body = markdown.markdown(feedback, extensions=['tables','fenced_code'])
        full_html = (
            f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Feedback Report</title>{css}</head>"
            f"<body><h2>{student_name}</h2><div class='report-container'>{html_body}</div>"
            f"</body></html>"
        )
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(full_html)