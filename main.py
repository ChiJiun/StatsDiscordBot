import sys

if __name__ == "__main__":
    try:
        from discord_bot import HomeworkBot

        # 檢查是否有 --force-welcome 參數
        force_welcome = "--force-welcome" in sys.argv

        bot = HomeworkBot(force_welcome=force_welcome)
        bot.run()

    except ImportError as e:
        print(f"❌ 導入錯誤: {e}")
        print("請確保所有必要的模組和設定檔案都存在且配置正確")
    except Exception as e:  
        print(f"❌ 啟動機器人時發生錯誤: {e}")
