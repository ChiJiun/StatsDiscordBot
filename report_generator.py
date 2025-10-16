import html
import markdown


def generate_html_report(
    student_name, student_id, question_number, attempt, answer_text, eng_score, eng_band, eng_feedback, stats_score, stats_band, stats_feedback
):
    """生成美觀的 HTML 格式評分報告"""

    def escape_with_br(text: str) -> str:
        """處理文字中的換行符號，轉換為 HTML 格式顯示"""
        placeholder = "__BR__"
        for br_tag in ["<br>", "<br/>", "\n", "<BR/>"]:
            text = text.replace(br_tag, placeholder)
        escaped = html.escape(text)
        return escaped.replace(placeholder, "<br>")

    safe_answer_text = escape_with_br(answer_text)

    eng_feedback_clean = eng_feedback.strip() if eng_feedback else "暂无评语内容"
    stats_feedback_clean = stats_feedback.strip() if stats_feedback else "暂无评语内容"

    if len(eng_feedback_clean) < 100 or "評分錯誤" in eng_feedback_clean:
        eng_feedback_html = f"<pre>{html.escape(eng_feedback_clean)}</pre>"
    else:
        eng_feedback_html = markdown.markdown(eng_feedback_clean, extensions=["tables", "fenced_code"])

    if len(stats_feedback_clean) < 100 or "評分錯誤" in stats_feedback_clean:
        stats_feedback_html = f"<pre>{html.escape(stats_feedback_clean)}</pre>"
    else:
        stats_feedback_html = markdown.markdown(stats_feedback_clean, extensions=["tables", "fenced_code"])

    print(f"生成評分報告 - 英語評語長度: {len(eng_feedback_clean)}, 統計評語長度: {len(stats_feedback_clean)}")

    html_report = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>統計學智慧評分報告</title>
<style>
/* CSS 樣式保持不變 */
body {{
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    background: linear-gradient(135deg, #e0eafc, #cfdef3);
    color: #2c3e50;
    margin: 40px auto;
    max-width: 960px;
    line-height: 1.75;
    padding: 0 20px;
}}

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

section {{
    background-color: #fff;
    border-radius: 16px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.1);
    padding: 35px 40px;
    margin-bottom: 50px;
}}

.original-answer {{
    font-family: Consolas, "Courier New", monospace;
    font-size: 1rem;
    color: #34495e;
    white-space: pre-wrap;
    border-left: 8px solid #2980b9;
    padding-left: 20px;
    background-color: #f8f9fa;
}}

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

.grading-section.eng .feedback-content {{
    border-left-color: #3498db;
    background-color: #f0f7ff;
}}

.grading-section.stats .feedback-content {{
    border-left-color: #e67e22;
    background-color: #fff8f0;
}}

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
    <h1>📊 統計學智慧評分報告</h1>
    <p style="text-align: center; color: #7f8c8d; margin-bottom: 2em;">
        學生：{student_name} | 學號：{student_id} | 題目：{question_number} | 第 {attempt} 次提交
    </p>
    
    <section class="original-answer">
        <h2>📝 原始作答內容</h2>
        <div>{safe_answer_text}</div>
    </section>
    
    <section class="grading-section eng">
        <h2>🔤 英語表達評分與建議</h2>
        <div class="feedback-content">{eng_feedback_html}</div>
    </section>
    
    <section class="grading-section stats">
        <h2>📈 統計內容評分與建議</h2>
        <div class="feedback-content">{stats_feedback_html}</div>
    </section>
    
    <footer style="text-align: center; margin-top: 3em; color: #95a5a6; font-size: 0.9em;">
        <p>Statistics AI Grading System | 統計學智慧評分系統</p>
    </footer>
</body>
</html>"""

    return html_report
