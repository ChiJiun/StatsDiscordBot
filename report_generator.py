import html
import markdown


def generate_html_report(
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
):
    """
    生成統一格式的 HTML 報告
    """
    import datetime

    # 獲取當前日期
    current_date = datetime.datetime.now().strftime("%Y年%m月%d日")

    def escape_with_br(text: str) -> str:
        """處理文字中的換行符號，轉換為 HTML 格式顯示"""
        placeholder = "__BR__"
        for br_tag in ["<br>", "<br/>", "\n", "<BR/>"]:
            text = text.replace(br_tag, placeholder)
        escaped = html.escape(text)
        return escaped.replace(placeholder, "<br>")

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
    </style>
<title>{student_id} 回饋報告</title></head><body>
<div class="container">
  <header><h1>{question_number} 綜合回饋報告</h1></header>
  <div class="cover"><h2>{student_id}_{student_name}</h2><p>{current_date}</p></div>
  <div class="toc"><strong>目錄</strong><ol>
    <li>一、學生原始作答</li><li>二、English Feedback</li><li>三、Statistical Feedback</li></ol></div>
<h2 class="section">一、學生原始作答</h2>
<p><strong>學生姓名：</strong>{student_name}</p>
<p><strong>學號：</strong>{student_id}</p>
<p><strong>題目：</strong>{question_number}</p>
<p><strong>作答次數：</strong>第{attempt}次</p>
<div style="white-space: pre-wrap; background: #f9f9f9; padding: 15px; border-left: 3px solid #4a7ebb; margin: 20px 0;">
{safe_answer_text}
</div>
<div class="page-break"></div>
<h2 class="section">二、English Feedback</h2>
<body><div class="report-container">{eng_feedback_html}</div></body>
<div class="page-break"></div>
<h2 class="section">三、Statistical Feedback</h2>
<body><div class="report-container">{stats_feedback_html}</div></body>
<footer><small>第 <span class="pageNumber"></span> 頁</small></footer>
</div></body></html>"""

    return html_template
