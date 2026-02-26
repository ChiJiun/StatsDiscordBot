import html
import markdown
import os
import datetime
import docx  # 👈 新增：匯入 docx 模組用來讀取 Word 檔

def generate_html_report(
    student_name,
    student_id,
    question_number,
    attempt,
    answer_text,
    eng_feedback,
    stats_feedback,
):
    """
    生成統一格式的 HTML 報告，並自動載入題目與解答 (支援 .docx, .md, .txt)
    """
    # 獲取當前日期
    current_date = datetime.datetime.now().strftime("%Y年%m月%d日")

    def escape_with_br(text: str) -> str:
        """處理文字中的換行符號，轉換為 HTML 格式顯示"""
        placeholder = "__BR__"
        for br_tag in ["<br>", "<br/>", "\n", "<BR/>"]:
            text = text.replace(br_tag, placeholder)
        escaped = html.escape(text)
        return escaped.replace(placeholder, "<br>")

    # ======== 讀取完整題目與完整答案 ========
    base_dir = os.path.dirname(os.path.abspath(__file__))
    question_dir = os.path.join(base_dir, "Question")
    answer_dir = os.path.join(base_dir, "Answer")
    
    problem_statement = "未提供完整題目 (Problem statement not found)"
    model_solution = "未提供完整答案 (Model solution not found)"
    
    safe_title = question_number.strip()
    
    def read_file_content(directory, title):
        """輔助函式：優先讀取 .docx，若無則讀取 .md 或 .txt"""
        # 1. 嘗試讀取 .docx
        docx_path = os.path.join(directory, f"{title}.docx")
        if os.path.exists(docx_path):
            try:
                doc = docx.Document(docx_path)
                # 將 Word 檔內的段落文字合併，並用換行符號隔開
                return "\n\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            except Exception as e:
                print(f"讀取 Word 檔案失敗 {docx_path}: {e}")
                
        # 2. 嘗試讀取 .md 或 .txt
        for ext in [".md", ".txt"]:
            file_path = os.path.join(directory, f"{title}{ext}")
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception as e:
                    print(f"讀取文字檔案失敗 {file_path}: {e}")
        
        return None

    # 讀取題目
    q_content = read_file_content(question_dir, safe_title)
    if q_content:
        problem_statement = q_content
        
    # 讀取答案
    a_content = read_file_content(answer_dir, safe_title)
    if a_content:
        model_solution = a_content

    # 將題目與答案轉換為 HTML (即使是 Word 純文字，經過 Markdown 轉換也能有較好的段落排版)
    problem_html = markdown.markdown(problem_statement, extensions=["tables", "fenced_code"])
    solution_html = markdown.markdown(model_solution, extensions=["tables", "fenced_code"])
    # ==========================================

    # 處理學生作答內容
    safe_answer_text = escape_with_br(answer_text)

    # 處理英文和統計反饋 - 保持 Markdown 格式並轉換為 HTML
    eng_feedback_clean = eng_feedback.strip() if eng_feedback else "暫無評語內容"
    stats_feedback_clean = stats_feedback.strip() if stats_feedback else "暫無評語內容"

    # 將 Markdown 轉換為 HTML（保留表格格式）
    if len(eng_feedback_clean) < 100 or "評分錯誤" in eng_feedback_clean:
        eng_feedback_html = f"<pre>{html.escape(eng_feedback_clean)}</pre>"
    else:
        eng_feedback_html = markdown.markdown(eng_feedback_clean, extensions=["tables", "fenced_code"])

    if len(stats_feedback_clean) < 100 or "評分錯誤" in stats_feedback_clean:
        stats_feedback_html = f"<pre>{html.escape(stats_feedback_clean)}</pre>"
    else:
        stats_feedback_html = markdown.markdown(stats_feedback_clean, extensions=["tables", "fenced_code"])

    print(f"生成評分報告 - 英語評語長度: {len(eng_feedback_clean)}, 統計評語長度: {len(stats_feedback_clean)}")

    html_template = f"""<!doctype html><html><head><meta charset='utf-8'><style>
      body{{font-family:sans-serif;margin:0;padding:0;background:#f4f4f4}}
      .container{{max-width:800px;margin:50px auto;background:#fff;
                 padding:30px;box-shadow:0 0 10px rgba(0,0,0,0.1)}}
      header,footer{{text-align:center;color:#555}}
      .cover{{text-align:center;padding:80px 0}}
      .cover h2{{font-size:2.2em;color:#4a7ebb;margin-bottom:.5em}}
      .toc{{margin:30px 0}}
      .toc ol{{padding-left:1.2em}}
      h2.section{{border-bottom:2px solid #4a7ebb;padding-bottom:.3em;margin-top:2em}}
      @media print{{.page-break{{page-break-after:always}}}}
      table {{
          width: 100%;
          border-collapse: collapse;
          margin: 20px 0;
        }}
        table, th, td {{
          border: 1px solid #666;
        }}
        th {{
          background-color: #dae4f4;
          padding: 8px;
          text-align: center;
        }}
        td {{
          background-color: #f2f2f2;
          padding: 8px;
          text-align: left;
        }}
        .report-container {{
          background-color: #fff;
          padding: 20px;
        }}
        .content-box {{
          background: #f9f9f9; 
          padding: 15px; 
          margin: 20px 0;
        }}
        /* 使用不同顏色左側邊框來區分區塊 */
        .box-problem {{ border-left: 4px solid #e67e22; }}
        .box-student {{ border-left: 4px solid #4a7ebb; white-space: pre-wrap; }}
        .box-solution {{ border-left: 4px solid #27ae60; }}
    </style>

<title>{student_id} 回饋報告</title></head><body>
<div class="container">
  <header><h1>{question_number} 綜合回饋報告</h1></header>
  <div class="cover"><h2>{student_id}_{student_name}</h2><p>{current_date}</p></div>
  <div class="toc"><strong>目錄</strong><ol>
    <li>一、完整題目 (Problem Statement)</li>
    <li>二、學生原始作答 (Student Answer)</li>
    <li>三、完整解答 (Model Solution)</li>
    <li>四、English Feedback</li>
    <li>五、Statistical Feedback</li></ol></div>
    
<h2 class="section">一、完整題目 (Problem Statement)</h2>
<div class="content-box box-problem report-container">
{problem_html}
</div>

<h2 class="section">二、學生原始作答 (Student Answer)</h2>
<p><strong>學生姓名：</strong>{student_name}</p>
<p><strong>學號：</strong>{student_id}</p>
<p><strong>題目：</strong>{question_number}</p>
<p><strong>作答次數：</strong>第{attempt}次</p>
<div class="content-box box-student">
{safe_answer_text}
</div>

<h2 class="section">三、完整解答 (Model Solution)</h2>
<div class="content-box box-solution report-container">
{solution_html}
</div>
<div class="page-break"></div>

<h2 class="section">四、English Feedback</h2>
<body><div class="report-container">{eng_feedback_html}</div></body>
<div class="page-break"></div>

<h2 class="section">五、Statistical Feedback</h2>
<body><div class="report-container">{stats_feedback_html}</div></body>
</div></body></html>"""

    return html_template