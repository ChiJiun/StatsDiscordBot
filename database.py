import sqlite3
import hashlib
from datetime import datetime
from config import DB_PATH
import os


class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.cur = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        """建立資料表結構"""
        # 建立班級資料表
        self.cur.execute(
            """
            CREATE TABLE IF NOT EXISTS Classes (
                class_id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name VARCHAR(50) NOT NULL UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # 建立學生資料表
        self.cur.execute(
            """
            CREATE TABLE IF NOT EXISTS Students (
                student_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name VARCHAR(100) NOT NULL,
                student_number VARCHAR(50),
                discord_id VARCHAR(20) UNIQUE,
                class_id INTEGER NOT NULL,
                password VARCHAR(50),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (class_id) REFERENCES Classes(class_id) ON DELETE CASCADE
            )
        """
        )

        # 建立作業檔案資料表
        self.cur.execute(
            """
            CREATE TABLE IF NOT EXISTS AssignmentFiles (
                file_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id VARCHAR(20) NOT NULL,
                class_id INTEGER NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                file_type VARCHAR(50) DEFAULT 'grading',
                question_number INTEGER,
                attempt_number INTEGER,
                score REAL,
                feedback TEXT,
                upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (class_id) REFERENCES Classes(class_id) ON DELETE CASCADE
            )
        """
        )

        # 創建索引以提高查詢效能
        self.cur.execute("CREATE INDEX IF NOT EXISTS idx_students_discord_id ON Students(discord_id)")
        self.cur.execute("CREATE INDEX IF NOT EXISTS idx_students_class_id ON Students(class_id)")
        self.cur.execute("CREATE INDEX IF NOT EXISTS idx_students_number ON Students(student_number)")
        self.cur.execute("CREATE INDEX IF NOT EXISTS idx_assignment_files_student_id ON AssignmentFiles(student_id)")
        self.cur.execute("CREATE INDEX IF NOT EXISTS idx_assignment_files_question ON AssignmentFiles(question_number)")

        self.conn.commit()

    def create_class(self, class_name):
        """建立新班級"""
        try:
            self.cur.execute("INSERT INTO Classes (class_name) VALUES (?)", (class_name,))
            self.conn.commit()
            return self.cur.lastrowid
        except sqlite3.IntegrityError:
            return None

    def get_all_classes(self):
        """獲取所有班級"""
        self.cur.execute("SELECT class_id, class_name FROM Classes ORDER BY class_name")
        return self.cur.fetchall()

    def create_student(self, student_name, discord_id, class_id, password=None, student_number=None):
        """建立新學生"""
        try:
            self.cur.execute(
                """
                INSERT INTO Students (student_name, student_number, discord_id, class_id, password) 
                VALUES (?, ?, ?, ?, ?)
            """,
                (student_name, student_number, discord_id, class_id, password),
            )
            self.conn.commit()
            return self.cur.lastrowid
        except sqlite3.IntegrityError as e:
            print(f"❌ 創建學生失敗: {e}")
            return None

    def get_student_by_discord_id(self, discord_id):
        """根據 Discord ID 獲取學生資料"""
        self.cur.execute(
            """
            SELECT s.student_id, s.student_name, s.student_number, s.discord_id, s.class_id, c.class_name
            FROM Students s
            LEFT JOIN Classes c ON s.class_id = c.class_id
            WHERE s.discord_id = ?
        """,
            (discord_id,),
        )
        return self.cur.fetchone()

    def get_student_by_student_id_with_password(self, student_number):
        """根據學號獲取學生資料（包含密碼）"""
        self.cur.execute(
            """
            SELECT s.student_number, s.student_name, s.discord_id, s.class_id, c.class_name, s.password
            FROM Students s
            JOIN Classes c ON s.class_id = c.class_id
            WHERE s.student_number = ?
        """,
            (student_number,),
        )
        return self.cur.fetchone()

    def get_students_by_class_id(self, class_id):
        """獲取指定班級ID的所有學生（統一方法）"""
        self.cur.execute(
            """
            SELECT student_id, student_name, student_number, discord_id 
            FROM Students 
            WHERE class_id = ?
            ORDER BY student_name
        """,
            (class_id,),
        )
        return self.cur.fetchall()

    # 保留向後相容性的別名
    def get_students_by_class(self, class_id):
        """獲取指定班級的學生（向後相容性別名）"""
        return self.get_students_by_class_id(class_id)

    def update_student_discord_id_by_student_id(self, student_number, discord_id):
        """根據學號更新學生的 Discord ID（向後相容性方法）"""
        try:
            # 檢查是否有重複學號
            self.cur.execute("SELECT COUNT(*) FROM Students WHERE student_number = ?", (student_number,))
            count = self.cur.fetchone()[0]

            if count > 1:
                print(f"⚠️ 警告：發現 {count} 個學號為 {student_number} 的學生，建議使用 update_student_discord_id_by_student_id_and_class 方法")

            self.cur.execute(
                """
                UPDATE Students 
                SET discord_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE student_number = ? AND (discord_id IS NULL OR discord_id = '')
            """,
                (discord_id, student_number),
            )
            self.conn.commit()
            affected_rows = self.cur.rowcount

            if affected_rows == 0 and count > 0:
                # 檢查是否是因為已經有 Discord ID
                self.cur.execute(
                    "SELECT discord_id FROM Students WHERE student_number = ? AND discord_id IS NOT NULL AND discord_id != ''", (student_number,)
                )
                existing_discord = self.cur.fetchone()
                if existing_discord:
                    print(f"⚠️ 學號 {student_number} 已綁定 Discord ID: {existing_discord[0]}")

            return affected_rows > 0

        except Exception as e:
            print(f"更新 Discord ID 失敗: {e}")
            self.conn.rollback()
            return False

    def update_student_discord_id_by_student_id_and_class(self, student_number, discord_id, class_id):
        """根據學號和班級ID更新學生的 Discord ID（避免重複學號問題）"""
        try:
            self.cur.execute(
                """
                UPDATE Students 
                SET discord_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE student_number = ? AND class_id = ? AND (discord_id IS NULL OR discord_id = '')
            """,
                (discord_id, student_number, class_id),
            )
            self.conn.commit()
            affected_rows = self.cur.rowcount
            print(f"📝 更新結果：受影響的行數 = {affected_rows}")
            return affected_rows > 0
        except Exception as e:
            print(f"更新 Discord ID 失敗: {e}")
            self.conn.rollback()
            return False

    def get_student_by_student_id_with_password_and_class(self, student_number, class_id):
        """根據學號和班級ID獲取學生資料（包含密碼）"""
        self.cur.execute(
            """
            SELECT s.student_number, s.student_name, s.discord_id, s.class_id, c.class_name, s.password
            FROM Students s
            JOIN Classes c ON s.class_id = c.class_id
            WHERE s.student_number = ? AND s.class_id = ?
        """,
            (student_number, class_id),
        )
        return self.cur.fetchone()

    def get_student_by_number(self, student_number):
        """根據學號獲取學生資料"""
        self.cur.execute(
            """
            SELECT s.student_id, s.student_name, s.student_number, s.discord_id, s.class_id, c.class_name
            FROM Students s
            LEFT JOIN Classes c ON s.class_id = c.class_id
            WHERE s.student_number = ?
        """,
            (student_number,),
        )
        return self.cur.fetchone()

    def get_students_by_class(self, class_id):
        """獲取指定班級的學生"""
        self.cur.execute(
            """
            SELECT student_id, student_name, student_number, discord_id 
            FROM Students 
            WHERE class_id = ?
            ORDER BY student_name
        """,
            (class_id,),
        )
        return self.cur.fetchall()

    def get_class_by_name(self, class_name):
        """根據班級名稱獲取班級資料"""
        self.cur.execute("SELECT class_id, class_name FROM Classes WHERE class_name = ?", (class_name,))
        return self.cur.fetchone()

    def get_max_attempt(self, user_id, question_number):
        """獲取使用者對特定題目的最大嘗試次數"""
        self.cur.execute(
            """
            SELECT MAX(attempt_number) FROM AssignmentFiles
            WHERE student_id = ? AND question_number = ?
        """,
            (user_id, question_number),
        )
        result = self.cur.fetchone()[0]
        return result if result is not None else 0

    def insert_submission(self, user_id, student_name, student_id, question_number, attempt_number, html_path, score, feedback):
        """插入作業提交記錄"""
        try:
            # 獲取學生資料
            student_data = self.get_student_by_discord_id(user_id)
            if not student_data:
                print(f"❌ 找不到用戶 {user_id} 的學生資料")
                return False

            # 解包學生資料
            # get_student_by_discord_id 返回：(student_id, student_name, student_number, discord_id, class_id, class_name)
            db_student_id, db_student_name, student_number, discord_id, class_id, class_name = student_data

            self.cur.execute(
                """
                INSERT INTO AssignmentFiles 
                (student_id, class_id, file_path, file_type, question_number, attempt_number, score, feedback, upload_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(user_id),  # student_id (使用 Discord ID)
                    class_id,  # class_id
                    html_path,  # file_path
                    "grading",  # file_type
                    question_number,  # question_number
                    attempt_number,  # attempt_number
                    score,  # score
                    feedback,  # feedback
                    datetime.now().isoformat(),  # upload_time
                ),
            )

            self.conn.commit()
            print(f"✅ 已記錄提交：用戶 {user_id}, 題目 {question_number}, 嘗試 {attempt_number}")
            return True

        except Exception as e:
            print(f"❌ 插入提交記錄失敗: {e}")
            import traceback

            traceback.print_exc()
            return False

    def get_student_submissions(self, student_id, question_number=None):
        """獲取學生的作業提交記錄"""
        if question_number:
            self.cur.execute(
                """
                SELECT file_id, upload_time, file_path, attempt_number, score, feedback
                FROM AssignmentFiles 
                WHERE student_id = ? AND question_number = ? AND file_type = 'grading'
                ORDER BY attempt_number DESC
            """,
                (student_id, question_number),
            )
        else:
            self.cur.execute(
                """
                SELECT file_id, upload_time, file_path, question_number, attempt_number, score, feedback
                FROM AssignmentFiles 
                WHERE student_id = ? AND file_type = 'grading'
                ORDER BY question_number, attempt_number DESC
            """,
                (student_id,),
            )
        return self.cur.fetchall()

    def get_class_statistics(self, class_id):
        """獲取班級統計資料"""
        self.cur.execute(
            """
            SELECT 
                COUNT(DISTINCT s.student_id) as total_students,
                COUNT(af.file_id) as total_submissions,
                AVG(af.score) as avg_score
            FROM Students s
            LEFT JOIN AssignmentFiles af ON s.student_id = af.student_id
            WHERE s.class_id = ?
        """,
            (class_id,),
        )
        return self.cur.fetchone()

    def close(self):
        """關閉資料庫連線"""
        self.conn.close()

    def login_with_password(self, password, discord_id):
        """
        使用密碼登入並綁定Discord ID

        Args:
            password (str): 學生密碼（原始密碼）
            discord_id (str): Discord ID

        Returns:
            dict: 登入結果
        """
        try:
            # 查找有此密碼且Discord ID為空的學生
            self.cur.execute(
                """
                SELECT s.student_id, s.student_name, s.student_number, s.discord_id, s.class_id, c.class_name, s.password
                FROM Students s
                JOIN Classes c ON s.class_id = c.class_id
                WHERE s.password = ? AND s.discord_id IS NULL
            """,
                (password,),
            )

            student_record = self.cur.fetchone()

            if not student_record:
                # 檢查是否密碼錯誤或已被使用
                self.cur.execute("SELECT COUNT(*) FROM Students WHERE password = ?", (password,))
                password_exists = self.cur.fetchone()[0] > 0

                if password_exists:
                    return {"success": False, "error": "此密碼已被其他帳戶使用，每個密碼只能綁定一個Discord帳戶"}
                else:
                    return {"success": False, "error": "密碼錯誤，請檢查您輸入的密碼是否正確"}

            student_id, student_name, student_number, current_discord_id, class_id, class_name, stored_password = student_record

            # 更新Discord ID
            self.cur.execute(
                """
                UPDATE Students 
                SET discord_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE student_id = ?
            """,
                (discord_id, student_id),
            )

            self.conn.commit()

            # 返回更新後的學生資料
            updated_student_data = (student_id, student_name, student_number, discord_id, class_id, class_name)

            return {"success": True, "student_data": updated_student_data, "message": f"成功綁定Discord ID到學生帳戶：{student_name}"}

        except Exception as e:
            return {"success": False, "error": f"登入過程中發生資料庫錯誤：{e}"}

    def update_student_discord_id(self, student_id, discord_id):
        """
        更新學生的Discord ID

        Args:
            student_id (int): 學生ID
            discord_id (str): Discord ID

        Returns:
            bool: 更新是否成功
        """
        try:
            # 檢查Discord ID是否已被其他學生使用
            self.cur.execute("SELECT student_id FROM Students WHERE discord_id = ? AND student_id != ?", (discord_id, student_id))
            existing_student = self.cur.fetchone()

            if existing_student:
                return False

            self.cur.execute(
                """
                UPDATE Students 
                SET discord_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE student_id = ?
            """,
                (discord_id, student_id),
            )

            self.conn.commit()
            return self.cur.rowcount > 0

        except Exception as e:
            print(f"更新Discord ID時發生錯誤: {e}")
            return False

    def get_student_by_password(self, password):
        """
        根據密碼查找學生

        Args:
            password (str): 學生密碼

        Returns:
            tuple: 學生資料 (student_id, student_name, discord_id, class_id, class_name) 或 None
        """
        try:
            self.cur.execute(
                """
                SELECT s.student_id, s.student_name, s.discord_id, s.class_id, c.class_name
                FROM Students s
                JOIN Classes c ON s.class_id = c.class_id
                WHERE s.password = ?
            """,
                (password,),
            )

            return self.cur.fetchone()

        except Exception as e:
            print(f"查找學生時發生錯誤: {e}")
            return None
