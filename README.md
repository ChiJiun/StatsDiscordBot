# 統計學 AI 系統 - HTML 作業評分機器人

一個基於 Discord 的智能作業評分系統，專為統計學課程設計，提供自動化的 HTML 作業評分和反饋功能。

## 🎯 專案概述

本系統是一個 Discord 機器人，能夠：

- 自動接收和處理學生提交的 HTML 作業
- 使用 AI 進行英語和統計學雙重評分
- 生成詳細的評分報告
- 管理學生身分組和權限
- 提供完整的資料庫記錄和統計功能

## ✨ 主要功能

### 🎓 身分組管理

- **一次性身分組選擇**：每位學生只能選擇一個身分組，選擇後無法更改
- **支持的身分組**：
  - 🏦 NCUFN - 中央大學財金系
  - 📈 NCUEC - 中央大學經濟系
  - 🌐 CYCUIUBM - 中原大學國際商學學士學位學程

### 📝 作業評分系統

- **自動 HTML 解析**：提取學生姓名、學號和答案內容
- **AI 雙重評分**：
  - 英語評分：評估語言表達和文法
  - 統計評分：評估統計概念和應用
- **詳細反饋**：提供具體的改進建議
- **分數等級**：A+, A, B+, B, C+, C, D 等級制度

### 📊 資料管理

- **完整記錄**：追蹤所有提交記錄和評分歷史
- **統計分析**：提供各種統計資訊和報告
- **資料匯出**：支援 CSV 格式匯出
- **自動備份**：定期資料庫備份功能

### 🔧 系統管理

- **頻道管理**：自動訊息清理，保持頻道整潔
- **權限控制**：管理員專用指令
- **歡迎系統**：新成員自動歡迎訊息更新
- **日誌記錄**：完整的系統操作日誌

## 🏗️ 系統架構

```text
📦 統計學AI系統
├── 🤖 Discord Bot (discord_bot.py)
│   ├── 訊息處理
│   ├── 身分組管理
│   ├── 檔案處理
│   └── 指令系統
├── 🗄️ 資料庫系統 (database.py)
│   ├── 用戶管理
│   ├── 提交記錄
│   ├── 身分組記錄
│   └── 系統日誌
├── 🧠 AI評分服務 (grading.py)
│   ├── OpenAI整合
│   ├── 英語評分
│   └── 統計評分
├── 📄 HTML解析器 (html_parser.py)
│   └── 內容提取
├── 📋 報告生成器 (report_generator.py)
│   └── HTML報告生成
└── ⚙️ 配置管理 (config.py)
    └── 環境變數管理
```

## 🚀 快速開始

### 環境需求

- Python 3.8+
- Discord Bot Token
- OpenAI API Key

### 安裝步驟

1. **克隆專案**

```bash
git clone <repository-url>
cd Stats/code/Bot
```

1. **安裝依賴**

```bash
pip install discord.py aiohttp openai beautifulsoup4
```

1. **配置環境變數**
   創建 `.env` 文件：

```env
DISCORD_TOKEN=your_discord_bot_token
OPENAI_API_KEY=your_openai_api_key
ADMIN_USER_ID=your_discord_user_id
WELCOME_CHANNEL_ID=welcome_channel_id
NCUFN_CHANNEL_ID=ncufn_channel_id
NCUEC_CHANNEL_ID=ncuec_channel_id
CYCUIUBM_CHANNEL_ID=cycuiubm_channel_id
NCUFN_ROLE_ID=ncufn_role_id
NCUEC_ROLE_ID=ncuec_role_id
CYCUIUBM_ROLE_ID=cycuiubm_role_id
```

1. **啟動機器人**

```bash
python main.py
```

1. **強制更新歡迎訊息**（可選）

```bash
python main.py --force-welcome
```

## 📱 使用指南

### 學生使用

#### 1. 選擇身分組

```bash
!join NCUFN    # 加入中央大學財金系
!join NCUEC    # 加入中央大學經濟系
!join CYCUIUBM # 加入中原大學國際商學學士學位學程
```

#### 2. 提交作業

- 直接在指定頻道上傳 `.html` 檔案
- 系統會自動處理並評分
- 評分結果將私訊發送

#### 3. 查看資訊

```bash
!help        # 查看幫助指令
!my-roles    # 查看我的身分組
```

### 管理員使用

#### 1. 系統管理

```bash
!update-welcome  # 更新歡迎訊息
```

#### 2. 資料庫管理

```bash
!db stats    # 查看資料庫統計
!db backup   # 備份資料庫
!db clean    # 清理舊資料
!db export   # 匯出資料
```

## 🐛 故障排除

### 常見錯誤及解決方案

#### AttributeError: 'NoneType' object has no attribute 'get_member'

**問題描述**：用戶在私訊中使用身分組指令時出現此錯誤。

**解決方案**：

- 身分組指令（如 `!join NCUFN`）必須在伺服器頻道中使用，不能在私訊中使用
- 確保機器人已正確加入伺服器且有適當權限
- 檢查機器人的成員意圖（Member Intents）是否已啟用

#### 機器人無回應

**可能原因**：

- Discord Bot Token 錯誤或過期
- 機器人權限不足
- 網路連線問題
- OpenAI API 配額用盡

**檢查步驟**：

1. 驗證 `.env` 檔案中的 Token 是否正確
1. 確認機器人在 Discord 開發者控制台中的狀態
1. 檢查機器人權限設定
1. 查看控制台錯誤訊息

#### 評分功能異常

**可能原因**：

- OpenAI API Key 無效
- API 請求限制
- HTML 檔案格式問題

**解決方法**：

- 檢查 OpenAI API Key 和配額
- 確認 HTML 檔案包含必要的學生資訊
- 查看詳細錯誤日誌

### 系統監控

#### 日誌位置

- 控制台輸出：即時錯誤和狀態訊息
- 資料庫日誌：`system_logs` 表記錄所有系統事件

#### 效能監控

```bash
# 查看機器人記憶體使用量
python -c "import psutil; print(f'Memory: {psutil.virtual_memory().percent}%')"

# 檢查資料庫大小
ls -lh homework.db
```

## 🗄️ 資料庫架構

### 主要資料表

#### users - 用戶資訊

- `discord_user_id`: Discord 用戶 ID
- `username`: 用戶名稱
- `role_group`: 身分組
- `created_at`: 建立時間

#### submissions - 提交記錄

- `discord_user_id`: 提交者 ID
- `student_name`: 學生姓名
- `student_id`: 學號
- `question_number`: 題目編號
- `attempt`: 嘗試次數
- `eng_score`: 英語分數
- `stats_score`: 統計分數
- `overall_score`: 總分
- `status`: 處理狀態

#### role_assignments - 身分組分配

- `discord_user_id`: 用戶 ID
- `role_name`: 身分組名稱
- `assigned_at`: 分配時間
- `is_active`: 是否活躍

### 資料關係

- 一對多：用戶 → 提交記錄
- 一對多：用戶 → 身分組記錄
- 外鍵約束確保資料完整性

## 🔧 配置說明

### 重要設定

- `WELCOME_CHANNEL_ID`: 歡迎頻道，僅用於身分組選擇
- `NCUFN_CHANNEL_ID`: 財金系專用頻道
- `NCUEC_CHANNEL_ID`: 經濟系專用頻道
- `CYCUIUBM_CHANNEL_ID`: 國際商學專用頻道

### 權限設定

機器人需要以下權限：

- 讀取訊息歷史
- 發送訊息
- 管理訊息（刪除）
- 添加反應
- 管理身分組
- 上傳檔案

## 📊 評分標準

### 英語評分

- 語法正確性
- 詞彙使用
- 表達清晰度
- 學術寫作風格

### 統計評分

- 概念理解
- 計算正確性
- 解釋合理性
- 專業術語使用

### 分數等級

- A+ (90-100): 優秀
- A (85-89): 良好
- B+ (80-84): 中上
- B (75-79): 中等
- C+ (70-74): 中下
- C (65-69): 及格
- D (0-64): 不及格

## 🛠️ 開發指南

### 程式碼結構

```python
class HomeworkBot:
    def __init__(self):          # 初始化
    async def on_ready(self):    # 機器人啟動
    async def on_message(self):  # 訊息處理
    async def on_member_join(self): # 新成員加入
```

### 錯誤處理最佳實踐

1. **檢查 Guild 存在性**：在處理伺服器相關操作前檢查 `message.guild`
2. **適當的錯誤回饋**：向用戶提供清楚的錯誤訊息
3. **日誌記錄**：記錄所有重要操作和錯誤
4. **防護性編程**：使用 try-except 包裝可能失敗的操作

### 新增功能

1. 在 `discord_bot.py` 中添加指令處理
1. 在 `database.py` 中添加資料存取方法
1. 更新 `config.py` 中的設定項目
1. 測試功能並更新文檔
1. **新增錯誤處理**：確保所有新功能都有適當的錯誤處理

### 資料庫遷移

```python
# 備份現有資料庫
db.backup_database()

# 執行遷移腳本
# 更新資料庫架構
```

### 除錯技巧

#### 啟用詳細日誌

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

#### 測試環境設定

1. 建立測試用 Discord 伺服器
1. 使用測試用 API Keys
1. 隔離測試資料庫

## 📋 常見問題

### Q: 如何重置用戶的身分組？

A: 目前系統設計為一次性選擇，如需重置請聯繫系統管理員手動處理。

### Q: 支援哪些檔案格式？

A: 目前僅支援 `.html` 格式的作業檔案。

### Q: 評分需要多長時間？

A: 通常在 30 秒到 2 分鐘內完成，取決於檔案大小和 AI 服務回應時間。

### Q: 如何查看歷史提交記錄？

A: 使用 `!my-submissions` 指令查看個人提交歷史。

### Q: 為什麼在私訊中使用指令沒有反應？

A: 身分組相關指令必須在伺服器頻道中使用，私訊中僅支援查看類指令（如 `!help`, `!my-roles`）。

### Q: 機器人突然停止工作怎麼辦？

A:

1. 檢查控制台是否有錯誤訊息
1. 確認網路連線正常
1. 重新啟動機器人
1. 檢查 Discord 和 OpenAI 服務狀態

## 🔄 更新日誌

### v1.1.0 (2024-01-XX)

- 🐛 修復私訊指令錯誤
- ✅ 改善錯誤處理機制
- 📝 更新故障排除文檔
- 🔧 優化系統穩定性

### v1.0.0 (2024-01-XX)

- ✅ 基礎 Discord 機器人功能
- ✅ HTML 作業處理和評分
- ✅ 身分組管理系統
- ✅ 資料庫記錄和統計
- ✅ AI 評分整合

## 🤝 貢獻指南

1. Fork 專案
1. 建立功能分支 (`git checkout -b feature/AmazingFeature`)
1. 提交變更 (`git commit -m 'Add some AmazingFeature'`)
1. 推送到分支 (`git push origin feature/AmazingFeature`)
1. 開啟 Pull Request

## 📄 授權協議

本專案採用 MIT 授權協議 - 詳見 [LICENSE](LICENSE) 文件

## 📞 聯繫方式

- 專案維護者: [您的名稱]
- Email: [您的郵箱]
- Discord: [您的 Discord]

## 🙏 致謝

- OpenAI 提供的 AI 評分服務
- Discord.py 社群的技術支援
- 所有參與測試的師生

---

## 注意事項

- 請確保遵守學校的學術誠信政策
- 本系統僅用於教學輔助，最終成績以教師評定為準
- 定期備份重要資料，避免資料遺失
- **身分組指令必須在伺服器頻道中使用，不支援私訊操作**
