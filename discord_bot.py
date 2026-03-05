import os
import discord
import aiohttp
import asyncio
import traceback
import openai
import time
from config import (
    DISCORD_TOKEN,
    UPLOADS_DIR, REPORTS_DIR,
    REPORTS_FOLDER_ID,
    WELCOME_CHANNEL_ID, NCUFN_CHANNEL_ID, NCUEC_CHANNEL_ID, CYCUIUBM_CHANNEL_ID, HWIS_CHANNEL_ID, ADMIN_CHANNEL_ID, 
    NCUFN_ROLE_NAME, NCUEC_ROLE_NAME, CYCUIUBM_ROLE_NAME, HWIS_ROLE_NAME,
    NCUFN_ROLE_ID, NCUEC_ROLE_ID, CYCUIUBM_ROLE_ID, HWIS_ROLE_ID, ADMIN_ROLE_ID
)
from database import DatabaseManager
from html_parser import extract_html_content, extract_html_title
from grading import GradingService
from file_handler import FileHandler
import io
import pandas as pd
import json
from html_parser import extract_html_content, extract_html_title, extract_scores_from_html_string


class HomeworkBot:
    def __init__(self, force_welcome=False):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        self.client = discord.Client(intents=intents)
        self.db = DatabaseManager()
        self.session = None
        self.force_welcome = force_welcome
        self.is_open = True  # 機器人開關狀態，預設為開啟

        # 身分組對應班級名稱 - 改為英文
        self.role_to_class = {
            NCUFN_ROLE_NAME: "NCUFN",
            NCUEC_ROLE_NAME: "NCUEC",
            CYCUIUBM_ROLE_NAME: "CYCUIUBM",
            HWIS_ROLE_NAME: "HWIS",
        }

        # 班級頻道 ID 設定
        try:
            self.class_channels = {
                "NCUFN": NCUFN_CHANNEL_ID,
                "NCUEC": NCUEC_CHANNEL_ID,
                "CYCUIUBM": CYCUIUBM_CHANNEL_ID,
                "HWIS": HWIS_CHANNEL_ID,
            }
        except ImportError:
            print("⚠️ 未設定班級頻道 ID，將允許在任何頻道使用")
            self.class_channels = {}

        # 設定事件處理器
        self.client.event(self.on_ready)
        self.client.event(self.on_message)
        self.client.event(self.on_close)

    def is_class_channel(self, channel_id, user_class=None):
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

    def get_user_class_channel_info(self, member):
        """獲取用戶的班級和對應頻道資訊"""
        user_class = self.get_user_class_from_roles(member)
        if user_class and user_class in self.class_channels:
            return user_class, self.class_channels[user_class]
        return user_class, None

    async def remove_role_members(self, message):
        """移除指定身份組的所有成員"""
        try:
            # 解析指令
            parts = message.content.split(maxsplit=1)
            
            if len(parts) < 2:
                await message.author.send(
                    "❌ **指令格式錯誤 / Command Format Error**\n\n"
                    "正確用法 / Correct usage：\n"
                    "`!remove-role-members 身份組名稱`\n"
                    "`!remove-role-members role_name`\n\n"
                    "範例 / Example：\n"
                    "`!remove-role-members NCUFN`\n"
                    "`!remove-role-members NCUEC`"
                )
                return
            
            role_name = parts[1].strip()
            
            # 獲取伺服器
            guild = message.guild
            if not guild:
                await message.author.send("❌ 無法獲取伺服器資訊 / Cannot get server info")
                return
            
            # 尋找身份組
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                await message.author.send(
                    f"❌ **找不到身份組 / Role Not Found**\n\n"
                    f"身份組名稱：`{role_name}`\n\n"
                    f"請確認身份組名稱是否正確。\n"
                    f"Please confirm the role name is correct."
                )
                return
            
            # 獲取擁有該身份組的所有成員
            members_with_role = [member for member in guild.members if role in member.roles]
            
            if not members_with_role:
                await message.author.send(
                    f"ℹ️ **身份組中沒有成員 / No Members in Role**\n\n"
                    f"身份組：`{role_name}`\n\n"
                    f"該身份組目前沒有任何成員。\n"
                    f"This role currently has no members."
                )
                return
            
            # 發送確認訊息
            total_members = len(members_with_role)
            await message.author.send(
                f"⏳ **正在移除身份組成員 / Removing Role Members**\n\n"
                f"身份組：`{role_name}`\n"
                f"成員數量：{total_members}\n\n"
                f"處理中，請稍候...\n"
                f"Processing, please wait..."
            )
            
            # 移除成員
            success_count = 0
            failed_count = 0
            failed_members = []
            
            for member in members_with_role:
                try:
                    await member.remove_roles(role, reason=f"Bulk removal by admin: {message.author.name}")
                    success_count += 1
                    print(f"✅ 已移除 {member.name} 的身份組 {role_name}")
                except Exception as e:
                    failed_count += 1
                    failed_members.append(f"{member.name} ({member.id})")
                    print(f"❌ 移除 {member.name} 的身份組時失敗: {e}")
            
            # 發送結果報告
            result_message = (
                f"✅ **身份組成員移除完成 / Role Members Removal Complete**\n\n"
                f"身份組：`{role_name}`\n"
                f"總成員數 / Total members：{total_members}\n"
                f"成功移除 / Successfully removed：{success_count}\n"
                f"失敗 / Failed：{failed_count}\n"
            )
            
            if failed_members:
                result_message += "\n❌ **移除失敗的成員 / Failed Members**:\n"
                for failed_member in failed_members[:10]:  # 只顯示前10個
                    result_message += f"• {failed_member}\n"
                if len(failed_members) > 10:
                    result_message += f"... 以及其他 {len(failed_members) - 10} 位成員\n"
            
            await message.author.send(result_message)
            print(f"✅ 身份組 {role_name} 成員移除完成：{success_count}/{total_members}")
            
        except Exception as e:
            await message.author.send(f"❌ 移除身份組成員時發生錯誤 / Error removing role members：{e}")
            print(f"❌ remove_role_members 錯誤: {e}")
            traceback.print_exc()
    
    async def broadcast_status_to_class_channels(self, status_message, is_open_status):
        """廣播狀態訊息到所有班級頻道，並刪除舊的狀態訊息"""
        try:
            if not self.class_channels:
                print("⚠️ 未設定班級頻道，無法廣播狀態")
                return
            
            # 狀態訊息的識別標記
            status_identifier = "【系統狀態】"
            
            for class_name, channel_id in self.class_channels.items():
                try:
                    channel = self.client.get_channel(channel_id)
                    if not channel:
                        print(f"❌ 找不到班級頻道: {class_name} (ID: {channel_id})")
                        continue
                    
                    # 刪除舊的狀態訊息
                    deleted_count = 0
                    async for old_message in channel.history(limit=50):
                        if (
                            old_message.author == self.client.user
                            and status_identifier in old_message.content
                        ):
                            try:
                                await old_message.delete()
                                deleted_count += 1
                            except (discord.Forbidden, discord.NotFound):
                                pass
                    
                    if deleted_count > 0:
                        print(f"🧹 已刪除 {class_name} 頻道的 {deleted_count} 個舊狀態訊息")
                    
                    # 發送新的狀態訊息（帶有識別標記）
                    await channel.send(f"{status_identifier}\n{status_message}")
                    print(f"✅ 狀態訊息已發送到 {class_name} 頻道")
                    
                except Exception as e:
                    print(f"❌ 處理 {class_name} 頻道時發生錯誤: {e}")
            
            print(f"✅ 狀態廣播完成（狀態：{'開啟' if is_open_status else '關閉'}）")
            
        except Exception as e:
            print(f"❌ 廣播狀態訊息時發生錯誤: {e}")
    
    async def notify_administrators(self, title, description, error_details=None, severity="warning"):
        """發送通知給管理員"""
        try:
            if not ADMIN_CHANNEL_ID:
                # print("⚠️ 未設定管理員頻道 ID，跳過通知")
                return
                
            channel = self.client.get_channel(ADMIN_CHANNEL_ID)
            if not channel:
                print(f"❌ 找不到管理員頻道: {ADMIN_CHANNEL_ID}")
                return
                
            # Create embed for notification
            embed = discord.Embed(
                title=f"🚨 {title}",
                description=description,
                color=0xFF0000 if severity == "error" else 0xFFA500
            )
            
            if error_details:
                embed.add_field(
                    name="錯誤詳情 / Error Details",
                    value=f"```{str(error_details)[:1000]}```",
                    inline=False
                )
                
            embed.set_footer(text=f"時間 / Time: {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            # Mention admin role if configured
            admin_mention = ""
            if ADMIN_ROLE_ID:
                admin_mention = f"<@&{ADMIN_ROLE_ID}> "
                
            await channel.send(f"{admin_mention}管理員通知 / Admin Notification", embed=embed)
            
        except Exception as e:
            print(f"❌ 發送管理員通知失敗: {e}")

    async def on_ready(self):
        """機器人啟動時執行的事件處理器"""
        self.session = aiohttp.ClientSession()
        print(f"✅ HTML作業處理機器人已啟動: {self.client.user}")

        # 初始化班級資料
        await self.initialize_classes()

        # 發送歡迎訊息
        await self.send_welcome_message()

    async def initialize_classes(self):
        """初始化班級資料"""
        for class_name in self.role_to_class.values():
            class_data = self.db.get_class_by_name(class_name)
            if not class_data:
                class_id = self.db.create_class(class_name)
                print(f"✅ 已創建班級: {class_name} (ID: {class_id})")
            else:
                print(f"📋 班級已存在: {class_name} (ID: {class_data[0]})")

    async def send_welcome_message(self):
        """發送歡迎訊息到歡迎頻道和所有班級頻道"""
        embed = discord.Embed(
            title="🎓 歡迎使用統計學AI評分系統\nWelcome to Statistics AI Grading System",
            description="✨ **歡迎同學們！請仔細閱讀以下重要提醒**\n"
            "✨ **Welcome! Please read the following important reminders carefully**\n\n"
            "📍 **開始使用前，請先將機器人加入好友，確保可以收到訊息**\n"
            "📍 **Before using, please add the bot as a friend to make sure you can receive messages**\n\n",
            color=0x3498DB,
        )

        # 插入一個隱藏欄位來強制換行
        embed.add_field(name="", value="", inline=False)

        # 替換掉原本的 !join 說明，改為統一的登入說明
        embed.add_field(
            name="🔑 登入與綁定帳號 / Login & Bind Account",
            value="🔑請輸入以下指令進行登入，系統會自動分配您的身分組：\n"
                  "Please type the following command to login:\n"
                  "• `!login 學號 密碼` - 登入系統 / Login to system", 
            inline=False
        )

        # 插入一個隱藏欄位來強制換行
        embed.add_field(name="", value="", inline=False)

        embed.add_field(
            name="\n📚 系統功能說明 / System Features",
            value="• `!help` - 查看完整指令說明 / View complete instructions\n"
            "• **直接上傳作業 HTML 檔案** - 系統會自動評分\n"
            "• **Upload HTML homework file** - Auto grading\n"
            "• `!my-submissions` - 查看作業提交記錄 / View submission history",
            inline=False,
        )
        
        # 插入一個隱藏欄位來強制換行
        embed.add_field(name="", value="", inline=False)

        embed.add_field(
            name="🔗 作答網站 Answer Website",
            value="[點擊進入作答網站 / Click to enter answer website](https://chijiun.github.io/StatsAnswerFormatter/)",
            inline=False,
        )

        embed.set_footer(
            text="Statistics AI Grading System | 登入後系統將自動為您開啟對應的班級頻道！"
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
                                "歡迎使用統計學AI評分系統" in message.embeds[0].title 
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
                                "歡迎使用統計學AI評分系統" in message.embeds[0].title 
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
        # 忽略機器人自己的訊息
        if message.author.bot:
            return

        user_id = str(message.author.id)

        # 中央化訊息刪除邏輯 - 除了機器人歡迎訊息外，刪除所有處理過的訊息
        should_delete = False

        # ✅ 修改：檢查是否為私訊
        if isinstance(message.channel, discord.DMChannel):
            # ✅ 新增：允許在私訊中使用 !login 指令
            if message.content.lower().startswith("!login"):
                await self.handle_password_login(message)
                return

            # 對於其他私訊，引導用戶到班級頻道
            await message.author.send(
                "💡 您可以在私訊中使用 `!login 學號 密碼` 登入系統\n"
                "💡 You can use `!login student_id password` in DM to login"
                "💬 請勿在私訊中使用其他功能\n"
                "💬 Please do not use other features in DM\n\n"
                "🏫 請前往您的班級頻道進行以下操作：\n"
                "🏫 Please go to your class channel for the following operations:\n\n"
                "• 使用 `!help` 查看完整功能說明 / Use `!help` to view complete instructions\n"
                "• 使用 `!my-submissions` 查看作業提交記錄 / Use `!my-submissions` to view submission history\n"
                "• 📤 上傳 HTML 作業檔案進行評分 / Upload HTML homework file for grading\n"
            )
            return

        # 獲取用戶的班級和頻道資訊
        member = message.guild.get_member(message.author.id)
        user_class, user_channel_id = self.get_user_class_channel_info(member)

        # 處理幫助指令
        if message.content.lower() == "!help":
            is_admin = message.author.guild_permissions.administrator

            help_text = (
                "📖 **統計學AI評分系統使用指南**\n"
                "📖 **Statistics AI Grading System User Guide**\n\n"
                "🎯 **主要功能 / Main Features**:\n"
                "1. 📤 **上傳作業檔案 / Upload Homework** - 直接拖拽 `.html` 檔案到聊天室，系統會自動評分\n"
                "   Drag `.html` file to chat, system will auto grade\n"
                "2. 📋 `!help` - 顯示這個使用指南 / Show this guide\n"
                "3. 🔑 `!login 學號 密碼` - 使用學號密碼登入系統\n"
                "   Login with student ID and password\n"
                "4. 📝 `!my-submissions` - 查看我的作業提交記錄\n"
                "   View my submission history\n"
            )

            if is_admin:
                help_text += (
                    "\n👑 **管理員專用功能 / Admin Functions**:\n"
                    "• `!update-welcome` - 更新歡迎訊息 / Update welcome message\n"
                    "• `!score 班級 題目` - 匯出指定班級和題目的成績 / Export scores for specific class and question\n"
                    "• `!open` - 開啟作業批改功能 / Enable homework grading\n"
                    "• `!close` - 關閉作業批改功能（僅刪除訊息）/ Disable homework grading (delete messages only)\n"
                    "• `!remove-role-members 身份組名稱` - 移除指定身份組的所有成員 / Remove all members from a role\n"
                )

            help_text += (
                "\n💡 **溫馨提醒 / Tips**：\n"
                "• 除了登入外，所有功能都必須在您的班級專屬頻道中使用\n"
                "  Except login, all features must be used in your class channel\n"
                "• 作業評分會同時提供英語表達和統計內容兩個面向的建議\n"
                "  Homework grading provides feedback on both English expression and statistics content\n"
                "• 每次提交都會保留詳細的評分報告供您參考\n"
                "  Each submission's detailed grading report will be saved for your reference"
            )

            await message.author.send(help_text)
            should_delete = True

        # 處理密碼登入指令
        elif message.content.lower().startswith("!login"):
            await self.handle_password_login(message)
            should_delete = True

        # 處理我的提交記錄指令
        elif message.content.lower() == "!my-submissions":
            await self.show_my_submissions(message)
            should_delete = True

        # 處理管理員匯出成績指令 (!score 班級 題目代碼)
        elif message.content.lower().startswith("!score"):
            # 檢查權限：比對 ADMIN_ROLE_ID 或是具有伺服器管理員權限
            is_admin = any(role.id == ADMIN_ROLE_ID for role in message.author.roles) or message.author.guild_permissions.administrator
            
            if not is_admin:
                await message.author.send("⛔ **權限不足 / Access Denied**\n此指令僅限管理員 (ADMIN) 使用。")
                should_delete = True
            else:
                await self.export_class_scores(message)
                should_delete = True

        # 處理管理員開啟作業批改功能
        elif message.content.lower() == "!open":
            is_admin = any(role.id == ADMIN_ROLE_ID for role in message.author.roles) or message.author.guild_permissions.administrator
            
            if not is_admin:
                await message.author.send("⛔ **權限不足 / Access Denied**\n此指令僅限管理員使用。")
                should_delete = True
            else:
                self.is_open = True
                # 廣播狀態到所有班級頻道
                status_message = (
                    "✅ **作業批改功能已開啟 / Homework Grading Enabled**\n"
                    "現在可以接收和批改作業了。\n"
                    "Now accepting and grading homework submissions."
                )
                await self.broadcast_status_to_class_channels(status_message, True)
                # 向管理員發送確認訊息
                await message.author.send(
                    "✅ 作業批改功能已開啟，狀態訊息已發送到所有班級頻道。\n"
                    "✅ Homework grading enabled, status message sent to all class channels."
                )
                should_delete = True

        # 處理管理員關閉作業批改功能
        elif message.content.lower() == "!close":
            is_admin = any(role.id == ADMIN_ROLE_ID for role in message.author.roles) or message.author.guild_permissions.administrator
            
            if not is_admin:
                await message.author.send("⛔ **權限不足 / Access Denied**\n此指令僅限管理員使用。")
                should_delete = True
            else:
                self.is_open = False
                # 廣播狀態到所有班級頻道
                status_message = (
                    "🔒 **作業批改功能已關閉 / Homework Grading Disabled**\n"
                    "暫時不接受作業提交，上傳的檔案將被刪除。\n"
                    "Temporarily not accepting submissions, uploaded files will be deleted."
                )
                await self.broadcast_status_to_class_channels(status_message, False)
                # 向管理員發送確認訊息
                await message.author.send(
                    "🔒 作業批改功能已關閉，狀態訊息已發送到所有班級頻道。\n"
                    "🔒 Homework grading disabled, status message sent to all class channels."
                )
                should_delete = True

        # 處理管理員移除身份組成員指令
        elif message.content.lower().startswith("!remove-role-members"):
            is_admin = any(role.id == ADMIN_ROLE_ID for role in message.author.roles) or message.author.guild_permissions.administrator
            
            if not is_admin:
                await message.author.send("⛔ **權限不足 / Access Denied**\n此指令僅限管理員使用。")
                should_delete = True
            else:
                await self.remove_role_members(message)
                should_delete = True

        # 擋下歡迎頻道的閒聊與無效訊息 (引導使用 !login)
        elif message.channel.id == WELCOME_CHANNEL_ID:
            await message.author.send(
                "👋 **歡迎！** 這個頻道專門用來登入系統。\n"
                "👋 **Welcome!** This channel is for logging in.\n\n"
                "請輸入 `!login 學號 密碼` 來登入，系統將為您自動分配身分組。\n"
                "Please use `!login student_id password` to login and automatically get your class role.\n\n"
                "⚠️ 請勿在歡迎頻道進行其他操作\n"
                "⚠️ Please do not perform other operations in welcome channel"
            )
            should_delete = True

        # 添加管理員指令
        elif message.content.lower() == "!update-welcome" and message.author.guild_permissions.administrator:
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
                                    "歡迎使用統計學AI評分系統" in old_message.embeds[0].title
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
                await self.send_welcome_message()
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

            should_delete = True
        
        # 檢查是否為歡迎頻道的其他訊息 (擋下非指令的閒聊)
        elif message.channel.id == WELCOME_CHANNEL_ID:
            await message.author.send(
                "👋 **歡迎！** 這個頻道專門用來登入系統。\n"
                "👋 **Welcome!** This channel is for logging in.\n\n"
                "請輸入 `!login 學號 密碼` 來登入，系統將為您自動分配身分組。\n"
                "Please use `!login student_id password` to login and automatically get your class role.\n"
                "⚠️ 請勿在歡迎頻道進行其他操作\n"
                "⚠️ Please do not perform other operations in welcome channel"
            )
            should_delete = True

        # 非歡迎、班級頻道(專門反應訊息)，忽略
        elif not self.is_class_channel(message.channel.id, user_class):
            return

        # 處理 HTML 檔案上傳
        elif message.attachments:
            html_attachment = None
            # 尋找是否有 HTML 檔案
            for att in message.attachments:
                if att.filename.lower().endswith('.html'):
                    html_attachment = att
                    break
            
            if html_attachment:
                # 檢查機器人是否處於開啟狀態
                if not self.is_open:
                    # 關閉狀態：僅刪除訊息，不批改
                    try:
                        await message.delete()
                    except (discord.Forbidden, discord.NotFound):
                        pass
                    return
                
                # 開啟狀態：正常處理作業
                # 傳遞正確的三個參數 (message, file, user_id)
                await self.process_html_file(message, html_attachment, user_id)
                # 這裡不需要 should_delete = True，因為 _process_html_file 內部會處理刪除
            else:
                # 如果有附件但都不是 HTML
                await message.author.send(
                    "📄 **檔案格式錯誤**\n"
                    "請上傳 `.html` 格式的作業檔案。\n"
                    "Please upload homework file in `.html` format."
                )
                should_delete = True

        # 其他所有訊息（包括非 HTML 附件、無效指令等）
        else:
            # 引導用戶使用正確的功能
            await message.author.send(
                "❓ **無效的指令或檔案**\n"
                "❓ **Invalid command or file**\n\n"
                "請使用以下功能：\n"
                "Please use the following features:\n\n"
                "• `!help` - 查看使用指南 / View guide\n"
                "• `!my-submissions` - 查看作業記錄 / View submissions\n"
                "• 📤 上傳 `.html` 檔案進行AI評分 / Upload `.html` file for AI grading"
            )
            should_delete = True

        # 統一刪除訊息
        if should_delete:
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass

    async def process_html_file(self, message, file, user_id):
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
                    "系統找不到您的學生資料，請先完成以下步驟：\n"
                    "System cannot find your student data, please complete the following steps:\n\n"
                    "   🔑 使用 `!login 學號 密碼` 登入現有帳戶\n"
                    "   Use `!login student_id password` to login to existing account"
                )
                try:
                    await message.delete()
                except (discord.Forbidden, discord.NotFound):
                    pass
                return

            # 解析學生資料
            if len(student_data) == 6:
                db_student_id, db_student_name, student_number, discord_id, class_id, class_name = student_data
            else:
                await message.author.send(f"❌ 學生資料格式錯誤，欄位數量：{len(student_data)}")
                try:
                    await message.delete()
                except (discord.Forbidden, discord.NotFound):
                    pass
                return

            # 確保目錄存在
            os.makedirs(UPLOADS_DIR, exist_ok=True)
            
            # 解析 HTML 內容（先保存到臨時檔案）
            temp_path = os.path.join(UPLOADS_DIR, f"temp_{user_id}_{file.filename}")
            await file.save(temp_path)

            html_title = extract_html_title(temp_path)
            student_name, student_id_from_html, answer_text = extract_html_content(temp_path)

            print(f"📝 HTML 標題: {html_title}")
            print(f"👤 學生姓名: {student_name}")
            print(f"🆔 學號: {student_id_from_html}")
            print(f"📄 答案內容長度: {len(answer_text)} 字元")

            # 使用 HTML 標題作為題目標題
            question_title = html_title if html_title else file.filename
            print(f"📝 題目標題: {question_title}")
            
            # ✅ 新增：檢查是否有對應的 Prompt
            eng_prompt, stat_prompt = GradingService.get_grading_prompts(html_title)
            
            # 如果沒有找到 Prompt (回傳 None)，發送尚未更新的訊息
            if eng_prompt is None or stat_prompt is None:
                await message.author.send(
                    f"⚠️ **系統尚未更新此題目 / Topic Not Updated**\n\n"
                    f"題目名稱：{html_title}\n"
                    f"系統目前尚未設定此題目的評分標準，無法進行評分。\n"
                    f"System has not updated grading criteria for this topic yet.\n\n"
                    f"請確認您上傳的是正確的作業檔案，或稍後再試。\n"
                    f"Please make sure you uploaded the correct homework file, or try again later."
                )
                print(f"🛑 題目 '{html_title}' 未設定 Prompt，停止處理")
                os.remove(temp_path)
                try: await message.delete()
                except: pass
                return

            # 取得嘗試次數
            max_attempt = self.db.get_max_attempt(user_id, question_title)
            attempt_number = max_attempt + 1
            print(f"🔄 嘗試次數: {attempt_number} (Discord ID: {user_id}, 題目: {question_title})")

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
                try: await message.delete()
                except: pass
                return

            # 建立安全的檔名與路徑
            safe_class_name = self.get_safe_filename(class_name)
            folder_name = student_number if student_number else str(db_student_id)
            safe_folder_name = self.get_safe_filename(folder_name)

            uploads_class_dir = os.path.join(UPLOADS_DIR, safe_class_name)
            uploads_student_dir = os.path.join(uploads_class_dir, safe_folder_name)
            reports_class_dir = os.path.join(REPORTS_DIR, safe_class_name)
            reports_student_dir = os.path.join(reports_class_dir, safe_folder_name)

            os.makedirs(uploads_student_dir, exist_ok=True)
            os.makedirs(reports_student_dir, exist_ok=True)

            # 保存上傳檔案
            save_path, drive_id = await FileHandler.save_upload_file(
                file, 
                user_id, 
                uploads_student_dir, 
                file.filename,
                html_title,
                class_name, 
                student_number or student_id_from_html,
                db_student_name, 
                attempt_number,
            )

            if save_path is None:
                # 本地保存失敗
                await message.author.send("❌ **檔案保存失敗 / File Save Failed**\n\n系統無法保存您的上傳檔案，請稍後再試。\nSystem cannot save your uploaded file, please try again later.")
                await self.notify_administrators(
                    "本地保存失敗",
                    f"用戶: {db_student_name}\n檔案: {file.filename}\n班級: {class_name}\n本地路徑: {save_path}",
                    severity="warning"
                )
                return

            if drive_id is None:
                # Google Drive 上傳失敗
                await self.notify_administrators(
                    "Google Drive 上傳失敗",
                    f"用戶: {db_student_name}\n檔案: {file.filename}\n班級: {class_name}\n本地路徑: {save_path}",
                    severity="warning"
                )

            # 檔案成功保存後才刪除上傳訊息
            try:
                await message.delete()
                print("✅ 已刪除上傳訊息")
            except (discord.Forbidden, discord.NotFound):
                print("⚠️ 無法刪除上傳訊息（可能權限不足或訊息已被刪除）")

            # 刪除臨時檔案
            os.remove(temp_path)

            # 發送處理中訊息
            processing_msg = await message.author.send(
                f"🔄 **正在處理您的作業 / Processing Your Homework**\n\n"
                f"📝 題目 / Question：{html_title}\n"
                f"🔢 第 {attempt_number} 次提交 / Submission #{attempt_number}\n"
                f"⏳ 請稍候，系統正在進行AI評分...\n"
                f"⏳ Please wait, AI grading in progress..."
            )

            # ✅ 記錄開始時間
            start_time = time.time()

            try:
                # 更新進度
                await processing_msg.edit(content=
                    f"🔄 **正在處理您的作業 / Processing Your Homework**\n\n"
                    f"📝 題目 / Question：{html_title}\n"
                    f"🔢 第 {attempt_number} 次提交 / Submission #{attempt_number}\n"
                    f"📖 正在進行英語評分...\n"
                    f"📖 English grading in progress..."
                )
                
                # 評分開始
                print("評分開始")
                eng_start = time.time()
                
                # 執行英語評分
                messages_eng = GradingService.create_messages(eng_prompt, db_student_name, answer_text)
                eng_feedback = await asyncio.wait_for(
                    GradingService.generate_feedback(messages_eng),
                    timeout=300.0
                )
                
                # ✅ 計算英語評分用時
                eng_duration = time.time() - eng_start
                print(f"✅ 英語評分完成 (用時: {eng_duration:.2f}秒)")
                
                # 更新進度
                await processing_msg.edit(content=
                    f"🔄 **正在處理您的作業 / Processing Your Homework**\n\n"
                    f"📝 題目 / Question：{html_title}\n"
                    f"🔢 第 {attempt_number} 次提交 / Submission #{attempt_number}\n"
                    f"✅ 英語評分完成 ({eng_duration:.1f}秒)\n"
                    f"📊 正在進行統計評分...\n"
                    f"📊 Statistics grading in progress..."
                )

                # ✅ 統計評分開始時間
                stat_start = time.time()
                
                # 執行統計評分
                messages_stat = GradingService.create_messages(stat_prompt, db_student_name, answer_text)
                stats_feedback = await asyncio.wait_for(
                    GradingService.generate_feedback(messages_stat),
                    timeout=300.0
                )
                
                # ✅ 計算統計評分用時
                stat_duration = time.time() - stat_start
                print(f"✅ 統計評分完成 (用時: {stat_duration:.2f}秒)")
                
                # 更新進度
                await processing_msg.edit(content=
                    f"🔄 **正在處理您的作業 / Processing Your Homework**\n\n"
                    f"📝 題目 / Question：{html_title}\n"
                    f"🔢 第 {attempt_number} 次提交 / Submission #{attempt_number}\n"
                    f"✅ 英語評分完成 ({eng_duration:.1f}秒)\n"
                    f"✅ 統計評分完成 ({stat_duration:.1f}秒)\n"
                    f"📄 正在生成報告...\n"
                    f"📄 Generating report..."
                )
                
                # ✅ 修正：使用 FileHandler.generate_and_save_report
                report_path, report_filename, report_drive_id = await FileHandler.generate_and_save_report(
                    db_student_name=db_student_name,
                    student_number=student_number,
                    student_id_from_html=student_id_from_html,
                    question_title=html_title,
                    attempt_number=attempt_number,
                    answer_text=answer_text,
                    eng_feedback_clean=eng_feedback,
                    stats_feedback_clean=stats_feedback,
                    reports_student_dir=reports_student_dir,
                    class_name=class_name,
                    student_id=student_number or student_id_from_html,
                )

                if not report_path:
                    await processing_msg.edit(content="❌ 報告生成失敗 / Report generation failed")
                    return
                
                # ✅ 計算總用時
                total_duration = time.time() - start_time
                
                # 發送完成訊息（包含用時資訊）
                await processing_msg.edit(content=
                    f"✅ **作業處理完成 / Homework Processing Complete**\n\n"
                    f"📝 題目 / Question：{html_title}\n"
                    f"🔢 第 {attempt_number} 次提交 / Submission #{attempt_number}\n"
                    f"✅ 英語評分完成 ({eng_duration:.1f}秒)\n"
                    f"✅ 統計評分完成 ({stat_duration:.1f}秒)\n"
                    f"✅ 報告已生成\n"
                    f"⏱️ 總處理時間 / Total time：{total_duration:.1f} 秒\n\n"
                    f"📊 評分報告已保存，您可以使用 `!my-submissions` 查看所有提交記錄\n"
                    f"📊 Grading report saved, use `!my-submissions` to view all submissions"
                )
                
                # 發送報告文件
                with open(report_path, 'rb') as f:
                    await message.author.send(
                        f"📄 **評分報告 / Grading Report**",
                        file=discord.File(f, filename=report_filename)
                    )

            except (asyncio.TimeoutError, openai.error.Timeout) as e:
                # ✅ 超時錯誤也顯示已用時間
                elapsed_time = time.time() - start_time
                print(f"⏱️ 捕獲到超時錯誤: {type(e).__name__} (已用時: {elapsed_time:.2f}秒)")
                
                await processing_msg.edit(content=
                    f"⏱️ AI評分連線超時，請稍後再試。\n"
                    f"⏱️ AI grading connection timed out, please try again later.\n\n"
                    f"已處理時間 / Elapsed time：{elapsed_time:.1f} 秒"
                )
                
                await self.notify_administrators(
                    "AI 評分超時", 
                    f"用戶: {db_student_name}\n題目: {html_title}\n錯誤類型: {type(e).__name__}\n已用時: {elapsed_time:.1f}秒", 
                    severity="warning"
                )
                
                # 清理暫存檔
                try:
                    if os.path.exists(save_path):
                        os.remove(save_path)
                except:
                    pass
                return

            except openai.error.InvalidRequestError as e:
                # 處理無效請求錯誤
                print(f"❌ OpenAI API 請求錯誤: {e}")
                await processing_msg.edit(content=f"❌ API 請求錯誤 / API Request Error：{e}")
                
                await self.notify_administrators(
                    "OpenAI API 請求錯誤",
                    f"用戶: {db_student_name}\n題目: {html_title}\n錯誤: {e}",
                    severity="error"
                )
                return

            except Exception as e:
                await processing_msg.edit(content=f"❌ 評分過程發生錯誤 / Error during grading：{e}")
                print(f"❌ AI評分錯誤: {e}")
                traceback.print_exc()
                
                await self.notify_administrators(
                    "AI 評分錯誤",
                    f"用戶: {db_student_name}\n題目: {html_title}",
                    error_details=str(e),
                    severity="error"
                )
                return

            # ========== 即時解析成績與寫入資料庫 ==========
            print(f"💾 正在解析成績並寫入資料庫...")
            try:
                # 讀取剛剛生成的 HTML 報告檔案進行成績解析
                with open(report_path, "r", encoding="utf-8") as f:
                    html_content = f.read()
                
                parsed_data, ordered_keys = extract_scores_from_html_string(html_content)
                
                db_insert_success = self.db.insert_submission(
                    discord_id=user_id,
                    student_name=db_student_name,
                    student_number=student_number or student_id_from_html,
                    question_title=html_title,
                    attempt_number=attempt_number,
                    html_path=save_path,
                    parsed_scores=parsed_data,  # 傳入成績字典
                    score_keys=ordered_keys     # 傳入欄位順序
                )
                
                if db_insert_success:
                    print(f"✅ 提交記錄已成功寫入資料庫")
                    print(f"   - Discord ID: {user_id}")
                    print(f"   - 學號: {student_number or student_id_from_html}")
                    print(f"   - 題目: {html_title}")
                    print(f"   - 嘗試次數: {attempt_number}")
                else:
                    print(f"⚠️ 提交記錄寫入資料庫失敗（方法返回 False）")
                    # 即使資料庫寫入失敗，仍繼續發送報告給用戶
                    
            except TypeError as type_error:
                print(f"❌ 參數類型錯誤: {type_error}")
                import traceback
                traceback.print_exc()
                await processing_msg.edit(
                    content=f"⚠️ 報告已生成，但記錄寫入資料庫時發生參數錯誤\n"
                            f"⚠️ Report generated, but database write parameter error occurred\n"
                            f"錯誤訊息 / Error: {type_error}\n\n"
                            f"請聯繫管理員檢查系統設定"
                )
            except Exception as db_error:
                print(f"❌ 資料庫寫入錯誤: {db_error}")
                import traceback
                traceback.print_exc()
                # 即使資料庫寫入失敗，仍繼續發送報告給用戶
                await processing_msg.edit(
                    content=f"⚠️ 報告已生成，但記錄寫入資料庫時發生錯誤\n"
                            f"⚠️ Report generated, but database write error occurred\n"
                            f"錯誤訊息 / Error: {db_error}"
                )
            
            # ========== 結束資料庫寫入 ==========

        except Exception as e:
            await message.author.send(f"❌ 處理檔案時發生錯誤 / Error processing file：{e}")
            print(f"❌ _process_html_file 錯誤: {e}")
            traceback.print_exc()

    async def on_close(self):
        """機器人關閉時的清理工作"""
        if self.session:
            await self.session.close()
        self.db.close()

    def run(self):
        """啟動機器人"""
        self.client.run(DISCORD_TOKEN)

    async def assign_role_after_login(self, user, class_name):
        """登入成功後自動分配身分組"""
        try:
            # 獲取所有 guild（伺服器）
            guilds = self.client.guilds
            if not guilds:
                print("❌ 找不到任何伺服器")
                return False
            
            # 使用第一個伺服器（通常機器人只在一個伺服器中）
            guild = guilds[0]
            
            # 獲取 member 物件
            member = guild.get_member(user.id)
            if not member:
                print(f"❌ 在伺服器中找不到用戶 {user.id}")
                return False
            
            # 根據班級名稱決定要分配的身分組
            role_mapping = {
                "NCUFN": (NCUFN_ROLE_ID, NCUFN_ROLE_NAME),
                "NCUEC": (NCUEC_ROLE_ID, NCUEC_ROLE_NAME),
                "CYCUIUBM": (CYCUIUBM_ROLE_ID, CYCUIUBM_ROLE_NAME),
                "HWIS": (HWIS_ROLE_ID, HWIS_ROLE_NAME),
            }
            
            if class_name not in role_mapping:
                print(f"❌ 未知的班級名稱: {class_name}")
                return False
            
            role_id, role_name = role_mapping[class_name]
            
            # 嘗試透過 ID 獲取身分組
            role = None
            if role_id:
                role = discord.utils.get(guild.roles, id=role_id)
            
            # 如果透過 ID 找不到，嘗試透過名稱
            if role is None and role_name:
                role = discord.utils.get(guild.roles, name=role_name)
            
            if role is None:
                print(f"❌ 找不到身分組: {class_name} (ID: {role_id}, Name: {role_name})")
                return False
            
            # 檢查用戶是否已經有這個身分組
            if role in member.roles:
                print(f"✅ 用戶 {user.id} 已經擁有身分組 {role.name}")
                return True
            
            # 分配身分組
            await member.add_roles(role, reason=f"Auto-assigned after login (class: {class_name})")
            print(f"✅ 已為用戶 {user.id} 分配身分組 {role.name}")
            return True
            
        except Exception as e:
            print(f"❌ 分配身分組失敗: {e}")
            traceback.print_exc()
            return False

    async def handle_password_login(self, message):
        """處理密碼登入邏輯 - 支援私訊和班級頻道"""
        try:
            user_id = message.author.id
            
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
                    f"ℹ️ **您已經登入過系統 / You have already logged in**\n\n"
                    f"📋 帳號資訊 / Account info：\n"
                    f"• 學號 / Student ID：`{student_number}`\n"
                    f"• 班級 / Class：`{class_name}`\n\n"
                    f"💡 您可以直接開始使用系統功能\n"
                    f"💡 You can start using system features now"
                )
                try:
                    # 只在非私訊時刪除訊息
                    if not isinstance(message.channel, discord.DMChannel):
                        await message.delete()
                except:
                    pass
                return

            # ✅ 檢查是否為私訊
            is_dm = isinstance(message.channel, discord.DMChannel)
            
            # 解析指令 - 只支援 !login 學號 密碼
            parts = message.content.split(maxsplit=2)

            if len(parts) != 3:
                # 登入需要身分組
                member = message.guild.get_member(user_id)
                
                await message.author.send(
                    "❌ **登入指令格式錯誤 / Login command format error**\n\n"
                    f"✅ 正確使用方式 / Correct usage：\n"
                    f"`!login 學號 密碼`\n"
                    f"`!login student_id password`\n\n"
                    f"💡 提示：您也可以在私訊中使用此指令\n"
                    f"💡 Tip: You can also use this command in DM"
                )
                try:
                    if not is_dm:
                        await message.delete()
                except:
                    pass
                return

            student_number = parts[1]
            password = parts[2]

            if is_dm:
                print(f"🔐 用戶 {user_id} 在私訊中嘗試登入，學號: {student_number}")
            else:
                print(f"🔐 用戶 {user_id} 在班級頻道嘗試登入，學號: {student_number}")

            # 班級頻道登入：限制在對應班級中查找
            guild = self.client.guilds[0] if self.client.guilds else None
            member = guild.get_member(user_id) if guild else None
            
            # 根據用戶身分組驗證登入
            success = await self.verify_and_login(message.author, student_number, password)
            
            if success:
                await message.author.send(
                    f"✅ **登入成功！/ Login Successful!**\n\n"
                    f"🎉 您可以開始上傳作業檔案進行評分了！\n"
                    f"🎉 You can now upload homework for grading!"
                )
                print(f"✅ 用戶 {user_id} 登入成功")
            else:
                await message.author.send(
                    f"❌ **登入失敗 / Login Failed**\n\n"
                    f"可能的原因 / Possible reasons：\n"
                    f"• 學號 `{student_number}` 不存在於班級中\n"
                    f"  Student ID does not exist in any class\n"
                    f"• 密碼錯誤 / Incorrect password\n"
                    f"• 該學號已綁定其他 Discord 帳號\n"
                    f"  Already bound to another Discord account\n\n"
                    f"💡 提示：您可以在私訊中使用 `!login` 指令\n"
                    f"   系統會在所有班級中查找您的帳號\n"
                    f"💡 Tip: Use `!login` in DM to search all classes"
                )
                print(f"❌ 用戶 {user_id} 在班級頻道登入失敗")

            try:
                await message.delete()
            except:
                pass

        except Exception as e:
            await message.author.send(f"❌ 登入過程發生錯誤 / Error during login：{e}")
            print(f"❌ 登入過程發生錯誤: {e}")
            traceback.print_exc()

    async def export_class_scores(self, message):
        """助教專用：抓取班級特定題目的所有成績並匯出 Excel"""
        try:
            parts = message.content.split()
            if len(parts) < 3:
                await message.author.send(
                    "❌ **指令格式錯誤**\n正確用法：`!score <班級名稱> <題目代碼>`\n例如：`!score NCUFN Four-Step_Final`"
                )
                return

            class_name = parts[1]
            question_title = " ".join(parts[2:])
            
            # 從資料庫獲取全班歷次成績
            records = self.db.get_all_scores_for_class(class_name, question_title)
            
            # 1. 如果連名單都空了，代表「班級名稱」打錯
            if not records:
                await message.author.send(f"⚠️ 找不到班級 `{class_name}` 的學生名單，請確認「班級代碼」是否正確。")
                return

            # 2. 檢查全班是否有人交作業
            has_submissions = any(row[2] is not None for row in records)
            
            # 根據是否有繳交紀錄，決定要發送給助教的訊息文字
            if not has_submissions:
                reply_text = (
                    f"📝 **目前尚無人繳交**\n"
                    f"班級 `{class_name}` 目前**還沒有任何學生**繳交 `{question_title}` 的作業喔！\n"
                    f"*💡 系統已為您匯出全班的空白名單。如果您確定已經有學生繳交，請檢查「題目代碼」是否有錯字！*"
                )
            else:
                reply_text = (
                    f"✅ **成績匯出成功**\n"
                    f"這是一份包含 `{class_name}` 班級所有學生 `{question_title}` **歷次提交**成績的 Excel 表格："
                )

            # --- 下方的組裝邏輯完全不變 ---
            all_data = []
            master_keys = ["學號", "姓名", "作答次數"]

            for row in records:
                stu_num, stu_name, attempt, scores_json, keys_json = row
                data_dict = {
                    "學號": stu_num,
                    "姓名": stu_name,
                    "作答次數": attempt if attempt else ""
                }
                
                if scores_json:
                    scores = json.loads(scores_json)
                    data_dict.update(scores)
                    
                    keys = json.loads(keys_json) if keys_json else []
                    for k in keys:
                        if k not in master_keys:
                            master_keys.append(k)
                            
                all_data.append(data_dict)

            df = pd.DataFrame.from_records(all_data)
            final_cols = [c for c in master_keys if c in df.columns]
            df = df[final_cols]

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name="Scores")
            buffer.seek(0)

            file = discord.File(fp=buffer, filename=f"{class_name}_{question_title}_All_Scores.xlsx")
            
            # 使用我們剛剛設定好的動態文字回覆
            await message.author.send(reply_text, file=file)

        except Exception as e:
            await message.author.send(f"❌ 匯出成績時發生錯誤：{e}")
            print(f"❌ export_class_scores 錯誤: {e}")
            import traceback
            traceback.print_exc()

    async def verify_and_login(self, user, student_number, password):
        """在所有班級中驗證學號密碼並完成登入"""
        try:
            print(f"🔍 開始在所有班級中驗證學號: {student_number}")
            print(f"🆔 用戶 Discord ID: {user.id}")

            # 步驟1：檢查該 Discord ID 是否已經被其他學生使用
            existing_student_with_discord = self.db.get_student_by_discord_id(str(user.id))
            if existing_student_with_discord:
                print(f"❌ Discord ID {user.id} 已被其他學生使用: {existing_student_with_discord}")
                await user.send(
                    f"❌ **您的 Discord 帳號已綁定到其他學生記錄**\n"
                    f"❌ **Your Discord account is bound to another student record**\n\n"
                    f"📋 已綁定的帳號資訊 / Bound account info：\n"
                    f"• 學號 / Student ID：{existing_student_with_discord[2] if len(existing_student_with_discord) > 2 else '未知/Unknown'}\n"
                    f"• 班級 / Class：{existing_student_with_discord[5] if len(existing_student_with_discord) > 5 else existing_student_with_discord[4] if len(existing_student_with_discord) > 4 else '未知/Unknown'}\n\n"
                    f"💡 每個 Discord 帳號只能綁定一個學生記錄\n"
                    f"💡 Each Discord account can only be bound to one student record"
                )
                return False

            # 步驟2：從資料庫查詢學生資料（不限制班級）
            student_data = self.db.get_student_by_student_id_with_password(student_number)
            if not student_data:
                print(f"❌ 找不到學號 {student_number} 的資料")
                return False

            print(f"✅ 找到學生資料: {student_data}")

            # 步驟3：解析學生資料
            student_number_db, student_name, discord_id_in_db, db_class_id, class_name_db, stored_password = student_data

            print(
                f"📋 學生完整資料: 學號={student_number_db}, 姓名={student_name}, Discord ID='{discord_id_in_db}', 班級ID={db_class_id}, 班級名={class_name_db}"
            )

            # 步驟4：驗證密碼
            print(f"🔐 資料庫中的密碼: {stored_password}, 輸入的密碼: {password}")
            if stored_password != password:
                print("❌ 密碼不匹配")
                return False

            print("✅ 密碼驗證成功")

            role_assigned = await self.assign_role_after_login(user, class_name_db)
            if not role_assigned:
                print(f"⚠️ 警告：為用戶 {user.id} 分配身分組 {class_name_db} 失敗，但將繼續登入流程")

            # 步驟5：檢查該學號的 Discord 綁定狀態
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
                        f"✅ **您已經登入過系統！/ You have already logged in!**\n\n"
                        f"📋 **帳號資訊 / Account Info：**\n"
                        f"👤 學號 / Student ID：`{student_number}`\n"
                        f"📛 姓名 / Name：`{student_name}`\n"
                        f"🏫 班級 / Class：`{class_name_db}`\n"
                        f"🔗 Discord ID 已綁定 / Discord ID bound\n\n"
                        f"🎓 您可以開始上傳作業檔案進行評分了！\n"
                        f"🎓 You can now upload homework files for grading!"
                    )
                    return True
                else:
                    # 已綁定其他 Discord 帳號
                    print(f"❌ 該學號已綁定其他 Discord 帳號: {discord_id_in_db}")
                    return False
            else:
                # Discord ID 為空值，可以直接綁定
                print(f"✅ 學號的 Discord ID 為空值，可以進行綁定")

            # 步驟6：更新 Discord ID
            print(f"🔗 開始將 Discord ID {user.id} 綁定到學號 {student_number} (班級: {class_name_db})")

            try:
                # 使用班級ID和學號的組合來更新
                update_result = self.db.update_student_discord_id_by_student_id_and_class(student_number, str(user.id), db_class_id)
                print(f"📝 資料庫更新結果: {update_result}")

                if update_result:
                    print("✅ Discord ID 更新成功")
                    
                    # ✅ 合併成一條訊息
                    await user.send(
                        f"✅ **登入成功！/ Login Successful!**\n\n"
                        f"📋 **帳號資訊 / Account Info：**\n"
                        f"👤 學號 / Student ID：`{student_number}`\n"
                        f"📛 姓名 / Name：`{student_name}`\n"
                        f"🏫 班級 / Class：`{class_name_db}`\n"
                        f"🎉 **您可以開始使用系統功能了！/ You can now use the system!**\n"
                        f"• 前往您的班級頻道上傳 HTML 作業檔案\n"
                        f"  Go to your class channel to upload HTML homework\n"
                        f"• 使用 `!help` 查看完整指令說明\n"
                        f"  Use `!help` to view complete instructions\n"
                        f"• 使用 `!my-submissions` 查看提交記錄\n"
                        f"  Use `!my-submissions` to view submission history"
                    )
                    
                    return True
                else:
                    print("❌ Discord ID 更新失敗 - 更新操作返回 False")
                    return False

            except Exception as update_error:
                error_msg = str(update_error)
                print(f"❌ 更新 Discord ID 時發生異常: {error_msg}")
                return False
                
        except Exception as e:
            print(f"驗證過程詳細錯誤: {e}")
            traceback.print_exc()
            return False

    def get_user_class_from_roles(self, member):
        """從用戶的身分組中獲取班級名稱"""
        if not member:
            return None
        
        for role in member.roles:
            if role.name in self.role_to_class:
                return self.role_to_class[role.name]
        
        return None

    def get_safe_filename(self, filename):
        """將字串轉換為安全的檔名"""
        # 移除或替換不安全的字元
        import re
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
        return safe_name

    async def show_my_submissions(self, message):
        """顯示用戶的作業提交記錄"""
        try:
            user_id = str(message.author.id)
            
            # 獲取學生資料
            student_data = self.db.get_student_by_discord_id(user_id)
            if not student_data:
                await message.author.send(
                    "❌ 找不到您的學生資料 / Cannot find your student data\n\n"
                    "請先使用以下方式登入：\n"
                    "Please login first using one of the following methods:\n\n"
                    "• `!login 學號 密碼` - 使用學號密碼登入"
                )
                try:
                    await message.delete()
                except:
                    pass
                return

            # 解析學生資料
            if len(student_data) >= 6:
                db_student_id, db_student_name, student_number, discord_id, class_id, class_name = student_data
            else:
                await message.author.send("❌ 學生資料格式錯誤")
                try:
                    await message.delete()
                except:
                    pass
                return

            # 獲取提交記錄（使用 Discord ID 查詢）
            submissions = self.db.get_student_submissions(user_id)
            
            if not submissions:
                await message.author.send(
                    f"📋 **作業提交記錄 / Submission History**\n\n"
                    f"👤 學生 / Student：{db_student_name}\n"
                    f"🆔 學號 / Student ID：{student_number}\n"
                    f"🏫 班級 / Class：{class_name}\n\n"
                    f"📝 您還沒有提交過任何作業\n"
                    f"📝 You haven't submitted any homework yet\n\n"
                    f"💡 請上傳 HTML 作業檔案到您的班級頻道進行評分\n"
                    f"💡 Please upload HTML homework file to your class channel for grading"
                )

            else:
                # 按題目分組統計
                from collections import defaultdict
                questions_dict = defaultdict(list)
                
                for submission in submissions:
                    if len(submission) >= 5:
                        file_id, upload_time, file_path, question_title, attempt_number = submission
                        questions_dict[question_title].append({
                            'attempt': attempt_number,
                            'time': upload_time,
                            'file_id': file_id
                        })
                
                # 建立回覆訊息
                response = (
                    f"📋 **作業提交記錄 / Submission History**\n\n"
                    f"👤 學生 / Student：{db_student_name}\n"
                    f"🆔 學號 / Student ID：{student_number}\n"
                    f"🏫 班級 / Class：{class_name}\n"
                    f"📊 總提交次數 / Total submissions：{len(submissions)} 次\n"
                    f"📝 題目數量 / Questions：{len(questions_dict)} 題\n\n"
                )
                
                # 列出每個題目的提交記錄
                for idx, (question_title, attempts) in enumerate(sorted(questions_dict.items()), 1):
                    response += f"**{idx}. {question_title}**\n"
                    response += f"   • 提交次數 / Submissions：{len(attempts)} 次\n"
                    
                    # 列出最近3次提交
                    sorted_attempts = sorted(attempts, key=lambda x: x['attempt'], reverse=True)[:3]
                    for attempt_info in sorted_attempts:
                        response += f"   • 第 {attempt_info['attempt']} 次 - {attempt_info['time'][:19]}\n"
                    
                    if len(attempts) > 3:
                        response += f"   • ... 及其他 {len(attempts) - 3} 次提交\n"
                    response += "\n"
                
                await message.author.send(response)
            
            try:
                await message.delete()
            except:
                pass
                
        except Exception as e:
            await message.author.send(f"❌ 查詢提交記錄時發生錯誤 / Error querying submissions：{e}")
            print(f"❌ _show_my_submissions 錯誤: {e}")
            import traceback
            traceback.print_exc()
