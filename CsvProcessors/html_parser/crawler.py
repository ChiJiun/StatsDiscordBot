import os
import re
import pandas as pd
from bs4 import BeautifulSoup

# ========= 基本設定 =========
input_folder = "./html_files"
output_excel = "IUBM_feedback_auto_Flexible_Ordered.xlsx"
log_file = "parse_log.txt"

# 定義基本欄位（永遠排在最左邊）
BASE_INFO_COLS = ["日期", "學號", "學生姓名", "題目", "作答次數"]

# ========= 工具函式 =========
def extract_text(tag):
    return tag.get_text(" ", strip=True) if tag else ""

# ========= HTML 解析 =========
def parse_html(file_path):
    data = {}
    ordered_keys = [] # 用來記錄此檔案中欄位出現的「由上往下」順序

    # 加入字典與順序清單的輔助函式
    def add_data(key, value):
        data[key] = value
        if key not in ordered_keys:
            ordered_keys.append(key)

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            soup = BeautifulSoup(f, "lxml")
    except Exception as e:
        raise Exception(f"檔案讀取失敗: {e}")

    # ----- 1. 基本資料 (Cover 區塊) -----
    cover = soup.select_one(".cover h2")
    date_tag = soup.select_one(".cover p")

    if cover:
        cover_text = cover.text.strip()
        if "_" in cover_text:
            parts = cover_text.split("_", 1)
            add_data("學號", parts[0])
            add_data("學生姓名", parts[1])
        else:
            add_data("學號", "格式錯誤")
            add_data("學生姓名", cover_text)

    add_data("日期", extract_text(date_tag))

    for p in soup.find_all("p"):
        t = extract_text(p)
        if t.startswith("題目："):
            add_data("題目", t.replace("題目：", "").strip())
        elif t.startswith("作答次數："):
            add_data("作答次數", t.replace("作答次數：", "").strip())

    # ----- 2. 動態抓取所有表格內容 (由上往下掃描) -----
    headers = soup.find_all(["h2", "h3"])
    for h in headers:
        header_text = extract_text(h)
        
        # 排除不需要的標題
        if any(x in header_text.lower() for x in ["reference", "overall", "summary", "revised sample"]):
            continue

        table = h.find_next("table")
        if table:
            rows = table.select("tbody tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    key = extract_text(cols[0])
                    # 抓取數值並過濾掉分母 (如 "4 / 5" 只取 "4")
                    value = extract_text(cols[1]).split('/')[0].strip()

                    # 過濾掉中英文表格的各種標題列 (包含英文版的 Grading Dimension)
                    ignore_list = ["subitem", "section", "item", "criteria", "grading dimension", "score", "score (out of 5)"]
                    if key.lower() in ignore_list:
                        continue
                    
                    # 如果遇到 Total 或 Subtotal，加上上方標題前綴以防衝突
                    if "total" in key.lower():
                        add_data(f"{header_text}-{key}", value)
                    else:
                        add_data(key, value)

    # ----- 3. 處理 Summary (統計總結表) -----
    # 這是為了防呆，如果 AI 有輸出 Summary 表格，順便把它抓下來
    summary_h3 = soup.find("h3", string=re.compile("Summary", re.I))
    if summary_h3:
        table = summary_h3.find_next("table")
        if table:
            for row in table.select("tbody tr"):
                cols = row.find_all("td")
                if len(cols) >= 2:
                    k = extract_text(cols[0])
                    v = extract_text(cols[1]).split('/')[0].strip()
                    if "total" in k.lower():
                        add_data("Stats_Summary_Total", v)

    # ----- 4. 抓取 Overall 區塊 (區分英文與統計) -----
    overall_headers = soup.find_all(["h2", "h3"], string=re.compile("Overall", re.I))
    for overall_h in overall_headers:
        container = overall_h.find_next(["ul", "p"])
        if container:
            container_text = extract_text(container)
            
            # 判斷這個 Overall 是英文的還是統計的 (英文的會包含 Band Level)
            is_english = "Band Level" in container_text
            prefix = "English" if is_english else "Stats"

            for li in container.find_all("li"):
                text = extract_text(li)
                if "Total Score" in text:
                    # 獨立儲存兩者的總分，並去掉分母
                    val = text.split(":")[-1].split("/")[0].strip()
                    add_data(f"{prefix}_Total_Score", val)
                elif "Band Level" in text:
                    val = text.split(":")[-1].strip()
                    add_data("Band Level", val)
                    
            # 防呆：如果 AI 把結果寫在段落 <p> 裡而不是 <li> 裡
            if "Total Score:" in container_text and not container.find("li"):
                 val = container_text.split("Total Score:")[-1].split("/")[0].split()[0].strip()
                 add_data(f"{prefix}_Total_Score", val)

    return data, ordered_keys

# ========= 主程式 =========
def main():
    all_data = []
    
    # 建立一個全域的順序清單，確保最終 Excel 照這個順序排
    master_ordered_cols = list(BASE_INFO_COLS)

    if os.path.exists(log_file):
        os.remove(log_file)

    if not os.path.exists(input_folder):
        print(f"❌ 找不到資料夾：{input_folder}")
        return

    file_list = [f for f in os.listdir(input_folder) if f.endswith(".html")]
    
    if not file_list:
        print("⚠️ 資料夾內沒有 HTML 檔案。")
        return

    for filename in file_list:
        try:
            result_data, file_ordered_keys = parse_html(os.path.join(input_folder, filename))
            all_data.append(result_data)
            
            # 將這個檔案發現的新欄位，依照發現順序加入全域清單
            for k in file_ordered_keys:
                if k not in master_ordered_cols:
                    master_ordered_cols.append(k)
                    
        except Exception as e:
            with open(log_file, "a", encoding="utf-8") as log:
                log.write(f"[ERROR] {filename}: {e}\n")

    # 將字典列表轉換為 DataFrame
    df = pd.DataFrame.from_records(all_data)

    # 依照 master_ordered_cols (由上往下的出現順序) 來排序欄位
    final_cols = [c for c in master_ordered_cols if c in df.columns]
    df = df[final_cols]

    # 匯出至 Excel
    df.to_excel(output_excel, index=False)
    
    print(f"✅ 匯出完成：{output_excel}")
    print(f"📊 總計處理檔案：{len(all_data)} 份")
    if os.path.exists(log_file):
        print("📄 部分檔案處理有誤，請查看 parse_log.txt")

if __name__ == "__main__":
    main()