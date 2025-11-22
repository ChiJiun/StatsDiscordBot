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