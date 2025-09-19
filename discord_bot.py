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
from html_parser import extract_html_content
from grading import GradingService
from report_generator import generate_html_report


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

        # 設定事件處理器
        self.client.event(self.on_ready)
        self.client.event(self.on_message)
        self.client.event(self.on_close)

    async def on_ready(self):
        """機器人啟動時執行的事件處理器"""
        self.session = aiohttp.ClientSession()
        self.grading_service = GradingService(self.session)
        print(f"✅ HTML作業處理機器人已啟動: {self.client.user}")

        # 發送歡迎訊息
        await self._send_welcome_message()

    async def _send_welcome_message(self):
        """發送歡迎訊息到指定頻道"""
        if WELCOME_CHANNEL_ID == 0:
            print("⚠️ 未設定歡迎頻道 ID，跳過發送歡迎訊息")
            return

        try:
            channel = self.client.get_channel(WELCOME_CHANNEL_ID)
            if not channel:
                print(f"❌ 找不到頻道 ID: {WELCOME_CHANNEL_ID}")
                return

            # 如果設定強制更新，先刪除舊的歡迎訊息
            if self.force_welcome:
                print("🔄 強制更新模式：正在刪除舊的歡迎訊息...")
                async for message in channel.history(limit=50):
                    if (
                        message.author == self.client.user
                        and message.embeds
                        and len(message.embeds) > 0
                        and ("歡迎來到統計學AI系統" in message.embeds[0].title or "歡迎來到 HTML 作業評分系統" in message.embeds[0].title)
                    ):
                        try:
                            await message.delete()
                            print("✅ 已刪除舊的歡迎訊息")
                        except discord.Forbidden:
                            print("❌ 無權限刪除舊訊息")
                        except Exception as e:
                            print(f"❌ 刪除舊訊息時發生錯誤: {e}")

            # 創建歡迎訊息嵌入
            embed = discord.Embed(
                title="🎓 歡迎來到統計學AI系統",
                description="⚠️ **重要提醒：請先將 Stats_bot 加入好友\n每人只能選擇一個身分組，選擇後無法更改！**\n請謹慎選擇您的身分組",
                color=0x3498DB,
            )

            embed.add_field(name="🏦 中央大學財金系 (NCUFN)", value="使用指令: `!join NCUFN`", inline=True)

            embed.add_field(name="📈 中央大學經濟系 (NCUEC)", value="使用指令: `!join NCUEC`", inline=True)

            embed.add_field(name="🌐 中原大學國際商學學士學位學程 (CYCUIUBM)", value="使用指令: `!join CYCUIUBM`", inline=True)

            embed.add_field(
                name="📋 其他指令", value="• `!help` - 查看詳細指令\n• `!my-roles` - 查看我的身分組\n• 直接上傳 `.html` 檔案進行評分", inline=False
            )

            embed.set_footer(text="HTML 作業評分機器人 | ⚠️ 身分組一旦選擇無法更改，請謹慎選擇！")

            # 如果不是強制更新，檢查是否已存在歡迎訊息 - 修正標題檢查
            if not self.force_welcome:
                async for message in channel.history(limit=50):
                    if (
                        message.author == self.client.user
                        and message.embeds
                        and len(message.embeds) > 0
                        and ("歡迎來到統計學AI系統" in message.embeds[0].title or "歡迎來到 HTML 作業評分系統" in message.embeds[0].title)
                    ):
                        print("✅ 歡迎訊息已存在，跳過發送")
                        return

            # 發送新的歡迎訊息
            welcome_message = await channel.send(embed=embed)
            print(f"✅ 歡迎訊息已發送到頻道: {channel.name}")

        except Exception as e:
            print(f"❌ 發送歡迎訊息時發生錯誤: {e}")

    async def on_message(self, message):
        """處理收到的 Discord 訊息事件"""
        if message.author.bot:
            return

        user_id = str(message.author.id)

        # 處理幫助指令
        if message.content.lower() == "!help":
            help_text = (
                "📚 **HTML作業處理機器人指令**:\n"
                "1. 直接上傳 `.html` 檔案 - 系統會自動處理並評分\n"
                "2. `!help` - 顯示此幫助訊息\n"
                "3. `!join NCUFN` - 加入中央大學財金系\n"
                "4. `!join NCUEC` - 加入中央大學經濟系\n"
                "5. `!join CYCUIUBM` - 加入中原大學國際商學學士學位學程\n"
                "6. `!my-roles` - 查看我的身分組\n"
                "\n⚠️ **重要提醒**：每人只能選擇一個身分組，選擇後無法更改！"
            )
            await message.author.send(help_text)

            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass
            except Exception as e:
                print(f"刪除訊息時發生錯誤: {e}")
            return

        # 處理加入身分組指令
        if message.content.lower().startswith("!join"):
            parts = message.content.split()
            if len(parts) != 2:
                await message.author.send("❌ 使用方法: `!join NCUFN` 或 `!join NCUEC` 或 `!join CYCUIUBM`\n⚠️ 注意：每人只能選擇一個身分組！")
                try:
                    await message.delete()
                except:
                    pass
                return

            role_type = parts[1].upper()
            await self._handle_join_role(message, role_type)
            return

        # 處理離開身分組指令（已禁用）
        if message.content.lower().startswith("!leave"):
            await self._handle_leave_role(message, "")
            return

        # 處理查看身分組指令
        if message.content.lower() == "!my-roles":
            await self._show_user_roles(message)
            return

        # 添加管理員指令來手動更新歡迎訊息
        if message.content.lower() == "!update-welcome" and message.author.guild_permissions.administrator:
            self.force_welcome = True
            await self._send_welcome_message()
            self.force_welcome = False
            await message.author.send("✅ 歡迎訊息已更新！")
            try:
                await message.delete()
            except:
                pass
            return

        # 處理 HTML 檔案上傳 - 排除歡迎頻道
        if message.attachments:
            # 檢查是否在歡迎頻道
            if message.channel.id == WELCOME_CHANNEL_ID:
                # 在歡迎頻道，不接收任何檔案，直接刪除並提醒
                await message.author.send("❌ 歡迎頻道僅供領取身分組使用，請到其他頻道上傳 HTML 檔案進行評分。")
                try:
                    await message.delete()
                except:
                    pass
                return

            # 不在歡迎頻道，正常處理檔案
            for file in message.attachments:
                if file.filename.lower().endswith(".html"):
                    await self._process_html_file(message, file, user_id)
                    return

            # 如果有附件但不是 HTML 檔案，刪除訊息並提醒用戶
            await message.author.send("❌ 請只上傳 `.html` 檔案進行評分。")
            try:
                await message.delete()
            except:
                pass
            return

        # 自動刪除所有其他訊息（非指令且非檔案的普通訊息）
        try:
            await message.delete()
            # 根據頻道給出不同的提醒訊息
            if message.channel.id == WELCOME_CHANNEL_ID:
                await message.author.send("ℹ️ 歡迎頻道僅供使用身分組指令。\n" "請使用 `!join ROLE_NAME` 領取身分組，或使用 `!help` 查看可用指令。")
            else:
                await message.author.send("ℹ️ 此頻道僅允許使用指令或上傳 HTML 檔案。\n" "請使用 `!help` 查看可用指令。")
            print(f"🧹 已自動刪除用戶 {message.author.name} 的非指令訊息: {message.content[:50]}...")
        except (discord.Forbidden, discord.NotFound):
            print(f"⚠️ 無法刪除用戶 {message.author.name} 的訊息")
        except Exception as e:
            print(f"❌ 刪除訊息時發生錯誤: {e}")

    async def _handle_join_role(self, message, role_type):
        """處理加入身分組請求"""
        guild = message.guild
        member = guild.get_member(message.author.id)

        if not member:
            await message.author.send("❌ 找不到成員資訊")
            return

        try:
            # 檢查用戶是否已經有任何身分組
            existing_roles = [role for role in member.roles if role.name in [NCUFN_ROLE_NAME, NCUEC_ROLE_NAME, CYCUIUBM_ROLE_NAME]]

            if existing_roles:
                await message.author.send(f"❌ 您已經擁有身分組 **{existing_roles[0].name}**，每人只能擁有一個身分組！")
                try:
                    await message.delete()
                except:
                    pass
                return

            # 根據指令類型決定身分組
            role_name = ""
            role_id = 0

            if role_type == "NCUFN":
                role_name = NCUFN_ROLE_NAME
                role_id = NCUFN_ROLE_ID
            elif role_type == "NCUEC":
                role_name = NCUEC_ROLE_NAME
                role_id = NCUEC_ROLE_ID
            elif role_type == "CYCUIUBM":
                role_name = CYCUIUBM_ROLE_NAME
                role_id = CYCUIUBM_ROLE_ID
            else:
                await message.author.send("❌ 無效的身分組類型，請使用 NCUFN、NCUEC 或 CYCUIUBM")
                return

            print(f"👤 用戶 {message.author.name} 請求加入身分組: {role_name}")

            # 查找身分組
            role = None
            if role_id != 0:
                role = guild.get_role(role_id)
                print(f"🔍 使用 ID 查找身分組: {role_id}")

            if not role:
                role = discord.utils.get(guild.roles, name=role_name)
                print(f"🔍 使用名稱查找身分組: {role_name}")

            # 如果身分組不存在，創建新的
            if not role:
                print(f"🆕 身分組不存在，正在創建: {role_name}")
                permissions = discord.Permissions()
                permissions.send_messages = True
                permissions.attach_files = True
                permissions.read_messages = True

                role = await guild.create_role(name=role_name, permissions=permissions, reason="自動創建身分組")
                print(f"✅ 已創建新身分組: {role_name}")

            # 給予用戶身分組
            await member.add_roles(role, reason=f"透過指令加入身分組: {role_name}")
            await message.author.send(f"✅ 成功加入 **{role_name}** 身分組！\n⚠️ 注意：每人只能擁有一個身分組，您無法再更改。")
            print(f"✅ 用戶 {message.author.name} 成功加入身分組: {role_name}")

            # 刪除指令訊息
            try:
                await message.delete()
            except:
                pass

        except Exception as e:
            await message.author.send(f"❌ 加入身分組時發生錯誤: {e}")
            print(f"❌ 加入身分組錯誤: {e}")

    async def _handle_leave_role(self, message, role_name):
        """處理離開身分組請求 - 已禁用"""
        await message.author.send("❌ 抱歉，身分組一旦選擇就無法更改或離開。")

        # 刪除指令訊息
        try:
            await message.delete()
        except:
            pass

    async def _show_user_roles(self, message):
        """顯示用戶的身分組"""
        member = message.guild.get_member(message.author.id)

        if not member:
            await message.author.send("❌ 找不到成員資訊")
            return

        # 只顯示系統相關的身分組
        system_roles = [role.name for role in member.roles if role.name in [NCUFN_ROLE_NAME, NCUEC_ROLE_NAME, CYCUIUBM_ROLE_NAME]]

        if system_roles:
            roles_text = f"📋 **您的身分組**:\n• {system_roles[0]}\n\n⚠️ 身分組無法更改"
        else:
            roles_text = "📋 您尚未選擇身分組\n使用 `!join ROLE_NAME` 來選擇身分組\n⚠️ 注意：每人只能選擇一個身分組！"

        await message.author.send(roles_text)

        # 刪除指令訊息
        try:
            await message.delete()
        except:
            pass

    async def _process_html_file(self, message, file, user_id):
        """處理 HTML 檔案的主要邏輯"""
        await message.author.send("📝 收到HTML檔案，正在處理中...")

        os.makedirs(UPLOADS_DIR, exist_ok=True)
        save_path = f"{UPLOADS_DIR}/{user_id}_{file.filename}"

        try:
            await file.save(save_path)

            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass
            except Exception as e:
                print(f"刪除訊息時發生錯誤: {e}")

            # 解析 HTML 檔案
            student_name, student_id, answer_text = extract_html_content(save_path)
            question_number = 1
            attempt = self.db.get_max_attempt(user_id, question_number) + 1

            # 進行評分
            await message.author.send("🔍 正在進行英語評分...")
            eng_result = await self.grading_service.grade_homework(answer_text, question_number, "eng")
            eng_score, eng_band, eng_feedback = self.grading_service.parse_grading_result(eng_result)
            print(f"英語評分結果: Score={eng_score}, Band={eng_band}, Feedback前50字={eng_feedback[:50]}...")

            await message.author.send("📊 正在進行統計評分...")
            stats_result = await self.grading_service.grade_homework(answer_text, question_number, "stats")
            stats_score, stats_band, stats_feedback = self.grading_service.parse_grading_result(stats_result)
            print(f"統計評分結果: Score={stats_score}, Band={stats_band}, Feedback前50字={stats_feedback[:50]}...")

            # 生成報告
            html_report = generate_html_report(
                student_name,
                student_id,
                question_number,
                attempt,
                answer_text,
                eng_score,
                eng_band,
                eng_feedback,
                stats_score,
                stats_band,
                stats_feedback,
            )

            os.makedirs(REPORTS_DIR, exist_ok=True)
            report_path = f"{REPORTS_DIR}/{user_id}_{student_id}_{question_number}_{attempt}.html"
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(html_report)

            # 儲存到資料庫
            self.db.insert_submission(user_id, student_name, student_id, question_number, attempt, save_path, eng_score, eng_feedback)

            # 發送結果
            result_text = (
                f"✅ **評分完成**\n"
                f"學生: {student_name} ({student_id})\n"
                f"第{question_number}題 第{attempt}次嘗試\n"
                f"已完成英語與統計雙重評分\n"
            )

            await message.author.send(content=result_text, file=discord.File(report_path))

        except Exception as e:
            await message.author.send(f"❌ 處理檔案時發生錯誤: {e}")
            try:
                await message.delete()
            except:
                pass

    async def on_close(self):
        """機器人關閉時的清理工作"""
        if self.session:
            await self.session.close()
        self.db.close()

    def run(self):
        """啟動機器人"""
        self.client.run(DISCORD_TOKEN)
