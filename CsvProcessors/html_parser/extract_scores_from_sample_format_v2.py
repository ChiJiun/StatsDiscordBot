# extract_scores_from_sample_format_v2.py
"""
改良版：更精準地抓取 'Overall Total' 或文件末端的總分 (e.g. 20/40)
用法：
    python extract_scores_from_sample_format_v2.py <html_folder> <output.xlsx>
依賴：
    pip install beautifulsoup4 lxml pandas openpyxl
"""
import sys, os, re
from bs4 import BeautifulSoup
import pandas as pd

SCORE_REGEX = re.compile(r'(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)')
NCUEC_REGEX = re.compile(r'NCUEC[_\-]?(\d{5,12})[_\-]?([\u4e00-\u9fff\w\s\-]+)', re.UNICODE | re.IGNORECASE)
FALLBACK_ID_REGEX = re.compile(r'\b(\d{6,10})\b')

def extract_id_name_from_text(text):
    if not text:
        return (None, None)
    m = NCUEC_REGEX.search(text)
    if m:
        sid = m.group(1).strip()
        name = m.group(2).strip().strip('_- ')
        name = name.replace('_',' ').strip()
        return (sid, name)
    m2 = FALLBACK_ID_REGEX.search(text)
    if m2:
        sid = m2.group(1)
        m_name = re.search(r'[\u4e00-\u9fff]{2,6}', text)
        name = m_name.group(0) if m_name else ''
        return (sid, name)
    return (None, None)

def extract_overall_score_from_soup(soup):
    """
    更穩定的策略：
      1) 取得全文文字 full_text（保留順序）
      2) 找出所有 score matches 與其在 full_text 的位置
      3) 找出所有包含 'overall' 或 'overall total' 的 label 位置（取最後一個 if 多個）
      4) 如果找到 label，選擇 label 之後最近的 score（within window_chars）
      5) 如果沒找到 label，回傳全文中最後一個 score（通常是總分）
    """
    full_text = soup.get_text(separator=' ', strip=True)
    if not full_text:
        return ('', '','')

    # 所有 score matches（記錄 start index）
    scores = []
    for m in SCORE_REGEX.finditer(full_text):
        scores.append((m.start(), m.group(1), m.group(2), m.group(0)))

    # 找 label 位置（找最後一個包含 'overall' 的位置）
    lower = full_text.lower()
    label_keywords = ['overall total', 'overall total:', 'overall:','overall total -','overall']
    label_positions = []
    for kw in label_keywords:
        start = 0
        while True:
            idx = lower.find(kw, start)
            if idx == -1:
                break
            label_positions.append(idx)
            start = idx + 1
    # 選最後一個 label（代表文件後段的 Overall）
    label_pos = max(label_positions) if label_positions else None

    window_chars = 400  # label 後面搜尋多少字元內找 score（可調）
    if label_pos is not None and scores:
        # 找第一個 start > label_pos 且在 window_chars 內
        for s in scores:
            if s[0] >= label_pos and s[0] <= label_pos + window_chars:
                return (s[3], s[1], s[2])
        # 若找不到在 window 內的，試找 label 之前最接近的 score（fallback）
        prev = None
        for s in scores:
            if s[0] < label_pos:
                prev = s
            else:
                break
        if prev:
            return (prev[3], prev[1], prev[2])

    # 若沒 label 或上述都沒找到，選全文中最後一個 score
    if scores:
        last = scores[-1]
        return (last[3], last[1], last[2])

    return ('', '','')

def process_file(path):
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()
    soup = BeautifulSoup(html, 'lxml')
    full_text = soup.get_text(separator=' ', strip=True)

    sid, name = (None, None)
    h2 = soup.find('h2')
    if h2:
        sid, name = extract_id_name_from_text(h2.get_text(" ", strip=True))
    if not sid and soup.title:
        sid, name = extract_id_name_from_text(soup.title.string or '')
    if not sid:
        sid, name = extract_id_name_from_text(full_text)
    if not sid:
        m = FALLBACK_ID_REGEX.search(full_text)
        if m:
            sid = m.group(1)
            mname = re.search(r'NCUEC[_\-]?' + re.escape(sid) + r'[_\-]?([\u4e00-\u9fff]{2,6})', full_text)
            if mname:
                name = mname.group(1)
            else:
                m2 = re.search(r'[\u4e00-\u9fff]{2,6}', full_text)
                name = m2.group(0) if m2 else ''

    overall_score, obtained, total = extract_overall_score_from_soup(soup)

    return {
        'filename': os.path.basename(path),
        'student_id': sid or '',
        'name': name or '',
        'overall_score': overall_score or '',
        'score_obtained': obtained or '',
        'score_total': total or ''
    }

def main():
    if len(sys.argv) != 3:
        print("Usage: python extract_scores_from_sample_format_v2.py <html_folder> <output.xlsx>")
        sys.exit(1)
    folder = sys.argv[1]
    out_xlsx = sys.argv[2]
    if not os.path.isdir(folder):
        print("Error: 指定的資料夾不存在:", folder)
        sys.exit(1)

    records = []
    files = sorted([f for f in os.listdir(folder) if f.lower().endswith('.html') or f.lower().endswith('.htm')])
    if not files:
        print("資料夾內找不到 .html 檔")
        sys.exit(0)

    for fn in files:
        path = os.path.join(folder, fn)
        try:
            rec = process_file(path)
            records.append(rec)
            print(f"處理: {fn} -> id: {rec['student_id'] or 'NOT FOUND'}, name: {rec['name'] or 'NOT FOUND'}, score: {rec['overall_score'] or 'NOT FOUND'}")
        except Exception as e:
            print(f"Error 處理 {fn}: {e}")
            records.append({'filename': fn, 'student_id': '', 'name': '', 'overall_score': '', 'score_obtained':'', 'score_total':'', 'error': str(e)})

    df = pd.DataFrame(records, columns=['filename','student_id','name','overall_score','score_obtained','score_total'])
    df.to_excel(out_xlsx, index=False)
    print("已輸出到", out_xlsx)

if __name__ == '__main__':
    main()
