import json
import re
import openai
import os
import datetime
import docx
import markdown
from config import OPENAI_API_KEY, MODEL, DEFAULT_PROMPTS, SPECIFIC_PROMPTS


class GradingService:
    @staticmethod
    def get_grading_prompts(question_title=None):
        """
        Get grading prompts from config.py based on question title
        Args:
            question_title (str, optional): The title of the question/homework
        Returns: 
            (eng_prompt, stat_prompt)
        """
        # 如果沒有提供題目標題，使用預設 prompt
        if not question_title:
            eng_prompt_file = DEFAULT_PROMPTS.get('eng', '')
            stat_prompt_file = DEFAULT_PROMPTS.get('stats', '')
        else:
            # 根據題目標題查找對應的 prompt 檔案
            stat_prompt_file = SPECIFIC_PROMPTS.get(question_title)
            
            if not stat_prompt_file:
                # 如果找不到特定 prompt，使用預設
                print(f"⚠️ 題目 '{question_title}' 沒有對應的 prompt，使用預設 Stats prompt")
                stat_prompt_file = DEFAULT_PROMPTS.get('stats', '')
            else:
                print(f"✅ 使用題目專屬 prompt: {question_title}")
            
            # 英文 prompt 始終使用預設
            eng_prompt_file = DEFAULT_PROMPTS.get('eng', '')
        
        # 讀取 prompt 檔案內容
        eng_prompt = GradingService._read_prompt_file(eng_prompt_file)
        stat_prompt = GradingService._read_prompt_file(stat_prompt_file)
        
        if not eng_prompt or not stat_prompt:
            raise RuntimeError("無法讀取 prompt 檔案，請檢查 config.py 中的檔案路徑設定。")
        
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
            return ""
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                print(f"✅ 成功讀取 prompt 檔案: {file_path} ({len(content)} 字元)")
                return content
        except Exception as e:
            print(f"❌ 讀取 prompt 檔案時發生錯誤: {e}")
            return ""

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
    def generate_feedback(messages, model=None, temperature=1.0):
        """
        Call OpenAI ChatCompletion API to generate feedback.
        """
        if model is None:
            model = MODEL
            
        openai.api_key = OPENAI_API_KEY
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=temperature
        )
        return response.choices[0].message.content

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

    # ---------- Processing Functions ----------
    @staticmethod
    def process_student_file(file_path, class_name, question_title=None):
        """
        Process a single student file and generate both English and Statistics feedback
        """
        eng_prompt, stat_prompt = GradingService.get_grading_prompts(question_title)
        if not eng_prompt or not stat_prompt:
            raise RuntimeError("請先在 config.py 中設定英文與統計 Prompt。")
        
        name, answer = GradingService.extract_student_data(file_path)
        safe = "".join(c for c in name if c.isalnum() or c in (' ','_')).rstrip()
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base_dir = "output_reports"
        eng_dir = os.path.join(base_dir, f"{class_name}_EN_feedback")
        stat_dir = os.path.join(base_dir, f"{class_name}_STAT_feedback")
        os.makedirs(eng_dir, exist_ok=True)
        os.makedirs(stat_dir, exist_ok=True)
        
        # English feedback
        msgs_e = GradingService.create_messages(eng_prompt, name, answer)
        fb_e = GradingService.generate_feedback(msgs_e)
        out_e = os.path.join(eng_dir, f"{safe}_{ts}_EN.html")
        GradingService.create_html_report(fb_e, name, out_e)
        
        # Statistics feedback
        msgs_s = GradingService.create_messages(stat_prompt, name, answer)
        fb_s = GradingService.generate_feedback(msgs_s)
        out_s = os.path.join(stat_dir, f"{safe}_{ts}_STAT.html")
        GradingService.create_html_report(fb_s, name, out_s)

    @staticmethod
    def process_student_files(folder_path, class_name, question_title=None):
        """
        Batch process all .docx files in given folder.
        """
        for fname in os.listdir(folder_path):
            if fname.lower().endswith('.docx'):
                GradingService.process_student_file(
                    os.path.join(folder_path, fname), 
                    class_name, 
                    question_title
                )
