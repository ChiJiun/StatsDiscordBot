from bs4 import BeautifulSoup

def extract_html_title(file_path):
    """
    解析 HTML 檔案，提取標題
    優先順序：<title> > <h1> > 預設值

    Args:
        file_path (str): HTML 檔案路徑

    Returns:
        str: HTML 標題
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
    
    # 如果都沒有找到，返回預設值
    return "未知標題"

def extract_html_content(file_path):
    """
    解析 HTML 檔案，提取學生資訊和作答內容

    Args:
        file_path (str): HTML 檔案路徑

    Returns:
        tuple: (學生姓名, 學生學號, 作答內容)
    """
    with open(file_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # 提取姓名與學號 - 尋找特定的 label 標籤
    name_label = soup.find("label", string="姓名：")
    id_label = soup.find("label", string="學號：")

    # 獲取 label 後面的 span 標籤內容
    student_name = name_label.find_next("span").get_text(strip=True) if name_label else "未知"
    student_id = id_label.find_next("span").get_text(strip=True) if id_label else "未知"

    # 提取作答內容 - 尋找作答區域
    answer_label = soup.find("label", string="作答區：")
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
        answer_text = ""

    return student_name, student_id, answer_text
