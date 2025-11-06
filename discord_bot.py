import os
import discord
import aiohttp
from config import (
    DISCORD_TOKEN,
    UPLOADS_DIR,
    REPORTS_DIR,
    WELCOME_CHANNEL_ID,
    NCUFN_ROLE_NAME,
    NCUEC_ROLE_NAME,
    CYCUIUBM_ROLE_NAME,
    NCUFN_ROLE_ID,
    NCUEC_ROLE_ID,
    CYCUIUBM_ROLE_ID,
)
from database import DatabaseManager
from html_parser import extract_html_content, extract_html_title
from grading import GradingService
from file_handler import FileHandler


class HomeworkBot:
    def __init__(self, force_welcome=False):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        self.client = discord.Client(intents=intents)
        self.db = DatabaseManager()
        self.session = None
        self.grading_service = None
        self.force_welcome = force_welcome

        # 身分組對應班級名稱 - 改為英文
        self.role_to_class = {
            NCUFN_ROLE_NAME: "NCUFN",
            NCUEC_ROLE_NAME: "NCUEC",
            CYCUIUBM_ROLE_NAME: "CYCUIUBM",
        }

        # 班級頻道 ID 設定 (需要在 config.py 中添加)
        try:
            from config import NCUFN_CHANNEL_ID, NCUEC_CHANNEL_ID, CYCUIUBM_CHANNEL_ID

            self.class_channels = {
                "NCUFN": NCUFN_CHANNEL_ID,
                "NCUEC": NCUEC_CHANNEL_ID,
                "CYCUIUBM": CYCUIUBM_CHANNEL_ID,
            }
        except ImportError:
            print("⚠️ 未設定班級頻道 ID，將允許在任何頻道使用")
            self.class_channels = {}

        # 設定事件處理器
        self.client.event(self.on_ready)
        self.client.event(self.on_message)
        self.client.event(self.on_close)

    def _is_class_channel(self, channel_id, user_class=None):
        """檢查是否為班級頻道"""
        if not self.class_channels:
            return True  # 如果沒有設定班級頻道，允許在任何頻道使用

        # 檢查是否為任何班級頻道
        if channel_id in self.class_channels.values():
            # 如果指定了用戶班級，檢查是否為對應的班級頻道
            if user_class and user_class in self.class_channels:
                return channel_id == self.class_channels[user_class]
            # 如果沒有指定用戶班級，任何班級頻道都可以
            return True

        return False

    def _get_user_class_channel_info(self, member):
        """獲取用戶的班級和對應頻道資訊"""
        user_class = self._get_user_class_from_roles(member)
        if user_class and user_class in self.class_channels:
            return user_class, self.class_channels[user_class]
        return user_class, None

    async def on_ready(self):
        """機器人啟動時執行的事件處理器"""
        self.session = aiohttp.ClientSession()
        self.grading_service = GradingService(self.session)
        print(f"✅ HTML作業處理機器人已啟動: {self.client.user}")

        # 初始化班級資料
        await self._initialize_classes()

        # 發送歡迎訊息
        await self._send_welcome_message()

    async def _initialize_classes(self):
        """初始化班級資料"""
        for class_name in self.role_to_class.values():
            class_data = self.db.get_class_by_name(class_name)
            if not class_data:
                class_id = self.db.create_class(class_name)
                print(f"✅ 已創建班級: {class_name} (ID: {class_id})")
            else:
                print(f"📋 班級已存在: {class_name} (ID: {class_data[0]})")

    async def _send_welcome_message(self):
        """發送歡迎訊息到歡迎頻道和所有班級頻道"""
        # 創建歡迎訊息嵌入
        embed = discord.Embed(
            title="🎓 歡迎使用統計學智慧評分系統\nWelcome to Statistics AI Grading System",
            description="✨ **歡迎同學們！請仔細閱讀以下重要提醒**\n"
            "✨ **Welcome! Please read the following important reminders carefully**\n\n"
            "📍 **開始使用前，請先將機器人加入好友**\n"
            "📍 **Before using, please add the bot as a friend**\n\n"
            "💡 **請根據您的學校選擇對應的身分組**\n"
            "💡 **Please choose the role corresponding to your school**",
            color=0x3498DB,
        )

        embed.add_field(name="🏦 中央大學財金系同學 / NCU Finance", value="請使用指令 / Use command: `!join NCUFN`", inline=True)
        embed.add_field(name="📈 中央大學經濟系同學 / NCU Economics", value="請使用指令 / Use command: `!join NCUEC`", inline=True)
        embed.add_field(name="🌐 中原大學國商學程同學 / CYU IUBM", value="請使用指令 / Use command: `!join CYCUIUBM`", inline=True)

        embed.add_field(
            name="📚 系統功能說明 / System Features",
            value="• `!help` - 查看完整指令說明 / View complete instructions\n"
            "• `!login 學號 密碼` - 登入系統 / Login to system\n"
            "• `!my-roles` - 查看我的學校身分 / View my school identity\n"
            "• `!class-stats` - 查看班級學習統計 / View class statistics\n"
            "• **直接上傳作業 HTML 檔案** - 系統會自動評分\n"
            "• **Upload HTML homework file** - Auto grading",
            inline=False,
        )

        embed.set_footer(
            text="Statistics AI Grading System | ⚠️ 提醒：身分選擇後無法更改，請慎重考慮！\nReminder: Role selection cannot be changed, please choose carefully!"
        )

        # 收集所有要發送的頻道 ID（歡迎頻道 + 班級頻道）
        all_channels = {}
        
        # 添加歡迎頻道
        all_channels["Welcome"] = WELCOME_CHANNEL_ID
        
        # 添加班級頻道
        if self.class_channels:
            all_channels.update(self.class_channels)
        else:
            print("⚠️ 未設定班級頻道 ID，只會在歡迎頻道發送")

        # 在所有頻道發送歡迎訊息
        for channel_name, channel_id in all_channels.items():
            try:
                channel = self.client.get_channel(channel_id)
                if not channel:
                    print(f"❌ 找不到頻道 ID: {channel_id} ({channel_name})")
                    continue

                # 如果設定強制更新，先刪除舊的歡迎訊息
                if self.force_welcome:
                    print(f"🔄 強制更新模式：正在刪除 {channel_name} 頻道的舊歡迎訊息...")
                    deleted_count = 0
                    async for message in channel.history(limit=50):
                        if (
                            message.author == self.client.user
                            and message.embeds
                            and len(message.embeds) > 0
                            and (
                                "歡迎使用統計學智慧評分系統" in message.embeds[0].title 
                                or "歡迎來到 HTML 作業評分系統" in message.embeds[0].title
                                or "Welcome to Statistics AI Grading System" in message.embeds[0].title
                            )
                        ):
                            try:
                                await message.delete()
                                deleted_count += 1
                                print(f"✅ 已刪除舊歡迎訊息 #{deleted_count} ({channel_name})")
                            except discord.Forbidden:
                                print(f"❌ 無權限刪除舊訊息 ({channel_name})")
                            except Exception as e:
                                print(f"❌ 刪除舊訊息時發生錯誤 ({channel_name}): {e}")

                    if deleted_count > 0:
                        print(f"🧹 {channel_name} 頻道總共刪除了 {deleted_count} 個舊歡迎訊息")

                # 如果不是強制更新，檢查是否已存在歡迎訊息
                if not self.force_welcome:
                    async for message in channel.history(limit=50):
                        if (
                            message.author == self.client.user
                            and message.embeds
                            and len(message.embeds) > 0
                            and (
                                "歡迎使用統計學智慧評分系統" in message.embeds[0].title 
                                or "歡迎來到 HTML 作業評分系統" in message.embeds[0].title
                                or "Welcome to Statistics AI Grading System" in message.embeds[0].title
                            )
                        ):
                            print(f"✅ {channel_name} 頻道的歡迎訊息已存在，跳過發送")
                            break
                    else:
                        # 如果沒有找到舊訊息，發送新訊息
                        await channel.send(embed=embed)
                        print(f"✅ 歡迎訊息已發送到 {channel_name} 頻道: {channel.name}")
                else:
                    # 強制更新模式，直接發送新訊息
                    await channel.send(embed=embed)
                    print(f"✅ 歡迎訊息已發送到 {channel_name} 頻道: {channel.name}")

            except Exception as e:
                print(f"❌ 發送歡迎訊息到 {channel_name} 頻道時發生錯誤: {e}")

    async def on_message(self, message):
        """處理收到的 Discord 訊息事件"""
        if message.author.bot:
            return

        user_id = str(message.author.id)

        # 檢查是否為私訊 - 直接引導到班級頻道
        if isinstance(message.channel, discord.DMChannel):
            # 檢查是否為登入步驟（保留原有登入功能）
            if hasattr(self, "pending_login") and int(user_id) in self.pending_login:
                if await self._handle_login_step(message):
                    return

            # 對於其他私訊，引導用戶到班級頻道
            await message.author.send(
                "💬 **請勿在私訊中使用系統功能**\n"
                "💬 **Please do not use system features in DM**\n\n"
                "🏫 **請前往您的班級專屬頻道進行以下操作：**\n"
                "🏫 **Please go to your class channel for the following operations:**\n\n"
                "• 使用 `!help` 查看完整功能說明 / Use `!help` to view complete instructions\n"
                "• 使用 `!join 學校代碼` 選擇學校身分 / Use `!join school_code` to choose school identity\n"
                "• 📤 上傳 HTML 作業檔案進行評分 / Upload HTML homework file for grading\n"
                "• 使用其他系統功能 / Use other system features"
            )
            return

        # 獲取用戶的班級和頻道資訊
        member = message.guild.get_member(message.author.id)
        user_class, user_channel_id = self._get_user_class_channel_info(member)

        # 處理加入身分組指令 (只能在歡迎頻道使用)
        if message.content.lower().startswith("!join"):
            if message.channel.id != WELCOME_CHANNEL_ID:
                await message.author.send("❌ 加入身分組指令只能在歡迎頻道使用！\n" "❌ Join role command can only be used in welcome channel!")
                try:
                    await message.delete()
                except:
                    pass
                return

            parts = message.content.split()
            if len(parts) != 2:
                await message.author.send(
                    "❌ 使用方法 / Usage: `!join NCUFN` 或 or `!join NCUEC` 或 or `!join CYCUIUBM`\n"
                    "⚠️ 注意 / Note：每人只能選擇一個身分組！/ Each person can only choose one role!"
                )
                try:
                    await message.delete()
                except:
                    pass
                return

            role_type = parts[1].upper()
            await self._handle_join_role(message, role_type)
            return

        # 檢查是否為歡迎頻道的其他訊息 (除了 !join)
        if message.channel.id == WELCOME_CHANNEL_ID:
            await message.author.send(
                "👋 **歡迎！** 這個頻道專門用來選擇學校身分。\n"
                "👋 **Welcome!** This channel is for choosing school identity.\n\n"
                "請使用 `!join 學校代碼` 來選擇您的身分，完成後請到您的班級頻道使用其他功能。\n"
                "Please use `!join school_code` to choose your identity, then go to your class channel to use other features."
            )
            try:
                await message.delete()
            except:
                pass
            return

        # 檢查是否在正確的班級頻道 (其他所有指令都需要在班級頻道)
        if not self._is_class_channel(message.channel.id, user_class):
            channel_info = ""
            if user_class and user_channel_id:
                channel_info = f"\n🏫 **您的專屬班級頻道 / Your class channel：<#{user_channel_id}>**"
            elif self.class_channels:
                channel_list = "\n".join([f"• {cls}: <#{ch_id}>" for cls, ch_id in self.class_channels.items()])
                channel_info = f"\n🏫 **班級頻道列表 / Class channels：**\n{channel_list}"

            await message.author.send(
                f"📍 **請在正確的頻道使用功能**\n"
                f"📍 **Please use features in the correct channel**{channel_info}\n\n"
                "🔧 **您可以使用的功能 / Available features：**\n"
                "• `!help` - 查看詳細使用指南 / View detailed guide\n"
                "• `!my-roles` - 查看我的學校身分 / View my school identity\n"
                "• `!class-stats` - 查看班級學習統計 / View class statistics\n"
                "• `!my-submissions` - 查看我的作業記錄 / View my submission history\n"
                "• 📤 **上傳 HTML 作業檔案進行智慧評分 / Upload HTML file for AI grading**"
            )
            try:
                await message.delete()
            except:
                pass
            return

        # 處理幫助指令
        if message.content.lower() == "!help":
            is_admin = message.author.guild_permissions.administrator

            help_text = (
                "📖 **統計學智慧評分系統使用指南**\n"
                "📖 **Statistics AI Grading System User Guide**\n\n"
                "🎯 **主要功能 / Main Features**:\n"
                "1. 📤 **上傳作業檔案 / Upload Homework** - 直接拖拽 `.html` 檔案到聊天室，系統會自動評分\n"
                "   Drag `.html` file to chat, system will auto grade\n"
                "2. 📋 `!help` - 顯示這個使用指南 / Show this guide\n"
                "3. 🏫 `!join 學校代碼` - 選擇您的學校身分 (僅限歡迎頻道)\n"
                "   Choose your school identity (welcome channel only)\n"
                "4. 🔑 `!login 學號 密碼` - 使用學號密碼登入系統\n"
                "   Login with student ID and password\n"
                "5. 👤 `!my-roles` - 查看我的學校身分資訊\n"
                "   View my school identity info\n"
                "6. 📊 `!class-stats` - 查看班級學習統計資料\n"
                "   View class learning statistics\n"
                "7. 📝 `!my-submissions` - 查看我的作業提交記錄\n"
                "   View my submission history\n"
            )

            if is_admin:
                help_text += (
                    "\n👑 **管理員專用功能 / Admin Functions**:\n"
                    "• `!class-list` - 查看所有班級資料 / View all classes\n"
                    "• `!student-list 班級名稱` - 查看指定班級學生清單 / View student list\n"
                    "• `!update-welcome` - 更新歡迎訊息 / Update welcome message\n"
                )

            help_text += (
                "\n💡 **溫馨提醒 / Tips**：\n"
                "• 除了選擇學校身分外，所有功能都必須在您的班級專屬頻道中使用\n"
                "  Except role selection, all features must be used in your class channel\n"
                "• 作業評分會同時提供英語表達和統計內容兩個面向的建議\n"
                "  Homework grading provides feedback on both English expression and statistics content\n"
                "• 每次提交都會保留詳細的評分報告供您參考\n"
                "  Each submission's detailed grading report will be saved for your reference"
            )

            await message.author.send(help_text)
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass
            return

        # 處理密碼登入指令
        if message.content.lower().startswith("!login"):
            await self._handle_password_login(message)
            return

        # 管理員專用指令
        if message.author.guild_permissions.administrator:
            # 查看所有班級
            if message.content.lower() == "!class-list":
                await self._show_class_list(message)
                return

            # 查看學生清單
            if message.content.lower().startswith("!student-list"):
                await self._show_student_list(message)
                return

        # 處理查看身分組指令
        if message.content.lower() == "!my-roles":
            await self._show_user_roles(message)
            return

        # 處理班級統計指令
        if message.content.lower() == "!class-stats":
            await self._show_class_stats(message)
            return

        # 處理我的提交記錄指令
        if message.content.lower() == "!my-submissions":
            await self._show_my_submissions(message)
            return

        # 添加管理員指令
        if message.content.lower() == "!update-welcome" and message.author.guild_permissions.administrator:
            try:
                # 收集所有要更新的頻道（歡迎頻道 + 班級頻道）
                all_channels = {"Welcome": WELCOME_CHANNEL_ID}
                if self.class_channels:
                    all_channels.update(self.class_channels)

                # 在所有頻道刪除舊的歡迎訊息
                total_deleted = 0
                for channel_name, channel_id in all_channels.items():
                    channel = self.client.get_channel(channel_id)
                    if channel:
                        deleted_count = 0
                        async for old_message in channel.history(limit=50):
                            if (
                                old_message.author == self.client.user
                                and old_message.embeds
                                and len(old_message.embeds) > 0
                                and (
                                    "歡迎使用統計學智慧評分系統" in old_message.embeds[0].title
                                    or "歡迎來到 HTML 作業評分系統" in old_message.embeds[0].title
                                    or "Welcome to Statistics AI Grading System" in old_message.embeds[0].title
                                )
                            ):
                                try:
                                    await old_message.delete()
                                    deleted_count += 1
                                    print(f"✅ 已刪除 {channel_name} 頻道的舊歡迎訊息 #{deleted_count}")
                                except discord.Forbidden:
                                    print(f"❌ 無權限刪除 {channel_name} 頻道的舊訊息")
                                except Exception as e:
                                    print(f"❌ 刪除 {channel_name} 頻道舊訊息時發生錯誤: {e}")

                        total_deleted += deleted_count
                        if deleted_count > 0:
                            print(f"🧹 {channel_name} 頻道總共刪除了 {deleted_count} 個舊歡迎訊息")

                if total_deleted > 0:
                    await message.author.send(
                        f"🧹 已刪除 {total_deleted} 個舊歡迎訊息（包含歡迎頻道和班級頻道）\n"
                        f"🧹 Deleted {total_deleted} old welcome messages (including welcome channel and class channels)"
                    )
                else:
                    await message.author.send(
                        "ℹ️ 沒有找到需要刪除的舊歡迎訊息\n"
                        "ℹ️ No old welcome messages found to delete"
                    )

                # 強制發送新的歡迎訊息到所有頻道
                self.force_welcome = True
                await self._send_welcome_message()
                self.force_welcome = False

                await message.author.send(
                    "✅ 歡迎訊息已更新！新的歡迎訊息已發送到歡迎頻道和所有班級頻道。\n"
                    "✅ Welcome messages updated! New welcome messages sent to welcome channel and all class channels."
                )

            except Exception as e:
                await message.author.send(
                    f"❌ 更新歡迎訊息時發生錯誤 / Error updating welcome messages：{e}"
                )
                print(f"❌ 更新歡迎訊息錯誤: {e}")

            try:
                await message.delete()
            except:
                pass
            return

        # 處理 HTML 檔案上傳
        if message.attachments:
            # 處理檔案
            for file in message.attachments:
                if file.filename.lower().endswith(".html"):
                    await self._process_html_file(message, file, user_id)
                    return

            # 如果有附件但不是 HTML 檔案
            await message.author.send("❌ 請只上傳 `.html` 檔案進行評分。\n" "❌ Please only upload `.html` files for grading.")
            try:
                await message.delete()
            except:
                pass
            return

        # 自動刪除其他訊息
        try:
            await message.delete()
            await message.author.send(
                "ℹ️ **頻道使用提醒 / Channel Usage Reminder**\n\n"
                "此頻道專門用於系統功能和作業評分。\n"
                "This channel is dedicated to system features and homework grading.\n\n"
                "請使用 `!help` 查看所有可用功能。\n"
                "Please use `!help` to view all available features."
            )
        except (discord.Forbidden, discord.NotFound):
            pass

    async def _process_html_file(self, message, file, user_id):
        """處理 HTML 檔案上傳"""
        try:
            # 檢查檔案類型
            if not file.filename.lower().endswith(".html"):
                await message.author.send(
                    "📄 **檔案格式提醒 / File Format Reminder**\n\n"
                    "請上傳 `.html` 格式的作業檔案。\n"
                    "Please upload homework file in `.html` format.\n\n"
                    "其他格式的檔案無法進行評分處理。\n"
                    "Other formats cannot be processed for grading."
                )
                try:
                    await message.delete()
                except (discord.Forbidden, discord.NotFound):
                    pass
                return

            # 獲取學生資料
            student_data = self.db.get_student_by_discord_id(user_id)
            if not student_data:
                await message.author.send(
                    "🔐 **身分驗證需要 / Identity Verification Required**\n\n"
                    "系統找不到您的學生資料，請先完成以下任一步驟：\n"
                    "System cannot find your student data, please complete one of the following steps:\n\n"
                    "1. 🏫 使用 `!join 學校代碼` 選擇學校身分\n"
                    "   Use `!join school_code` to choose school identity\n"
                    "2. 🔑 使用 `!login 學號 密碼` 登入現有帳戶\n"
                    "   Use `!login student_id password` to login to existing account"
                )
                try:
                    await message.delete()
                except (discord.Forbidden, discord.NotFound):
                    pass
                return

            # 解析學生資料 - 根據實際返回結果調整
            # get_student_by_discord_id 返回：(student_id, student_name, student_number, discord_id, class_id, class_name)
            if len(student_data) == 6:
                db_student_id, db_student_name, student_number, discord_id, class_id, class_name = student_data
            else:
                await message.author.send(f"❌ 學生資料格式錯誤，欄位數量：{len(student_data)}")
                # 刪除上傳訊息
                try:
                    await message.delete()
                except (discord.Forbidden, discord.NotFound):
                    pass
                return

            # 檢查 class_name 是否存在
            if not class_name:
                await message.author.send("❌ 找不到您的班級資料\n" "❌ Cannot find your class data")
                # 刪除上傳訊息
                try:
                    await message.delete()
                except (discord.Forbidden, discord.NotFound):
                    pass
                return

            # 建立安全的檔名
            safe_class_name = self._get_safe_filename(class_name)

            # 使用學號作為資料夾名稱，如果沒有學號則使用 student_id
            folder_name = student_number if student_number else str(db_student_id)
            safe_folder_name = self._get_safe_filename(folder_name)

            # 設定上傳目錄
            uploads_class_dir = os.path.join(UPLOADS_DIR, safe_class_name)
            uploads_student_dir = os.path.join(uploads_class_dir, safe_folder_name)

            # 設定報告目錄
            reports_class_dir = os.path.join(REPORTS_DIR, safe_class_name)
            reports_student_dir = os.path.join(reports_class_dir, safe_folder_name)

            # 確保目錄存在
            os.makedirs(uploads_student_dir, exist_ok=True)
            os.makedirs(reports_student_dir, exist_ok=True)

            # 解析 HTML 內容（先保存到臨時檔案）
            temp_path = os.path.join(UPLOADS_DIR, f"temp_{user_id}_{file.filename}")
            await file.save(temp_path)

            html_title = extract_html_title(temp_path)
            student_name, student_id_from_html, answer_text = extract_html_content(temp_path)

            print(f"📝 HTML 標題: {html_title}")
            print(f"👤 學生姓名: {student_name}")
            print(f"🆔 學號: {student_id_from_html}")
            print(f"📄 答案內容長度: {len(answer_text)} 字元")

            # 檢查是否有答案內容
            if not answer_text or answer_text.strip() == "":
                await message.author.send(
                    "📝 **作業內容檢查 / Homework Content Check**\n\n"
                    "系統在您的 HTML 檔案中沒有找到作答內容。\n"
                    "System did not find any answer content in your HTML file.\n\n"
                    "請確認檔案包含完整的作答區域。\n"
                    "Please ensure the file contains complete answer area."
                )
                os.remove(temp_path)
                return

            # 使用 HTML 標題作為題目標題，如果沒有則使用檔案名稱
            question_title = html_title if html_title else file.filename
            print(f"📝 題目標題: {question_title}")

            # 獲取下一次嘗試編號（使用題目標題）
            max_attempt = self.db.get_max_attempt(user_id, question_title)
            attempt_number = max_attempt + 1

            print(f"🔄 嘗試次數: {attempt_number}")

            # 設定上傳目錄
            uploads_class_dir = os.path.join(UPLOADS_DIR, safe_class_name)
            uploads_student_dir = os.path.join(uploads_class_dir, safe_folder_name)

            # 設定報告目錄
            reports_class_dir = os.path.join(REPORTS_DIR, safe_class_name)
            reports_student_dir = os.path.join(reports_class_dir, safe_folder_name)

            # 確保目錄存在
            os.makedirs(uploads_student_dir, exist_ok=True)
            os.makedirs(reports_student_dir, exist_ok=True)

            # 保存上傳檔案（現在有 question_title 和 attempt_number）
            save_path, drive_id = await FileHandler.save_upload_file(
                file,
                user_id,
                uploads_student_dir,
                file.filename,
                class_name,
                student_number or student_id_from_html,
                db_student_name,
                question_title,
                attempt_number,
            )

            # 檔案成功保存後才刪除上傳訊息
            try:
                await message.delete()
                print("✅ 已刪除上傳訊息")
            except (discord.Forbidden, discord.NotFound):
                print("⚠️ 無法刪除上傳訊息（可能權限不足或訊息已被刪除）")

            # 刪除臨時檔案
            os.remove(temp_path)

            if save_path is None:
                await message.author.send("❌ 檔案保存失敗\n" "❌ File save failed")
                return

            # 發送處理中訊息
            processing_msg = await message.author.send(
                f"🔄 **正在處理您的作業 / Processing Your Homework**\n\n"
                f"📝 題目 / Question：{question_title}\n"
                f"🔢 第 {attempt_number} 次提交 / Submission #{attempt_number}\n"
                f"⏳ 請稍候，系統正在進行智慧評分...\n"
                f"⏳ Please wait, AI grading in progress..."
            )

            # 執行英語評分
            eng_feedback = await self.grading_service.grade_homework(
                answer_text=answer_text, question_number=question_title, prompt_type="eng", html_title=html_title
            )

            # 執行統計評分
            stats_feedback = await self.grading_service.grade_homework(
                answer_text=answer_text, question_number=question_title, prompt_type="stats", html_title=html_title
            )

            print(f"✅ 英語評分完成")
            print(f"✅ 統計評分完成")

            # 解析評分結果
            eng_score, eng_band, eng_feedback_clean = self.grading_service.parse_grading_result(eng_feedback)
            stats_score, stats_band, stats_feedback_clean = self.grading_service.parse_grading_result(stats_feedback)

            print(f"📊 英語分數: {eng_score}, 等級: {eng_band}")
            print(f"📊 統計分數: {stats_score}, 等級: {stats_band}")

            # 生成並保存報告
            report_path, report_filename, report_drive_id = await FileHandler.generate_and_save_report(
                db_student_name=db_student_name,
                student_number=student_number,
                student_id_from_html=student_id_from_html,
                question_title=question_title,
                attempt_number=attempt_number,
                answer_text=answer_text,
                eng_score=eng_score,
                eng_band=eng_band,
                eng_feedback_clean=eng_feedback_clean,
                stats_score=stats_score,
                stats_band=stats_band,
                stats_feedback_clean=stats_feedback_clean,
                reports_student_dir=reports_student_dir,
                class_name=class_name,
                student_id=student_number or student_id_from_html,
            )

            if not report_path:
                await message.author.send("❌ 生成報告失敗")
                return

            # 記錄到資料庫（保留在 discord_bot.py 中）
            overall_score = (eng_score + stats_score) / 2
            combined_feedback = f"英語評分:\n{eng_feedback_clean}\n\n統計評分:\n{stats_feedback_clean}"

            success = self.db.insert_submission(
                user_id=user_id,
                student_name=db_student_name,
                student_id=student_number or student_id_from_html,
                question_number=question_title,
                attempt_number=attempt_number,
                html_path=report_path,
                score=overall_score,
                feedback=combined_feedback,
            )

            if success:
                print(f"✅ 已記錄到資料庫")
            else:
                print(f"⚠️ 記錄到資料庫失敗，但評分已完成")

            # 更新處理中訊息
            await processing_msg.edit(content="✨ **評分完成！/ Grading Complete!** 正在準備您的詳細報告...\n" "Preparing your detailed report...")

            # 發送結果
            result_text = (
                f"🎉 **作業評分完成 / Homework Grading Complete**\n\n"
                f"👤 **學生 / Student**：{db_student_name}\n"
                f"📝 **題目 / Question**：{question_title}\n"
                f"🔢 **提交次數 / Submission**：第 {attempt_number} 次 / #{attempt_number}\n\n"
                f"📊 **評分結果 / Grading Results**：\n"
                f"• 🔤 英語表達 / English：{eng_score} 分 / points (等級 / Level: {eng_band})\n"
                f"• 📈 統計內容 / Statistics：{stats_score} 分 / points (等級 / Level: {stats_band})\n"
                f"• 🎯 總體分數 / Overall：{overall_score:.1f} 分 / points\n"
            )

            await message.author.send(result_text)

            # 發送報告檔案
            with open(report_path, "rb") as f:
                await message.author.send(
                    f"📄 **詳細評分報告 / Detailed Grading Report**\n"
                    f"完整的評分分析和改進建議請參考附件\n"
                    f"Please refer to the attachment for complete grading analysis and improvement suggestions",
                    file=discord.File(f, report_filename),
                )

            print(f"✅ 已發送結果給用戶")

        except Exception as e:
            print(f"❌ 處理檔案時發生錯誤: {e}")
            import traceback

            traceback.print_exc()

            await message.author.send(f"❌ 處理檔案時發生錯誤 / Error processing file: {e}")
            try:
                if "save_path" in locals() and os.path.exists(save_path):
                    os.remove(save_path)
            except:
                pass

        except Exception as e:
            print(f"❌ 處理 HTML 檔案時發生錯誤: {e}")
            import traceback

            traceback.print_exc()
            await message.author.send(f"❌ 處理 HTML 檔案時發生錯誤: {e}")

            # 如果在檔案保存前出現錯誤，仍嘗試刪除訊息
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass

    async def on_close(self):
        """機器人關閉時的清理工作"""
        if self.session:
            await self.session.close()
        self.db.close()

    def run(self):
        """啟動機器人"""
        self.client.run(DISCORD_TOKEN)

    async def _handle_password_login(self, message):
        """處理密碼登入邏輯 - 根據用戶身分組決定查詢範圍"""
        try:
            user_id = message.author.id
            member = message.guild.get_member(user_id)

            # 檢查用戶是否已經登入過
            existing_student = self.db.get_student_by_discord_id(str(user_id))
            if existing_student:
                # 根據實際返回的欄位數量調整解析
                if len(existing_student) >= 6:
                    student_number = existing_student[2]
                    class_name = existing_student[5]
                elif len(existing_student) >= 5:
                    student_number = "未知"
                    class_name = existing_student[4]
                else:
                    student_number = "未知"
                    class_name = "未知"

                await message.author.send(
                    f"❌ 您已經登入過系統 / You have already logged in\n" f"學號 / Student ID：{student_number}\n" f"班級 / Class：{class_name}"
                )
                try:
                    await message.delete()
                except:
                    pass
                return

            # 檢查用戶是否有身分組
            user_class_name = self._get_user_class_from_roles(member)
            if not user_class_name:
                await message.author.send(
                    "❌ 您尚未擁有任何身分組，無法使用密碼登入\n"
                    "❌ You don't have any role yet, cannot use password login\n\n"
                    "請先到歡迎頻道使用以下指令加入身分組：\n"
                    "Please go to welcome channel and use the following commands to join a role:\n\n"
                    "• `!join NCUFN` - 中央大學財金系 / NCU Finance\n"
                    "• `!join NCUEC` - 中央大學經濟系 / NCU Economics\n"
                    "• `!join CYCUIUBM` - 中原大學國際商學學士學位學程 / CYU IUBM\n\n"
                    "⚠️ **重要 / Important**：只有擁有對應身分組的用戶才能登入該班級的帳號！\n"
                    "Only users with corresponding role can login to that class account!"
                )
                try:
                    await message.delete()
                except:
                    pass
                return

            # 解析指令 - 只支援 !login 學號 密碼
            parts = message.content.split(maxsplit=2)

            if len(parts) != 3:
                await message.author.send(
                    "❌ 登入指令格式錯誤 / Login command format error\n\n"
                    f"正確使用方式 / Correct usage：`!login 學號 密碼` / `!login student_id password`\n"
                    f"您的身分組 / Your role：{user_class_name}\n"
                    f"系統將只在 {user_class_name} 班級中驗證您的資料\n"
                    f"System will only verify your data in {user_class_name} class\n\n"
                    "⚠️ **重要 / Important**：系統會根據您的身分組限制登入範圍，確保資料安全！\n"
                    "System will restrict login scope based on your role to ensure data security!"
                )
                try:
                    await message.delete()
                except:
                    pass
                return

            student_number = parts[1]
            password = parts[2]

            print(f"🔐 用戶 {user_id} 嘗試登入，身分組: {user_class_name}, 學號: {student_number}")

            # 根據用戶身分組驗證登入
            if await self._verify_and_login_by_user_role(message.author, user_class_name, student_number, password):
                await message.author.send("✅ 登入成功！/ Login successful!")
                print(f"✅ 用戶 {user_id} 登入成功")
            else:
                await message.author.send(
                    f"❌ 登入失敗 / Login failed\n\n"
                    f"可能的原因 / Possible reasons：\n"
                    f"1. 學號 {student_number} 不存在於 {user_class_name} 班級中\n"
                    f"   Student ID {student_number} does not exist in {user_class_name} class\n"
                    f"2. 密碼錯誤 / Incorrect password\n"
                    f"3. 該學號已綁定其他 Discord 帳號\n"
                    f"   This student ID is already bound to another Discord account\n\n"
                    f"💡 **說明 / Note**：\n"
                    f"• 系統只會在您的身分組（{user_class_name}）對應的班級中查找帳號\n"
                    f"  System will only search for account in your role's ({user_class_name}) corresponding class\n"
                    f"• 不同班級可以有相同學號，這是正常的\n"
                    f"  Different classes can have same student ID, this is normal\n"
                    f"• 如果您確定學號和密碼正確，請聯繫管理員檢查帳號是否已正確導入到 {user_class_name} 班級\n"
                    f"  If you're sure the ID and password are correct, please contact admin to check if account is imported to {user_class_name} class"
                )
                print(f"❌ 用戶 {user_id} 登入失敗")

            try:
                await message.delete()
            except:
                pass

        except Exception as e:
            await message.author.send(f"❌ 登入過程發生錯誤 / Error during login process：{e}")
            print(f"❌ 登入過程發生錯誤: {e}")
            # 清除登入狀態
            if hasattr(self, "pending_login") and user_id in self.pending_login:
                del self.pending_login[user_id]

    async def _handle_login_step(self, message):
        """處理登入步驟中的訊息"""
        user_id = message.author.id

        if user_id not in self.pending_login:
            return False

        login_data = self.pending_login[user_id]
        content = message.content.strip()

        try:
            if login_data["step"] == "student_number":
                # 處理學號輸入
                login_data["student_number"] = content
                login_data["step"] = "password"

                await message.author.send("🔐 請輸入您的密碼：")

            elif login_data["step"] == "password":
                # 處理密碼輸入並完成登入
                student_number = login_data["student_number"]
                password = content

                if await self._verify_and_login(message.author, student_number, password):
                    await message.author.send("✅ 登入成功！")
                    del self.pending_login[user_id]
                else:
                    await message.author.send("❌ 密碼錯誤，請重新輸入密碼：")

            return True

        except Exception as e:
            await message.author.send(f"❌ 處理登入步驟時發生錯誤：{e}")
            del self.pending_login[user_id]
            return True

    async def _verify_and_login(self, user, student_number, password):
        """驗證學號密碼並完成登入"""
        try:
            print(f"開始驗證學號: {student_number}")

            # 從資料庫查詢學生資料（包含密碼）
            student_data = self.db.get_student_by_student_id_with_password(student_number)

            if not student_data:
                print(f"❌ 找不到學號 {student_number} 的資料")
                return False

            print(f"✅ 找到學生資料: {student_data}")

            # 解析學生資料 - 根據修正後的查詢結果調整
            # (student_number, student_name, discord_id, class_id, class_name, password)
            student_number_db, student_name, discord_id_in_db, class_id, class_name_db, stored_password = student_data

            print(f"資料庫中的密碼: {stored_password}, 輸入的密碼: {password}")

            # 驗證密碼
            if stored_password != password:
                print("❌ 密碼不匹配")
                return False

            print("✅ 密碼驗證成功")

            # 檢查該學號是否已經綁定其他 Discord 帳號
            if discord_id_in_db and discord_id_in_db != str(user.id):
                await user.send(f"❌ 該學號已綁定其他 Discord 帳號")
                return False

            # 更新 Discord ID
            if self.db.update_student_discord_id_by_student_id(student_number, str(user.id)):
                await user.send(
                    f"✅ 登入成功！\n"
                    f"👤 學號：{student_number}\n"
                    f"📛 姓名：{student_name}\n"
                    f"🏫 班級：{class_name_db}\n"
                    f"🔗 Discord ID 已綁定"
                )

                # 給予相應的身分組
                await self._assign_role_after_login(user, class_name_db)
                return True
            else:
                await user.send("❌ 更新 Discord ID 失敗")
                return False

        except Exception as e:
            print(f"驗證過程詳細錯誤: {e}")
            import traceback

            traceback.print_exc()
            await user.send(f"❌ 驗證過程發生錯誤：{e}")
            return False

    async def _assign_role_after_login(self, user, class_name):
        """登入後自動分配身分組"""
        try:
            # 獲取用戶所在的伺服器
            guild = None
            for g in self.client.guilds:
                member = g.get_member(user.id)
                if member:
                    guild = g
                    break

            if not guild:
                await user.send("⚠️ 無法找到您所在的伺服器，請手動聯繫管理員分配身分組")
                return

            member = guild.get_member(user.id)
            if not member:
                return

            # 根據班級名稱分配身分組
            role_mapping = {
                "NCUFN": (NCUFN_ROLE_NAME, NCUFN_ROLE_ID),
                "NCUEC": (NCUEC_ROLE_NAME, NCUEC_ROLE_ID),
                "CYCUIUBM": (CYCUIUBM_ROLE_NAME, CYCUIUBM_ROLE_ID),
            }

            if class_name in role_mapping:
                role_name, role_id = role_mapping[class_name]

                # 查找身分組
                role = None
                if role_id != 0:
                    role = guild.get_role(role_id)

                if not role:
                    role = discord.utils.get(guild.roles, name=role_name)

                if not role:
                    # 創建身分組
                    permissions = discord.Permissions()
                    permissions.send_messages = True
                    permissions.attach_files = True
                    permissions.read_messages = True
                    role = await guild.create_role(name=role_name, permissions=permissions, reason="自動創建身分組")

                # 給予身分組
                await member.add_roles(role, reason=f"登入後自動分配身分組: {class_name}")
                await user.send(f"✅ 已自動分配身分組：{role_name}")

        except Exception as e:
            await user.send(f"⚠️ 分配身分組時發生錯誤：{e}")

    def _extract_question_number(self, filename, html_title):
        """從檔案名稱或標題提取題目編號"""
        import re

        # 嘗試從檔案名稱提取
        filename_match = re.search(r"(\d+)", filename)
        if filename_match:
            return int(filename_match.group(1))

        # 嘗試從HTML標題提取
        if html_title:
            title_match = re.search(r"(\d+)", html_title)
            if title_match:
                return int(title_match.group(1))

        # 預設返回1
        return 1

    def _get_user_class_from_roles(self, member):
        """根據用戶的 Discord 身分組獲取對應的班級名稱"""
        if not member:
            return None

        # 檢查用戶擁有的身分組
        user_roles = [role.name for role in member.roles]

        # 根據身分組對應班級
        if NCUFN_ROLE_NAME in user_roles:
            return "NCUFN"
        elif NCUEC_ROLE_NAME in user_roles:
            return "NCUEC"
        elif CYCUIUBM_ROLE_NAME in user_roles:
            return "CYCUIUBM"

        return None

    async def _verify_and_login_by_user_role(self, user, class_name, student_number, password):
        """根據用戶身分組在對應班級範圍內驗證學號密碼並完成登入"""
        try:
            print(f"🔍 開始在 {class_name} 班級中驗證學號: {student_number}")
            print(f"🆔 用戶 Discord ID: {user.id}")

            # 步驟1：獲取班級ID
            class_data = self.db.get_class_by_name(class_name)
            if not class_data:
                print(f"❌ 找不到班級 {class_name}")
                return False

            class_id = class_data[0]
            print(f"✅ 找到班級 {class_name}, ID: {class_id}")

            # 步驟2：檢查該 Discord ID 是否已經被其他學生使用
            existing_student_with_discord = self.db.get_student_by_discord_id(str(user.id))
            if existing_student_with_discord:
                print(f"❌ Discord ID {user.id} 已被其他學生使用: {existing_student_with_discord}")
                await user.send(
                    f"❌ 您的 Discord 帳號已綁定到其他學生記錄\n"
                    f"❌ Your Discord account is bound to another student record\n\n"
                    f"📋 已綁定的帳號資訊 / Bound account info：\n"
                    f"• 學號 / Student ID：{existing_student_with_discord[2] if len(existing_student_with_discord) > 2 else '未知/Unknown'}\n"
                    f"• 班級 / Class：{existing_student_with_discord[5] if len(existing_student_with_discord) > 5 else existing_student_with_discord[4] if len(existing_student_with_discord) > 4 else '未知/Unknown'}\n\n"
                    f"💡 **說明 / Note**：\n"
                    f"• 每個 Discord 帳號只能綁定一個學生記錄\n"
                    f"  Each Discord account can only be bound to one student record\n"
                    f"• 如果這不是您的帳號，請聯繫管理員處理\n"
                    f"  If this is not your account, please contact administrator"
                )
                return False

            # 步驟3：從資料庫查詢學生資料
            student_data = self.db.get_student_by_student_id_with_password(student_number)
            if not student_data:
                print(f"❌ 找不到學號 {student_number} 的資料")
                await user.send(
                    f"❌ 學號 {student_number} 不存在於系統中\n"
                    f"❌ Student ID {student_number} does not exist in system\n\n"
                    f"💡 可能的原因 / Possible reasons：\n"
                    f"• 學號輸入錯誤 / Student ID input error\n"
                    f"• 學號尚未導入系統 / Student ID not yet imported to system\n"
                    f"• 請檢查學號格式是否正確 / Please check if student ID format is correct"
                )
                return False

            print(f"✅ 找到學生資料: {student_data}")

            # 步驟4：解析學生資料並驗證班級匹配
            student_number_db, student_name, discord_id_in_db, db_class_id, class_name_db, stored_password = student_data

            print(
                f"📋 學生完整資料: 學號={student_number_db}, 姓名={student_name}, Discord ID='{discord_id_in_db}', 班級ID={db_class_id}, 班級名={class_name_db}"
            )

            # 驗證班級是否匹配
            if db_class_id != class_id or class_name_db != class_name:
                print(f"❌ 班級不匹配 - 用戶班級: {class_name}(ID:{class_id}), 學號班級: {class_name_db}(ID:{db_class_id})")
                await user.send(
                    f"❌ 學號 {student_number} 存在，但不在您的班級中\n"
                    f"❌ Student ID {student_number} exists, but not in your class\n\n"
                    f"🔍 查詢結果 / Query result：\n"
                    f"• 您的身分組班級 / Your role's class：{class_name}\n"
                    f"• 該學號所屬班級 / Student ID's class：{class_name_db}\n\n"
                    f"💡 **說明 / Note**：\n"
                    f"• 不同班級可能有相同學號 / Different classes may have same student ID\n"
                    f"• 系統只允許您登入自己班級的帳號 / System only allows you to login to your own class account\n"
                    f"• 請確認您選擇了正確的身分組 / Please confirm you chose the correct role"
                )
                return False

            print(f"✅ 班級驗證通過：學號 {student_number} 屬於班級 {class_name}")

            # 步驟5：驗證密碼
            print(f"🔐 資料庫中的密碼: {stored_password}, 輸入的密碼: {password}")
            if stored_password != password:
                print("❌ 密碼不匹配")
                await user.send(
                    f"❌ 密碼錯誤 / Incorrect password\n\n"
                    f"📋 帳號資訊 / Account info：\n"
                    f"• 學號 / Student ID：{student_number}\n"
                    f"• 班級 / Class：{class_name}\n"
                    f"• 姓名 / Name：{student_name}\n\n"
                    f"請確認密碼是否正確 / Please confirm if password is correct"
                )
                return False

            print("✅ 密碼驗證成功")

            # 步驟6：檢查該學號的 Discord 綁定狀態
            print(f"🔍 檢查學號的 Discord 綁定狀態: '{discord_id_in_db}' (type: {type(discord_id_in_db)})")

            # 檢查 Discord ID 是否為空值（NULL, None, 空字符串等）
            def is_empty_discord_id(discord_id):
                return discord_id is None or discord_id == "" or str(discord_id).lower() in ["none", "null", ""]

            if not is_empty_discord_id(discord_id_in_db):
                # Discord ID 不為空，檢查是否匹配當前用戶
                if str(discord_id_in_db) == str(user.id):
                    # 已經是當前用戶，直接返回成功
                    print(f"✅ 學號已綁定當前用戶，直接返回成功")
                    await user.send(
                        f"✅ 您已經登入過系統！/ You have already logged in!\n\n"
                        f"📋 帳號資訊 / Account info：\n"
                        f"👤 學號 / Student ID：{student_number}\n"
                        f"📛 姓名 / Name：{student_name}\n"
                        f"🏫 班級 / Class：{class_name}\n"
                        f"🔗 Discord ID 已綁定 / Discord ID bound"
                    )
                    return True
                else:
                    # 已綁定其他 Discord 帳號
                    print(f"❌ 該學號已綁定其他 Discord 帳號: {discord_id_in_db}")
                    await user.send(
                        f"❌ 該學號已經綁定其他 Discord 帳號\n"
                        f"❌ This student ID is already bound to another Discord account\n\n"
                        f"📋 帳號資訊 / Account info：\n"
                        f"• 學號 / Student ID：{student_number}\n"
                        f"• 班級 / Class：{class_name}\n"
                        f"• 姓名 / Name：{student_name}\n\n"
                        f"如果這是您的帳號，請聯繫管理員處理\n"
                        f"If this is your account, please contact administrator"
                    )
                    return False
            else:
                # Discord ID 為空值，可以直接綁定
                print(f"✅ 學號的 Discord ID 為空值，可以進行綁定")

            # 步驟7：更新 Discord ID（只有當 Discord ID 為空值時才執行）
            print(f"🔗 開始將 Discord ID {user.id} 綁定到學號 {student_number} (班級: {class_name})")

            try:
                # 使用班級ID和學號的組合來更新，避免重複學號問題
                update_result = self.db.update_student_discord_id_by_student_id_and_class(student_number, str(user.id), class_id)
                print(f"📝 資料庫更新結果: {update_result}")

                if update_result:
                    print("✅ Discord ID 更新成功")
                    await user.send(
                        f"✅ 登入成功！/ Login successful!\n\n"
                        f"📋 帳號資訊 / Account info：\n"
                        f"👤 學號 / Student ID：{student_number}\n"
                        f"📛 姓名 / Name：{student_name}\n"
                        f"🏫 班級 / Class：{class_name}\n"
                        f"🔗 Discord ID 已綁定 / Discord ID bound\n\n"
                        f"🛡️ 系統已驗證您的身分組與班級匹配\n"
                        f"🛡️ System has verified your role matches the class"
                    )
                    return True
                else:
                    print("❌ Discord ID 更新失敗 - 更新操作返回 False")
                    await user.send(
                        f"❌ 系統更新失敗 / System update failed\n\n"
                        f"📋 嘗試綁定的帳號 / Attempted binding account：\n"
                        f"• 學號 / Student ID：{student_number}\n"
                        f"• 班級 / Class：{class_name}\n\n"
                        f"請聯繫管理員檢查資料庫狀態\n"
                        f"Please contact administrator to check database status"
                    )
                    return False

            except Exception as update_error:
                error_msg = str(update_error)
                print(f"❌ 更新 Discord ID 時發生異常: {error_msg}")

                if "UNIQUE constraint failed" in error_msg:
                    # 檢查是否是 Discord ID 重複
                    print(f"🔍 UNIQUE 約束失敗，檢查 Discord ID 衝突...")
                    conflicting_student = self.db.get_student_by_discord_id(str(user.id))
                    if conflicting_student:
                        # 分析衝突學生的資訊
                        conflict_class_name = (
                            conflicting_student[5]
                            if len(conflicting_student) > 5
                            else conflicting_student[4] if len(conflicting_student) > 4 else "未知"
                        )
                        conflict_student_number = conflicting_student[2] if len(conflicting_student) > 2 else "未知"

                        print(f"🔍 發現 Discord ID 衝突: {conflicting_student}")
                        await user.send(
                            f"❌ Discord ID 綁定衝突 / Discord ID binding conflict\n\n"
                            f"📋 您的 Discord 帳號已綁定到 / Your Discord account is bound to：\n"
                            f"• 學號 / Student ID：{conflict_student_number}\n"
                            f"• 班級 / Class：{conflict_class_name}\n\n"
                            f"🔄 嘗試綁定的帳號 / Attempted binding account：\n"
                            f"• 學號 / Student ID：{student_number}\n"
                            f"• 班級 / Class：{class_name}\n\n"
                            f"💡 每個 Discord 帳號只能綁定一個學生記錄\n"
                            f"💡 Each Discord account can only be bound to one student record\n"
                            f"如果需要更改綁定，請聯繫管理員\n"
                            f"If you need to change binding, please contact administrator"
                        )
                    else:
                        # 可能是學號重複約束
                        print(f"🔍 可能是學號+班級組合衝突")
                        await user.send(
                            f"❌ 學號綁定失敗：資料約束錯誤\n"
                            f"❌ Student ID binding failed: Data constraint error\n\n"
                            f"📋 嘗試綁定的帳號 / Attempted binding account：\n"
                            f"• 學號 / Student ID：{student_number}\n"
                            f"• 班級 / Class：{class_name}\n\n"
                            f"💡 **可能的原因 / Possible reasons**：\n"
                            f"• 該學號在此班級中已有其他 Discord 綁定\n"
                            f"  This student ID already has another Discord binding in this class\n"
                            f"• 資料庫約束衝突 / Database constraint conflict\n"
                            f"• 請聯繫管理員檢查帳號狀態\n"
                            f"  Please contact administrator to check account status"
                        )
                elif "no such method" in error_msg.lower() or "no such function" in error_msg.lower():
                    # 如果新方法不存在，回退到原方法
                    print(f"⚠️ 新的更新方法不存在，回退到原方法")
                    try:
                        update_result = self.db.update_student_discord_id_by_student_id(student_number, str(user.id))
                        if update_result:
                            print("✅ 使用原方法更新 Discord ID 成功")
                            await user.send(
                                f"✅ 登入成功！/ Login successful!\n\n"
                                f"📋 帳號資訊 / Account info：\n"
                                f"👤 學號 / Student ID：{student_number}\n"
                                f"📛 姓名 / Name：{student_name}\n"
                                f"🏫 班級 / Class：{class_name}\n"
                                f"🔗 Discord ID 已綁定 / Discord ID bound\n\n"
                                f"⚠️ 系統使用了備用更新方法\n"
                                f"⚠️ System used backup update method"
                            )
                            return True
                        else:
                            await user.send(
                                "❌ 備用更新方法也失敗 / Backup update method also failed\n" "請聯繫管理員 / Please contact administrator"
                            )
                            return False
                    except Exception as fallback_error:
                        print(f"❌ 備用方法也失敗: {fallback_error}")
                        await user.send(
                            f"❌ 所有更新方法都失敗 / All update methods failed\n\n"
                            f"錯誤訊息 / Error message：{fallback_error}\n\n"
                            f"請聯繫管理員處理 / Please contact administrator"
                        )
                        return False
                else:
                    await user.send(
                        f"❌ Discord ID 綁定失敗 / Discord ID binding failed\n\n"
                        f"📋 嘗試綁定的帳號 / Attempted binding account：\n"
                        f"• 學號 / Student ID：{student_number}\n"
                        f"• 班級 / Class：{class_name}\n\n"
                        f"錯誤訊息 / Error message：{error_msg}\n\n"
                        f"請聯繫管理員處理此問題\n"
                        f"Please contact administrator to handle this issue"
                    )
                return False
        except Exception as e:
            print(f"驗證過程詳細錯誤: {e}")
            import traceback

            traceback.print_exc()
            await user.send(f"❌ 驗證過程發生錯誤 / Error during verification process：{e}")
            return False

    async def _handle_join_role(self, message, role_type):
        """處理使用者請求加入身分組"""
        try:
            # 確認為 Guild 內的 Member
            guild = message.guild
            member = message.author
            if guild is None or not hasattr(member, "add_roles"):
                return

            # 延遲匯入 config 以避免循環導入
            from config import (
                NCUFN_ROLE_ID,
                NCUEC_ROLE_ID,
                CYCUIUBM_ROLE_ID,
                NCUFN_ROLE_NAME,
                NCUEC_ROLE_NAME,
                CYCUIUBM_ROLE_NAME,
            )

            mapping = {
                "NCUFN": (NCUFN_ROLE_ID, NCUFN_ROLE_NAME),
                "NCUEC": (NCUEC_ROLE_ID, NCUEC_ROLE_NAME),
                "CYCUIUBM": (CYCUIUBM_ROLE_ID, CYCUIUBM_ROLE_NAME),
            }

            if role_type not in mapping:
                await message.author.send(
                    f"❌ **找不到身分組類型 / Role Type Not Found**\n\n"
                    f"• 輸入的類型 / Input: `{role_type}`\n"
                    f"• 可用的類型 / Available types: `NCUFN`, `NCUEC`, `CYCUIUBM`"
                )
                return

            role_id, role_name = mapping[role_type]
            role = None
            if role_id:
                role = discord.utils.get(guild.roles, id=role_id)
            if role is None and role_name:
                role = discord.utils.get(guild.roles, name=role_name)

            if role is None:
                await message.author.send(
                    f"❌ **伺服器中找不到身分組 / Role Not Found in Server**\n\n"
                    f"• 身分組類型 / Role Type: `{role_type}`\n"
                    f"• 請確認身分組存在且機器人有權限\n"
                    f"  Please ensure the role exists and bot has permissions"
                )
                return

            await member.add_roles(role, reason="User requested role join")
            await message.author.send(
                f"✅ **身分組已加入 / Role Added Successfully**\n\n"
                f"• 身分組名稱 / Role Name: `{role.name}`\n"
                f"• 您現在可以使用系統功能了\n"
                f"  You can now use the system features"
            )

            # 刪除用戶的 !join 訊息，保持頻道清潔
            try:
                await message.delete()
            except discord.Forbidden:
                print("無權限刪除訊息 / No permission to delete message")
            except discord.NotFound:
                print("訊息已被刪除 / Message already deleted")

        except Exception as e:
            await message.author.send(
                f"❌ **處理身分組時發生錯誤 / Error Processing Role**\n\n"
                f"• 錯誤訊息 / Error Message: {e}\n"
                f"• 請聯繫管理員 / Please contact administrator"
            )

    def _get_safe_filename(self, name: str) -> str:
        """
        將名稱轉換為安全的檔案名稱
        移除或替換不安全的字元
        """
        # 移除或替換不安全的字元
        safe_name = name.replace(" ", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in ("_", "-"))
        return safe_name
