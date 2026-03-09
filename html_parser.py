import re  # ✅ 記得導入 re
from bs4 import BeautifulSoup


def extract_html_title(file_path):
    """
    解析 HTML 檔案，智慧提取作業標題
    """
    with open(file_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # 優先從 <title> 標籤提取標題
    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        return title_tag.get_text(strip=True)

    # 如果沒有 <title> 或內容為空，則從 <h1> 提取
    h1_tag = soup.find("h1")
    if h1_tag and h1_tag.get_text(strip=True):
        return h1_tag.get_text(strip=True)

    return "未知題目"


def extract_html_content(file_path):
    """
    解析 HTML 檔案，提取學生基本資訊和作答內容
    """
    with open(file_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # ✅ 修正：使用正規表達式尋找標籤，忽略冒號前後的空白
    name_label = soup.find("label", string=re.compile(r"姓名\s*[：:]"))
    id_label = soup.find("label", string=re.compile(r"學號\s*[：:]"))

    # 獲取 label 後面的 span 標籤內容
    student_name = name_label.find_next("span").get_text(strip=True) if name_label else "未知姓名"
    student_id = id_label.find_next("span").get_text(strip=True) if id_label else "未知學號"

    # 提取作答內容 - 尋找作答區域
    answer_label = soup.find("label", string=re.compile(r"作答區\s*[：:]"))
    
    if answer_label:
        answer_tag = answer_label.find_next("p")
        if answer_tag:
            # 將 <br> 標籤轉換為換行符號以保留格式
            for br in answer_tag.find_all("br"):
                br.replace_with("\n")
            answer_text = answer_tag.get_text("\n", strip=True)
        else:
            answer_text = ""
    else:
        # 如果找不到 Label，嘗試找 textarea
        textarea = soup.find("textarea")
        if textarea:
            answer_text = textarea.get_text(strip=True)
        else:
                answer_text = ""

    return student_name, student_id, answer_text

import json
import re
from bs4 import BeautifulSoup

def extract_scores_from_html_string(html_content):
    """
    即時解析 HTML 報告內容，提取評分項目與成績
    """
    data = {}
    ordered_keys = []

    def add_data(key, value):
        data[key] = value
        if key not in ordered_keys:
            ordered_keys.append(key)

    def extract_text(tag):
        return tag.get_text(" ", strip=True) if tag else ""

    try:
        soup = BeautifulSoup(html_content, "lxml") # 如果沒有 lxml 可改用 "html.parser"
    except Exception as e:
        print(f"解析 HTML 字串失敗: {e}")
        return {}, []

    # ✅ 修復 1：只抓取 h3 標籤，因為 AI 的評分區塊都是以 ### (h3) 輸出
    # 這樣能完美避開報告預設的 h2 標題 (如一、完整題目、學生姓名等)
    headers = soup.find_all("h3")
    for h in headers:
        header_text = extract_text(h)
        
        # 排除不需要抓取子項目的標題
        if any(x in header_text.lower() for x in ["reference", "overall", "summary", "revised sample"]):
            continue

        # ✅ 修復 2：安全尋找「同一個區塊內」的表格，避免跨區塊誤抓 (取代原本危險的 find_next)
        nxt = h.find_next_sibling()
        table = None
        while nxt and nxt.name not in ['h1', 'h2', 'h3']:
            if nxt.name == 'table':
                table = nxt
                break
            nxt = nxt.find_next_sibling()

        if table:
            rows = table.select("tbody tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    key = extract_text(cols[0])
                    value = extract_text(cols[1]).split('/')[0].strip()

                    ignore_list = ["subitem", "section", "item", "criteria", "grading dimension", "score", "score (out of 5)"]
                    if key.lower() in ignore_list:
                        continue
                    
                    if "total" in key.lower() or "subtotal" in key.lower():
                        # ✅ 修復 3：過濾掉 English Feedback 裡的 Grading Table-Total
                        if "grading table" not in header_text.lower():
                            add_data(f"{header_text}-{key}", value)
                    else:
                        add_data(key, value)

    # 處理 Summary (統計總結表)
    summary_h3 = soup.find("h3", string=re.compile("Summary", re.I))
    if summary_h3:
        nxt = summary_h3.find_next_sibling()
        table = None
        while nxt and nxt.name not in ['h1', 'h2', 'h3']:
            if nxt.name == 'table':
                table = nxt
                break
            nxt = nxt.find_next_sibling()

        if table:
            for row in table.select("tbody tr"):
                cols = row.find_all("td")
                if len(cols) >= 2:
                    k = extract_text(cols[0])
                    if k.lower() in ["section", "subitem", "item", "score"]:
                        continue
                    
                    v = extract_text(cols[1]).split('/')[0].strip()
                    
                    if "total" in k.lower():
                        add_data("Stats_Summary_Total", v)
                    else:
                        # ✅ 修復 4：支援「隱藏獨立表格」功能
                        # 如果總表裡面的分數是純數字(或小數)，代表這是合併進來的成績，才抓下來
                        if v.replace('.', '', 1).isdigit():
                            add_data(k, v)

    # 抓取 Overall 區塊 (區分英文與統計)
    overall_headers = soup.find_all(["h2", "h3"], string=re.compile("Overall", re.I))
    for overall_h in overall_headers:
        container = overall_h.find_next(["ul", "p"])
        if container:
            container_text = extract_text(container)
            is_english = "Band Level" in container_text
            prefix = "English" if is_english else "Stats"

            for li in container.find_all("li"):
                text = extract_text(li)
                if "Total Score" in text:
                    val = text.split(":")[-1].split("/")[0].strip()
                    add_data(f"{prefix}_Total_Score", val)
                elif "Band Level" in text:
                    val = text.split(":")[-1].strip()
                    add_data("Band Level", val)
                    
            if "Total Score:" in container_text and not container.find("li"):
                 val = container_text.split("Total Score:")[-1].split("/")[0].split()[0].strip()
                 add_data(f"{prefix}_Total_Score", val)

    return data, ordered_keys