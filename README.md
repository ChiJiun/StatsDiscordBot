# Discord 統計學 FRQ 智慧評分 Bot

這個專案是一個以 Discord 為核心的統計學 FRQ 批改系統。學生可以在指定的 Discord 班級頻道中，使用學號與密碼登入後上傳 HTML 作答檔案；系統會自動解析題目、讀取學生答案，並透過 OpenAI 產生英文表達與統計內容兩個面向的評分回饋。除了批改功能外，系統也會保留提交紀錄、產生 HTML 評分報告，並將檔案同步整理到 Google Drive。

這個專案目前是「長時間運行的 Python Discord Bot」，不是前端網站或一般 Web App。

## 專案特色

- 支援 Discord 帳號登入與班級身分組分配
- 支援多班級頻道管理
- 根據題目標題對應不同 Prompt 進行評分
- 提供英文表達與統計內容雙重回饋
- 記錄學生歷次提交與作答次數
- 自動產生 HTML 評分報告
- 使用 SQLite 儲存學生、班級與提交資料
- 將原始作答檔與報告同步上傳至 Google Drive
- 提供管理員指令，例如開關批改、更新歡迎訊息與匯出成績

## 系統流程

1. 學生在 Discord 使用 `!login 學號 密碼` 登入
2. 系統依照資料庫中的班級資料綁定學生 Discord 帳號
3. 學生在對應班級頻道上傳 `.html` 作答檔案
4. 系統解析 HTML 內的題目標題、學生資訊與作答內容
5. 依題目標題載入對應的英文與統計評分 Prompt
6. 呼叫 OpenAI 產生回饋內容
7. 產生 HTML 評分報告
8. 將提交紀錄與解析後的分數寫入 SQLite
9. 將作答檔與報告儲存到本地資料夾並同步上傳到 Google Drive

## 專案結構

```text
Bot/
├── main.py                    # 專案入口
├── discord_bot.py             # Discord Bot 核心邏輯
├── config.py                  # 環境變數與系統設定
├── database.py                # SQLite 資料庫操作
├── grading.py                 # OpenAI 評分邏輯
├── html_parser.py             # HTML 解析工具
├── file_handler.py            # 本地檔案與 Google Drive 上傳
├── report_generator.py        # HTML 報告生成器
├── requirements.txt           # Python 套件需求
├── .env.example               # 環境變數範例
├── homework.db                # SQLite 資料庫
├── prompts/                   # 各題目的評分 Prompt
├── Question/                  # 題目檔案
├── Answer/                    # 參考解答檔案
├── Course List/               # 課程名單 Excel
├── uploads/                   # 學生上傳作答檔
├── reports/                   # 產生的評分報告
└── script/
    ├── oauth_setup.py         # Google Drive OAuth 初始化
    └── student_importer.py    # 匯入學生資料
```

## 執行需求

- Python 3.10 以上
- Discord Bot Token
- OpenAI API Key
- Google Cloud OAuth 用戶端憑證
- 可存取目標 Discord 伺服器、頻道與身分組的權限

## 安裝方式

### Windows

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 環境變數設定

請在專案根目錄建立 `.env`，可以參考 `.env.example` 填入實際值。

範例：

```env
DISCORD_TOKEN=your_discord_bot_token
OPENAI_API_KEY=your_openai_api_key

UPLOADS_FOLDER_ID=your_google_drive_uploads_folder_id
REPORTS_FOLDER_ID=your_google_drive_reports_folder_id

WELCOME_CHANNEL_ID=your_welcome_channel_id
NCUFN_CHANNEL_ID=your_ncufn_channel_id
NCUEC_CHANNEL_ID=your_ncuec_channel_id
CYCUIUBM_CHANNEL_ID=your_cycuiubm_channel_id
HWIS_CHANNEL_ID=your_hwis_channel_id

ADMIN_CHANNEL_ID=your_admin_channel_id
ADMIN_ROLE_ID=your_admin_role_id

NCUFN_ROLE_ID=optional_role_id
NCUEC_ROLE_ID=optional_role_id
CYCUIUBM_ROLE_ID=optional_role_id
HWIS_ROLE_ID=optional_role_id
```

補充說明：

- `config.py` 會自動讀取 `.env`
- 目前模型設定在 [config.py](/c:/Users/USER/OneDrive/Desktop/Stats/code/Bot/config.py:9)，預設為 `gpt-5-mini`
- 資料庫預設使用專案根目錄下的 `homework.db`
- `uploads/` 與 `reports/` 不存在時會自動建立

## Google Drive OAuth 設定

如果你要啟用 Google Drive 上傳功能，需要先在專案根目錄放入 `credentials.json`，接著執行：

```bash
python script/oauth_setup.py
```

執行後會開啟本機 OAuth 授權流程，完成後產生 `token.json`。

Google Drive 功能需要以下檔案：

- `credentials.json`
- `token.json`

## 匯入學生資料

學生名單從 `Course List/` 內的 Excel 檔案匯入。匯入程式會自動嘗試辨識以下欄位：

- 姓名
- 學號
- 密碼
- Discord ID（可選）

執行方式：

```bash
python script/student_importer.py
```

如果 Excel 有多個工作表，系統會優先使用工作表名稱推斷班級名稱。專案目前常見的班級代碼包含：

- `NCUFN`
- `NCUEC`
- `CYCUIUBM`

## 如何啟動專案

在完成以下項目後：

- 已安裝 Python 套件
- 已建立 `.env`
- 已準備 `credentials.json`
- 已完成 OAuth，產生 `token.json`
- 已匯入學生資料

就可以直接啟動 Bot：

```bash
python main.py
```

如果你要強制重新發送歡迎訊息：

```bash
python main.py --force-welcome
```

入口程式在 [main.py](/c:/Users/USER/OneDrive/Desktop/Stats/code/Bot/main.py:1)，會建立 [discord_bot.py](/c:/Users/USER/OneDrive/Desktop/Stats/code/Bot/discord_bot.py:26) 裡的 `HomeworkBot` 並啟動。

## Discord 指令

### 學生可用指令

- `!login 學號 密碼`
- `!my-submissions`
- 在正確的班級頻道直接上傳 `.html` 檔案

### 管理員可用指令

- `!help`
- `!update-welcome`
- `!score 班級 題目`
- `!open`
- `!close`
- `!remove-role-members 身分組名稱`

## 評分流程細節

1. 學生登入 Discord 系統
2. Bot 從資料庫辨識學生班級
3. 學生上傳 HTML FRQ 作答檔案
4. 系統從 HTML 中擷取：
   - 題目標題
   - 學生姓名
   - 學號
   - 作答內容
5. 系統依照 `config.py` 中的 `SPECIFIC_PROMPTS` 載入英文與統計 Prompt
6. OpenAI 產生兩份回饋內容
7. 系統產生 HTML 報告
8. 提交紀錄與解析分數寫入 SQLite
9. 檔案儲存到本地並同步到 Google Drive

## 資料儲存

目前專案使用：

- `homework.db`：儲存 SQLite 資料
- `uploads/`：儲存原始上傳檔
- `reports/`：儲存 HTML 評分報告
- Google Drive：雲端整理作答檔與報告

資料庫主要保存：

- 班級資料
- 學生資料
- 提交紀錄
- 歷次作答次數
- 解析後的成績資料

## 常見問題

### Bot 無法啟動

- 檢查 `.env` 是否存在
- 檢查 `DISCORD_TOKEN` 是否正確
- 確認依賴套件已安裝
- 如果有啟用 Google Drive，上傳功能請確認 `credentials.json` 與 `token.json` 存在

### 學生無法登入

- 確認學生資料已匯入
- 檢查 `homework.db` 是否已有對應的學號與密碼

### 無法評分

- 檢查 HTML 標題是否能對應到 `SPECIFIC_PROMPTS`
- 確認 `OPENAI_API_KEY` 是否有效
- 查看終端輸出是否有 OpenAI timeout 或 prompt 讀取錯誤

### Google Drive 上傳失敗

- 重新執行 `python script/oauth_setup.py`
- 確認 `UPLOADS_FOLDER_ID` 與 `REPORTS_FOLDER_ID` 設定正確
- 確認 `token.json` 沒有過期或授權不完整

## 部署建議

這個專案適合部署在可長時間運行的 VM 或 Docker 環境，因為它依賴：

- 長時間維持的 Discord 連線
- 本地檔案儲存
- SQLite 資料庫
- Google OAuth 憑證

因此它比起無狀態的前端託管平台，更適合部署在持久化伺服器上。

## License

目前此專案尚未定義授權條款。
