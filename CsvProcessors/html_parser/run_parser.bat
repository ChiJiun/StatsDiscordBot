@echo off
title IUBM HTML Parser
echo ==============================================
echo   IUBM HTML Parser 自動化 Excel 匯出工具
echo ==============================================
echo.

REM 檢查 Python 是否安裝
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未偵測到 Python！
    echo 請先至 https://www.python.org/downloads/ 安裝 Python，
    echo 並勾選 "Add Python to PATH"。
    pause
    exit /b
)

echo ✅ Python 環境檢測完成。
echo.

REM 檢查套件是否已安裝
echo 正在檢查必要套件...
pip install --quiet beautifulsoup4 lxml pandas openpyxl
echo ✅ 套件檢查完成。
echo.

REM 執行主程式
echo 🚀 開始解析 HTML 檔案...
python parser.py

echo.
echo ==============================================
echo ✅ 完成！已輸出：IUBM_feedback_auto.xlsx
echo ==============================================
echo.
pause
