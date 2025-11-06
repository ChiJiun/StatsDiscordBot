# 📊 統計學智慧評分系統 Discord Bot

## Statistics AI Grading System

> 一個基於 Discord 的智慧作業評分系統，提供自動化的英語表達和統計內容雙向評分。
>
> An intelligent homework grading system based on Discord, providing automated dual assessment for English expression and statistical content.

---

## 🌟 功能特色 / Features

- ✅ **自動評分系統** / Automated Grading

  - 英語表達評分 (English Expression)
  - 統計內容評分 (Statistical Content)
  - AI 驅動的詳細反饋 (AI-driven Detailed Feedback)
- 👥 **多班級管理** / Multi-Class Management

  - 支援三個班級：NCUFN、NCUEC、CYCUIUBM
  - 獨立的班級頻道 (Separate Class Channels)
  - 班級統計分析 (Class Statistics)
- 🔐 **身分驗證系統** / Authentication System

  - Discord 身分組管理 (Role Management)
  - 學號密碼登入 (Student ID & Password Login)
  - Discord 帳號綁定 (Discord Account Binding)
- 📝 **作業追蹤** / Assignment Tracking

  - 多次提交記錄 (Multiple Submission History)
  - 詳細評分報告 (Detailed Grading Reports)
  - 進度統計 (Progress Statistics)

---

## 📋 系統需求 / Requirements

- Python 3.8 或更高版本 / Python 3.8+
- Discord Bot Token
- OpenAI API Key (用於 AI 評分)

---

## 🚀 快速開始 / Quick Start

### 1️⃣ 安裝依賴 / Install Dependencies

```bash
pip install -r requirements.txt
```

### 2️⃣ 配置設定 / Configuration

根目錄匯入.env token.json credentials.json
Csvprocessors/password_importer 準備各班資料夾

### 3️⃣ 初始化資料庫 / Initialize Database

```bash
python database.py
```

這會創建必要的資料表並顯示資料庫管理選單。

### 4️⃣ (可選) 導入學生密碼 / Import Student Passwords

準備密碼檔案（格式：`學號_姓名.txt`，內容為密碼）：

```bash
python CsvProcessors/password_importer/password_importer.py
```

### 5️⃣ 導入學生資料 / Import Student Data

準備班級清單 Excel 檔案（放在 `Course List` 資料夾）：

- `course list.xlsx` (包含 NCUFN、NCUEC、CYCUIUBM 三個工作表)

執行導入腳本：

```bash
python CsvProcessors/student_importer.py
```

### 6️⃣ 啟動機器人 / Start the Bot

正常啟動：

```bash
python main.py
```

強制更新歡迎訊息：

```bash
python main.py --force-welcome
```

---

## 📁 專案結構 / Project Structure

```bash
Bot/
├── main.py                          # 主程式入口
├── discord_bot.py                   # Discord 機器人核心
├── database.py                      # 資料庫管理
├── grading.py                       # AI 評分服務
├── html_parser.py                   # HTML 解析器
├── file_handler.py                  # 檔案處理器
├── config.py                        # 配置檔案（需自行創建）
├── requirements.txt                 # Python 依賴套件
├── homework_bot.db                  # SQLite 資料庫（自動生成）
│
├── Course List/                     # 課程清單資料夾
│   └── course list.xlsx            # 學生名單（三個工作表）
│
├── CsvProcessors/                   # 資料處理工具
│   ├── student_importer.py         # 學生資料導入
│   └── password_importer/          # 密碼導入工具
│       ├── password_importer.py
│       ├── NCUFN/                  # 各班級密碼檔案
│       ├── NCUEC/
│       └── CYCUIUBM/
│
├── uploads/                         # 上傳檔案儲存（自動生成）
│   ├── NCUFN/
│   ├── NCUEC/
│   └── CYCUIUBM/
│
└── reports/                         # 評分報告儲存（自動生成）
    ├── NCUFN/
    ├── NCUEC/
    └── CYCUIUBM/
```

---

## 🎮 使用指南 / User Guide

### 學生使用流程 / Student Workflow

1. **加入身分組** (在歡迎頻道)

   ```bash
   !join NCUFN    # 中央大學財金系
   !join NCUEC    # 中央大學經濟系
   !join CYCUIUBM # 中原大學國商學程
   ```
2. **登入系統** (在班級頻道)

   ```bash
   !login 學號 密碼
   ```
3. **上傳作業**

   - 直接拖拽 `.html` 檔案到班級頻道
   - 系統會自動評分並私訊結果
4. **查看記錄**

```bash
!my-submissions  # 查看作業記錄
!class-stats     # 查看班級統計
```

### 管理員指令 / Admin Commands

```bash
!class-list              # 查看所有班級
!student-list 班級名稱    # 查看學生清單
!update-welcome          # 更新歡迎訊息
```

### 完整指令列表 / Complete Command List

```bash
!help              # 顯示幫助訊息
!join <學校代碼>    # 加入身分組
!login 學號 密碼    # 登入系統
!my-roles          # 查看我的身分
!class-stats       # 查看班級統計
!my-submissions    # 查看作業記錄
```

---

## 🗄️ 資料庫結構 / Database Schema

### Classes (班級表)

```sql
class_id        INTEGER PRIMARY KEY
class_name      VARCHAR(50) UNIQUE
created_at      DATETIME
```

### Students (學生表)

```sql
student_id      INTEGER PRIMARY KEY
student_name    VARCHAR(100)
student_number  VARCHAR(50)
discord_id      VARCHAR(20) UNIQUE
class_id        INTEGER
password        VARCHAR(50)
created_at      DATETIME
updated_at      DATETIME
```

### AssignmentFiles (作業檔案表)

```sql
file_id         INTEGER PRIMARY KEY
student_id      VARCHAR(20)
class_id        INTEGER
file_path       VARCHAR(500)
question_number INTEGER
attempt_number  INTEGER
score           REAL
feedback        TEXT
upload_time     DATETIME
```

---

## 🔧 開發工具 / Development Tools

### 資料庫管理工具

```bash
python database.py
```

提供以下功能：

- 查看資料庫統計
- 管理班級和學生
- 檢查資料完整性

### 學生資料導入

```bash
python CsvProcessors/student_importer.py
```

### 密碼導入

```bash
python CsvProcessors/password_importer/password_importer.py
```

---

## 📊 評分系統 / Grading System

### 評分標準 / Grading Criteria

- **英語表達 (English Expression)**: 40%

  - 文法正確性 (Grammar)
  - 詞彙使用 (Vocabulary)
  - 表達清晰度 (Clarity)
- **統計內容 (Statistical Content)**: 60%

  - 概念理解 (Concept Understanding)
  - 計算準確性 (Calculation Accuracy)
  - 解釋完整性 (Interpretation Completeness)

### 評分等級 / Grading Levels

- A (90-100): 優秀 / Excellent
- B (80-89): 良好 / Good
- C (70-79): 及格 / Pass
- D (60-69): 需改進 / Needs Improvement
- F (0-59): 不及格 / Fail

---

## 🛠️ 疑難排解 / Troubleshooting

### 常見問題 / Common Issues

**Q: 機器人無法啟動？**

- 檢查 `config.py` 是否正確配置
- 確認 Discord Token 有效
- 檢查 Python 版本是否 >= 3.8

**Q: 無法上傳作業？**

- 確認已完成登入或加入身分組
- 檢查是否在正確的班級頻道
- 確認檔案格式為 `.html`

**Q: 評分失敗？**

- 檢查 OpenAI API Key 是否有效
- 確認 API 配額是否充足
- 查看機器人控制台的錯誤訊息

**Q: 學生資料導入失敗？**

- 確認 Excel 檔案格式正確
- 檢查工作表名稱是否為 NCUFN、NCUEC、CYCUIUBM
- 確認必要欄位（Student ID、Name、Password）存在

## 📮 聯絡方式 / Contact

如有問題或建議，請聯繫系統管理員。

## ⚠️ 注意事項 / Important Notes

1. **資料安全**：請妥善保管 `config.py` 和資料庫檔案
2. **API 配額**：注意 OpenAI API 的使用配額
3. **備份**：定期備份 `homework_bot.db` 資料庫
4. **隱私**：學生資料僅用於評分系統，請遵守隱私規範
