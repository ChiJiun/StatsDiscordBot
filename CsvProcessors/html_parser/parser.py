import os
import re
import pandas as pd
from bs4 import BeautifulSoup

input_folder = "./html_files"
output_excel = "IUBM_feedback_auto.xlsx"
log_file = "parse_log.txt"

OUTPUT_COLUMNS = [
    "檔名", "學號", "姓名", "日期",
    "Task Fulfillment & Disciplinary Logical Structure",
    "Lexical Range & Statistical Terminology",
    "Grammatical Accuracy & Sentence Structure",
    "Clarity & Cohesion",
    "Total Score", "Band Level",
    "Median Position", "Cumulative Frequency",
    "Median Interval", "Conclusion", "Total",
    "Shape", "Outliers", "Center", "Spread", "Total_b",
    "Overall Total"
]

def extract_text(tag):
    return tag.get_text(" ", strip=True) if tag else ""

def parse_html(file_path):
    data = {col: "" for col in OUTPUT_COLUMNS}
    data["檔名"] = os.path.basename(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "lxml")

    # ====== 基本資料 ======
    cover = soup.select_one(".cover h2")
    date = soup.select_one(".cover p")
    if cover:
        full_name = cover.text.strip()
        match = re.search(r"(\d{8,})", full_name)
        data["學號"] = match.group(1) if match else ""
        parts = full_name.split("_")
        data["姓名"] = parts[-1] if len(parts) >= 3 else ""
    data["日期"] = extract_text(date)

    # ====== English Feedback ======
    grading_table = None
    for t in soup.find_all("table"):
        header = extract_text(t.find_previous(["h3", "h2"]))
        if "Grading" in header or "Dimension" in extract_text(t):
            grading_table = t
            break

    if grading_table:
        for row in grading_table.select("tbody tr"):
            tds = row.find_all("td")
            if len(tds) < 2:
                continue
            key = extract_text(tds[0])
            val = extract_text(tds[1])
            if re.search("Task", key, re.I):
                data["Task Fulfillment & Disciplinary Logical Structure"] = val
            elif re.search("Lexical", key, re.I):
                data["Lexical Range & Statistical Terminology"] = val
            elif re.search("Gramma|Sentence", key, re.I):
                data["Grammatical Accuracy & Sentence Structure"] = val
            elif re.search("Clarity|Cohesion", key, re.I):
                data["Clarity & Cohesion"] = val

    # 總分與 CEFR 等級
    for li in soup.find_all("li"):
        text = extract_text(li)
        if "Total Score" in text:
            data["Total Score"] = text.split(":")[-1].strip()
        elif re.search("Band Level", text, re.I):
            match = re.search(r"(CEFR[: ]?\s*[A-C]\d?)", text)
            if match:
                data["Band Level"] = match.group(1).replace("CEFR", "").strip(": ").strip()
            else:
                data["Band Level"] = text.split(":")[-1].strip()

    # ====== Statistical Feedback (a) ======
    part_a = None
    for h in soup.find_all(["h2", "h3"]):
        if re.search(r"Part\s*\(a\)", h.get_text(), re.I):
            part_a = h
            break
    if part_a:
        table = part_a.find_next("table")
        if table:
            for row in table.select("tbody tr"):
                tds = row.find_all("td")
                if len(tds) >= 2:
                    key, val = extract_text(tds[0]), extract_text(tds[1])
                    if "Median Position" in key:
                        data["Median Position"] = val
                    elif "Cumulative" in key:
                        data["Cumulative Frequency"] = val
                    elif "Median Interval" in key:
                        data["Median Interval"] = val
                    elif "Conclusion" in key:
                        data["Conclusion"] = val
                    elif "Total" in key:
                        data["Total"] = val

    # ====== Statistical Feedback (b) ======
    part_b = None
    for h in soup.find_all(["h2", "h3"]):
        if re.search(r"Part\s*\(b\)", h.get_text(), re.I):
            part_b = h
            break
    if part_b:
        table = part_b.find_next("table")
        if table:
            for row in table.select("tbody tr"):
                tds = row.find_all("td")
                if len(tds) >= 2:
                    key, val = extract_text(tds[0]), extract_text(tds[1])
                    if key == "Shape":
                        data["Shape"] = val
                    elif key == "Outliers":
                        data["Outliers"] = val
                    elif key == "Center":
                        data["Center"] = val
                    elif key == "Spread":
                        data["Spread"] = val
                    elif "Total" in key:
                        data["Total_b"] = val
        fb_text = extract_text(part_b.find_next("ul"))
        match = re.search(r"Overall Total[:：]?\s*([\d/ ]+)", fb_text)
        if match:
            data["Overall Total"] = match.group(1).strip()

    # 若完全沒抓到任何內容，記錄到 log
    if all(v == "" for k, v in data.items() if k not in ["檔名"]):
        with open(log_file, "a", encoding="utf-8") as log:
            log.write(f"[WARN] 無資料: {data['檔名']}\n")

    return data

def main():
    all_data = []
    if os.path.exists(log_file):
        os.remove(log_file)

    for filename in os.listdir(input_folder):
        if filename.endswith(".html"):
            try:
                result = parse_html(os.path.join(input_folder, filename))
                all_data.append(result)
            except Exception as e:
                with open(log_file, "a", encoding="utf-8") as log:
                    log.write(f"[ERROR] {filename}: {e}\n")

    df = pd.DataFrame(all_data, columns=OUTPUT_COLUMNS)
    df.to_excel(output_excel, index=False)
    print(f"✅ 匯出完成：{output_excel}")
    print("📄 如有缺資料檔案，請查看 parse_log.txt")

if __name__ == "__main__":
    main()
