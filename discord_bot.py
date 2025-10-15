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

        # 新增：追蹤等待登入的用戶
        self.pending_login = {}  # {user_id: {'step': 'student_id'/'password', 'student_id': '', 'class_name': ''}}

        # 身分組對應班級名稱 - 改為英文
        self.role_to_class = {
            NCUFN_ROLE_NAME: "NCUFN",
            NCUEC_ROLE_NAME: "NCUEC",
            CYCUIUBM_ROLE_NAME: "CYCUIUBM",
        }

        # 設定事件處理器
        self.client.event(self.on_ready)
        self.client.event(self.on_message)
        self.client.event(self.on_close)

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
                name="📋 其他指令",
                value="• `!help` - 查看詳細指令\n• `!my-roles` - 查看我的身分組\n• `!class-stats` - 查看班級統計\n• 直接上傳 `.html` 檔案進行評分",
                inline=False,
            )

            embed.set_footer(text="HTML 作業評分機器人 | ⚠️ 身分組一旦選擇無法更改，請謹慎選擇！")

            # 如果不是強制更新，檢查是否已存在歡迎訊息
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

        # 檢查是否為私訊中的登入步驟
        if isinstance(message.channel, discord.DMChannel):
            if int(user_id) in self.pending_login:
                if await self._handle_login_step(message):
                    return

        # 處理幫助指令
        if message.content.lower() == "!help":
            is_admin = message.author.guild_permissions.administrator

            help_text = (
                "📚 **HTML作業處理機器人指令**:\n"
                "1. 直接上傳 `.html` 檔案 - 系統會自動處理並評分\n"
                "2. `!help` - 顯示此幫助訊息\n"
                "3. `!join NCUFN` - 加入中央大學財金系\n"
                "4. `!join NCUEC` - 加入中央大學經濟系\n"
                "5. `!join CYCUIUBM` - 加入中原大學國際商學學士學位學程\n"
                "6. `!login <學號>   <密碼>` - 使用密碼登入系統（如果老師有提供）\n"
                "7. `!my-roles` - 查看我的身分組\n"
                "8. `!class-stats` - 查看班級統計資料\n"
                "9. `!my-submissions` - 查看我的提交記錄\n"
            )

            if is_admin:
                help_text += (
                    "\n🔧 **管理員專用指令**:\n"
                    "• `!update-welcome` - 更新歡迎訊息\n"
                    "• `!class-list` - 查看所有班級\n"
                    "• `!student-list [班級]` - 查看學生清單\n"
                )

            help_text += "\n⚠️ **重要提醒**：每人只能選擇一個身分組，選擇後無法更改！"

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
            self.force_welcome = True
            await self._send_welcome_message()
            self.force_welcome = False
            await message.author.send("✅ 歡迎訊息已更新！")
            try:
                await message.delete()
            except:
                pass
            return

        # 處理 HTML 檔案上傳
        if message.attachments:
            # 檢查是否在歡迎頻道
            if message.channel.id == WELCOME_CHANNEL_ID:
                await message.author.send("❌ 歡迎頻道僅供領取身分組使用，請到其他頻道上傳 HTML 檔案進行評分。")
                try:
                    await message.delete()
                except:
                    pass
                return

            # 虸理檔案
            for file in message.attachments:
                if file.filename.lower().endswith(".html"):
                    await self._process_html_file(message, file, user_id)
                    return

            # 如果有附件但不是 HTML 檔案
            await message.author.send("❌ 請只上傳 `.html` 檔案進行評分。")
            try:
                await message.delete()
            except:
                pass
            return

        # 自動刪除其他訊息
        try:
            await message.delete()
            if message.channel.id == WELCOME_CHANNEL_ID:
                await message.author.send("ℹ️ 歡迎頻道僅供使用身分組指令。\n請使用 `!join ROLE_NAME` 領取身分組，或使用 `!help` 查看可用指令。")
            else:
                await message.author.send("ℹ️ 此頻道僅允許使用指令或上傳 HTML 檔案。\n請使用 `!help` 查看可用指令。")
        except (discord.Forbidden, discord.NotFound):
            pass

    async def _handle_join_role(self, message, role_type):
        """處理加入身分組請求"""
        guild = message.guild
        member = guild.get_member(message.author.id)

        if not member:
            await message.author.send("❌ 找不到成員資訊")
            return

        try:
            # 檢查用戶是否已經是系統學生
            student_data = self.db.get_student_by_discord_id(str(message.author.id))
            if student_data:
                await message.author.send(f"❌ 您已經是 **{student_data[4]}** 的學生，無法更改班級！")
                try:
                    await message.delete()
                except:
                    pass
                return

            # 檢查用戶是否已經有任何身分組
            existing_roles = [role for role in member.roles if role.name in [NCUFN_ROLE_NAME, NCUEC_ROLE_NAME, CYCUIUBM_ROLE_NAME]]

            if existing_roles:
                await message.author.send(f"❌ 您已經擁有身分組 **{existing_roles[0].name}**，每人只能擁有一個身分組！")
                try:
                    await message.delete()
                except:
                    pass
                return

            # 根據指令類型決定身分組和班級 - 改為英文班級名稱
            role_name = ""
            role_id = 0
            class_name = ""

            if role_type == "NCUFN":
                role_name = NCUFN_ROLE_NAME
                role_id = NCUFN_ROLE_ID
                class_name = "NCUFN"
            elif role_type == "NCUEC":
                role_name = NCUEC_ROLE_NAME
                role_id = NCUEC_ROLE_ID
                class_name = "NCUEC"
            elif role_type == "CYCUIUBM":
                role_name = CYCUIUBM_ROLE_NAME
                role_id = CYCUIUBM_ROLE_ID
                class_name = "CYCUIUBM"
            else:
                await message.author.send("❌ 無效的身分組類型，請使用 NCUFN、NCUEC 或 CYCUIUBM")
                return

            # 查找或創建班級
            class_data = self.db.get_class_by_name(class_name)
            if not class_data:
                class_id = self.db.create_class(class_name)
            else:
                class_id = class_data[0]

            # 創建學生記錄
            student_id = self.db.create_student(member.display_name, str(message.author.id), class_id)  # 使用 Discord 顯示名稱

            if not student_id:
                await message.author.send("❌ 創建學生記錄失敗，可能 Discord ID 已存在")
                return

            # 查找或創建 Discord 身分組
            role = None
            if role_id != 0:
                role = guild.get_role(role_id)

            if not role:
                role = discord.utils.get(guild.roles, name=role_name)

            if not role:
                permissions = discord.Permissions()
                permissions.send_messages = True
                permissions.attach_files = True
                permissions.read_messages = True
                role = await guild.create_role(name=role_name, permissions=permissions, reason="自動創建身分組")

            # 給予用戶身分組
            await member.add_roles(role, reason=f"透過指令加入身分組: {role_name}")

            await message.author.send(
                f"✅ 成功加入 **{role_name}** 身分組！\n"
                f"📚 您已被分配到班級：**{class_name}**\n"
                f"👤 學生ID：{student_id}\n"
                f"⚠️ 注意：每人只能擁有一個身分組，您無法再更改。"
            )

            try:
                await message.delete()
            except:
                pass

        except Exception as e:
            await message.author.send(f"❌ 加入身分組時發生錯誤: {e}")

    async def _show_user_roles(self, message):
        """顯示用戶的身分組和班級資訊"""
        # 從資料庫獲取學生資訊
        student_data = self.db.get_student_by_discord_id(str(message.author.id))

        if student_data:
            student_id, student_name, discord_id, class_id, class_name = student_data
            roles_text = (
                f"📋 **您的學生資訊**:\n" f"👤 姓名: {student_name}\n" f"🏫 班級: {class_name}\n" f"🆔 學生ID: {student_id}\n" f"⚠️ 身分組無法更改"
            )
        else:
            roles_text = "📋 您尚未選擇身分組\n" "使用 `!join ROLE_NAME` 來選擇身分組\n" "⚠️ 注意：每人只能選擇一個身分組！"

        await message.author.send(roles_text)

        try:
            await message.delete()
        except:
            pass

    async def _show_class_stats(self, message):
        """顯示班級統計資料"""
        student_data = self.db.get_student_by_discord_id(str(message.author.id))

        if not student_data:
            await message.author.send("❌ 您尚未加入任何班級，請先使用 `!join` 指令選擇身分組")
            try:
                await message.delete()
            except:
                pass
            return

        student_id, student_name, discord_id, class_id, class_name = student_data
        stats = self.db.get_class_statistics(class_id)

        if stats:
            total_students, total_submissions, avg_score = stats
            avg_score = round(avg_score, 2) if avg_score else 0

            stats_text = (
                f"📊 **{class_name} 班級統計**:\n"
                f"👥 學生總數: {total_students}\n"
                f"📝 作業提交總數: {total_submissions}\n"
                f"📈 平均分數: {avg_score}\n"
            )
        else:
            stats_text = f"📊 **{class_name}** 暫無統計資料"

        await message.author.send(stats_text)

        try:
            await message.delete()
        except:
            pass

    async def _show_my_submissions(self, message):
        """顯示用戶的提交記錄"""
        student_data = self.db.get_student_by_discord_id(str(message.author.id))

        if not student_data:
            await message.author.send("❌ 您尚未加入任何班級，請先使用 `!join` 指令選擇身分組")
            try:
                await message.delete()
            except:
                pass
            return

        student_id = student_data[0]
        submissions = self.db.get_student_submissions(student_id)

        if not submissions:
            await message.author.send("📝 您還沒有任何作業提交記錄")
        else:
            submissions_text = "📝 **您的作業提交記錄**:\n\n"
            for submission in submissions[:10]:  # 只顯示最近10筆
                if len(submission) >= 7:  # 包含 question_number 的完整記錄
                    file_id, upload_time, file_path, question_title, attempt_number, score, feedback = submission
                    # 截斷過長的題目標題
                    display_title = question_title[:30] + "..." if len(question_title) > 30 else question_title
                    submissions_text += (
                        f"📋 {display_title}\n"
                        f"🔄 第{attempt_number}次嘗試\n"
                        f"📅 提交時間: {upload_time}\n"
                        f"📊 分數: {score}\n"
                        f"────────────────\n"
                    )
                else:  # 特定題目的記錄
                    file_id, upload_time, file_path, attempt_number, score, feedback = submission
                    submissions_text += f"🗂️ 第{attempt_number}次嘗試\n" f"📅 提交時間: {upload_time}\n" f"📊 分數: {score}\n" f"────────────────\n"

            if len(submissions) > 10:
                submissions_text += f"\n... 還有 {len(submissions) - 10} 筆記錄"

        await message.author.send(submissions_text)

        try:
            await message.delete()
        except:
            pass

    async def _process_html_file(self, message, file, user_id):
        """處理 HTML 檔案上傳"""
        try:
            # 檢查檔案類型
            if not file.filename.lower().endswith(".html"):
                await message.author.send("❌ 請上傳 .html 檔案")
                # 刪除上傳訊息
                try:
                    await message.delete()
                except (discord.Forbidden, discord.NotFound):
                    pass
                return

            # 獲取學生資料
            student_data = self.db.get_student_by_discord_id(user_id)
            if not student_data:
                await message.author.send("❌ 找不到您的學生資料，請先加入身分組或使用密碼登入")
                # 刪除上傳訊息
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
                await message.author.send("❌ 找不到您的班級資料")
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

            # 設定檔案路徑
            save_path = os.path.join(uploads_student_dir, f"{user_id}_{file.filename}")

            try:
                # 先下載並保存檔案
                await file.save(save_path)
                print(f"✅ 檔案已保存到: {save_path}")

                # 檔案成功保存後才刪除上傳訊息
                try:
                    await message.delete()
                    print("✅ 已刪除上傳訊息")
                except (discord.Forbidden, discord.NotFound):
                    print("⚠️ 無法刪除上傳訊息（可能權限不足或訊息已被刪除）")

                # 解析 HTML 內容
                html_title = extract_html_title(save_path)
                student_name, student_id_from_html, answer_text = extract_html_content(save_path)

                print(f"📝 HTML 標題: {html_title}")
                print(f"👤 學生姓名: {student_name}")
                print(f"🆔 學號: {student_id_from_html}")
                print(f"📄 答案內容長度: {len(answer_text)} 字元")

                # 檢查是否有答案內容
                if not answer_text or answer_text.strip() == "":
                    await message.author.send("❌ 未找到答案內容，請確認您的 HTML 檔案包含作答區域")
                    return

                # 使用 HTML 標題作為題目標題，如果沒有則使用檔案名稱
                question_title = html_title if html_title else file.filename
                print(f"📝 題目標題: {question_title}")

                # 獲取下一次嘗試編號（使用題目標題）
                max_attempt = self.db.get_max_attempt(user_id, question_title)
                attempt_number = max_attempt + 1

                print(f"🔄 嘗試次數: {attempt_number}")

                # 發送處理中訊息
                processing_msg = await message.author.send(f"🔄 正在處理您的「{question_title}」第{attempt_number}次提交，請稍候...")

                # 執行英語評分
                eng_feedback = await self.grading_service.grade_homework(
                    answer_text=answer_text, question_number=question_title, prompt_type="eng", html_title=html_title  # 傳遞題目標題
                )

                # 執行統計評分
                stats_feedback = await self.grading_service.grade_homework(
                    answer_text=answer_text, question_number=question_title, prompt_type="stats", html_title=html_title  # 傳遞題目標題
                )

                print(f"✅ 英語評分完成")
                print(f"✅ 統計評分完成")

                # 解析評分結果
                eng_score, eng_band, eng_feedback_clean = self.grading_service.parse_grading_result(eng_feedback)
                stats_score, stats_band, stats_feedback_clean = self.grading_service.parse_grading_result(stats_feedback)

                print(f"📊 英語分數: {eng_score}, 等級: {eng_band}")
                print(f"📊 統計分數: {stats_score}, 等級: {stats_band}")

                # 生成 HTML 報告
                html_report = generate_html_report(
                    student_name=db_student_name,
                    student_id=student_number or student_id_from_html,
                    question_number=question_title,  # 使用題目標題
                    attempt=attempt_number,
                    answer_text=answer_text,
                    eng_score=eng_score,
                    eng_band=eng_band,
                    eng_feedback=eng_feedback_clean,
                    stats_score=stats_score,
                    stats_band=stats_band,
                    stats_feedback=stats_feedback_clean,
                )

                # 保存報告檔案（使用安全的檔名）
                safe_question_title = self._get_safe_filename(question_title)
                report_filename = f"{db_student_name}_{student_number or student_id_from_html}_{safe_question_title}_第{attempt_number}次.html"
                report_path = os.path.join(reports_student_dir, report_filename)

                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(html_report)

                print(f"✅ 報告已保存到: {report_path}")

                # 記錄到資料庫
                overall_score = (eng_score + stats_score) / 2
                combined_feedback = f"英語評分:\n{eng_feedback_clean}\n\n統計評分:\n{stats_feedback_clean}"

                success = self.db.insert_submission(
                    user_id=user_id,
                    student_name=db_student_name,
                    student_id=student_number or student_id_from_html,
                    question_number=question_title,  # 使用題目標題
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
                await processing_msg.edit(content="✅ 處理完成！正在發送結果...")

                # 發送結果
                result_text = (
                    f"✅ **評分完成**\n"
                    f"👤 學生：{db_student_name}\n"
                    f"📝 題目：{question_title}\n"
                    f"🔄 嘗試：第{attempt_number}次\n"
                    f"📊 英語分數：{eng_score} (等級: {eng_band})\n"
                    f"📊 統計分數：{stats_score} (等級: {stats_band})\n"
                    f"📈 總分：{overall_score:.1f}\n"
                )

                await message.author.send(result_text)

                # 發送報告檔案
                with open(report_path, "rb") as f:
                    await message.author.send(f"📄 **詳細評分報告**", file=discord.File(f, report_filename))

                print(f"✅ 已發送結果給用戶")

            except Exception as e:
                print(f"❌ 處理檔案時發生錯誤: {e}")
                import traceback

                traceback.print_exc()

                await message.author.send(f"❌ 處理檔案時發生錯誤: {e}")
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

    def _get_safe_filename(self, filename):
        """產生安全的檔名"""
        import re

        # 移除或替換不安全的字符
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", filename)
        return safe_name.strip()

    async def on_close(self):
        """機器人關閉時的清理工作"""
        if self.session:
            await self.session.close()
        self.db.close()

    def run(self):
        """啟動機器人"""
        self.client.run(DISCORD_TOKEN)

    async def _handle_password_login(self, message):
        """處理密碼登入邏輯"""
        try:
            user_id = message.author.id

            # 檢查用戶是否已經登入過
            existing_student = self.db.get_student_by_discord_id(str(user_id))
            if existing_student:
                await message.author.send(f"❌ 您已經登入過系統，學號：{existing_student[0]}，班級：{existing_student[4]}")
                try:
                    await message.delete()
                except:
                    pass
                return

            # 解析指令
            parts = message.content.split(maxsplit=2)

            if len(parts) == 1:  # 只有 !login
                # 開始登入流程
                self.pending_login[user_id] = {"step": "student_number"}

                embed = discord.Embed(title="🔐 學生登入系統", description="請輸入您的學號：", color=0x3498DB)
                embed.add_field(name="📝 說明", value="請輸入您在資料庫中註冊的學號", inline=False)

                await message.author.send(embed=embed)

            elif len(parts) == 3:  # !login 學號 密碼
                student_number = parts[1]
                password = parts[2]

                # 直接驗證登入
                if await self._verify_and_login(message.author, student_number, password):
                    await message.author.send("✅ 登入成功！")
                else:
                    await message.author.send("❌ 學號或密碼錯誤，請檢查後重試")
            else:
                await message.author.send(
                    "❌ 登入指令格式錯誤\n" "使用方式：\n" "• `!login` - 進入互動式登入流程\n" "• `!login 學號 密碼` - 直接登入"
                )

            try:
                await message.delete()
            except:
                pass

        except Exception as e:
            await message.author.send(f"❌ 登入過程發生錯誤：{e}")
            # 清除登入狀態
            if user_id in self.pending_login:
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
            student_number_db, student_name, discord_id_in_db, class_id, class_name, stored_password = student_data

            print(f"資料庫中的密碼: {stored_password}, 輸入的密碼: {password}")

            # 驗證密碼
            if stored_password != password:
                print("❌ 密碼不匹配")
                return False

            print("✅ 密碼驗證成功")

            # 檢查該學號是否已經綁定其他 Discord 帳號
            if discord_id_in_db and discord_id_in_db != str(user.id):
                await user.send(f"❌ 該學號已經綁定其他 Discord 帳號")
                return False

            # 更新 Discord ID
            if self.db.update_student_discord_id_by_student_id(student_number, str(user.id)):
                await user.send(
                    f"✅ 登入成功！\n" f"👤 學號：{student_number}\n" f"📛 姓名：{student_name}\n" f"🏫 班級：{class_name}\n" f"🔗 Discord ID 已綁定"
                )

                # 給予相應的身分組
                await self._assign_role_after_login(user, class_name)
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
