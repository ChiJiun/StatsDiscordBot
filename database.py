import sqlite3
import hashlib
from datetime import datetime
from config import DB_PATH
import os
import json


class DatabaseManager:
    def __init__(self):
        # 當初始化 DatabaseManager 時，會自動連接/創建資料庫
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.cur = self.conn.cursor()
        # 自動創建所有必要的資料表
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
                user_id VARCHAR(20) NOT NULL,
                student_id VARCHAR(50),
                class_id INTEGER NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                file_type VARCHAR(50) DEFAULT 'grading',
                question_title VARCHAR(200),
                attempt_number INTEGER,
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
        self.cur.execute("CREATE INDEX IF NOT EXISTS idx_assignment_files_question ON AssignmentFiles(question_title)")

        try:
            self.cur.execute("ALTER TABLE AssignmentFiles ADD COLUMN parsed_scores TEXT")
            self.cur.execute("ALTER TABLE AssignmentFiles ADD COLUMN score_keys TEXT")
        except sqlite3.OperationalError:
            pass # 如果欄位已存在會觸發此錯誤，直接忽略即可，確保程式不會崩潰

        self.conn.commit()
        print("✅ 資料庫表格建立完成 / Database tables created")

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
        """獲取指定班級ID的所有學生"""
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

    def get_students_by_class(self, class_id):
        """獲取指定班級的學生（向後相容性別名）"""
        return self.get_students_by_class_id(class_id)

    def update_student_discord_id_by_student_id(self, student_number, discord_id):
        """根據學號更新學生的 Discord ID"""
        try:
            self.cur.execute("SELECT COUNT(*) FROM Students WHERE student_number = ?", (student_number,))
            count = self.cur.fetchone()[0]

            if count > 1:
                print(f"⚠️ 警告：發現 {count} 個學號為 {student_number} 的學生")

            self.cur.execute(
                """
                UPDATE Students 
                SET discord_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE student_number = ? AND (discord_id IS NULL OR discord_id = '')
            """,
                (discord_id, student_number),
            )
            self.conn.commit()
            return self.cur.rowcount > 0
        except Exception as e:
            print(f"更新 Discord ID 失敗: {e}")
            self.conn.rollback()
            return False

    def update_student_discord_id_by_student_id_and_class(self, student_number, discord_id, class_id):
        """根據學號和班級ID更新學生的 Discord ID"""
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
            return self.cur.rowcount > 0
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

    def get_class_by_name(self, class_name):
        """根據班級名稱獲取班級資料"""
        self.cur.execute("SELECT class_id, class_name FROM Classes WHERE class_name = ?", (class_name,))
        return self.cur.fetchone()

    def get_max_attempt(self, discord_id, question_title):
        """
        獲取使用者對特定題目的最大嘗試次數
        
        Args:
            discord_id (str): Discord ID（用於查詢的唯一標識）
            question_title (str): 題目標題
            
        Returns:
            int: 最大嘗試次數，如果沒有記錄則返回 0
        """
        self.cur.execute(
            """
            SELECT MAX(attempt_number) FROM AssignmentFiles
            WHERE user_id = ? AND question_title = ?
            """,
            (discord_id, question_title),
        )
        result = self.cur.fetchone()[0]
        print(f"🔍 查詢嘗試次數: Discord ID={discord_id}, 題目={question_title}, 結果={result if result is not None else 0}")
        return result if result is not None else 0

    # 替換原有的 insert_submission
    def insert_submission(self, discord_id, student_name, student_number, question_title, attempt_number, 
                         html_path, parsed_scores=None, score_keys=None):
        """插入作業提交記錄與解析成績"""
        try:
            # 獲取學生資料（通過 Discord ID）
            student_data = self.get_student_by_discord_id(discord_id)
            if not student_data:
                print(f"❌ 找不到 Discord ID {discord_id} 的學生資料")
                return False

            db_student_id, db_student_name, db_student_number, db_discord_id, class_id, class_name = student_data

            # 將成績字典與順序清單轉為 JSON 字串
            scores_json = json.dumps(parsed_scores, ensure_ascii=False) if parsed_scores else None
            keys_json = json.dumps(score_keys, ensure_ascii=False) if score_keys else None

            # 插入記錄，現在包含了 parsed_scores 和 score_keys
            self.cur.execute(
                """
                INSERT INTO AssignmentFiles 
                (user_id, student_id, class_id, file_path, file_type, question_title, attempt_number, 
                 upload_time, parsed_scores, score_keys)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(discord_id),
                    db_student_number or student_number,
                    class_id,
                    html_path,
                    "grading",
                    question_title,
                    attempt_number,
                    datetime.now().isoformat(),
                    scores_json,  # 儲存成績資料
                    keys_json     # 儲存欄位順序
                ),
            )

            self.conn.commit()
            print(f"✅ 已記錄提交：Discord ID={discord_id}, 學號={db_student_number or student_number}, 題目={question_title}, 嘗試={attempt_number}")
            return True

        except Exception as e:
            print(f"❌ 插入提交記錄失敗: {e}")
            import traceback
            traceback.print_exc()
            self.conn.rollback()
            return False

    # 新增給 TA 查詢成績用的方法
    def get_all_scores_for_class(self, class_name, question_title):
        """
        獲取某班級、特定題目的所有學生「歷次」成績
        先按學號排序，再按作答次數排序，讓同一個學生的紀錄排在一起
        """
        self.cur.execute("""
            SELECT 
                s.student_number, 
                s.student_name, 
                a.attempt_number, 
                a.parsed_scores, 
                a.score_keys
            FROM Students s
            JOIN Classes c ON s.class_id = c.class_id
            -- 使用 LEFT JOIN 確保就算沒繳交作業的學生也會出現在名單上 (成績空白)
            LEFT JOIN AssignmentFiles a ON s.student_number = a.student_id AND a.question_title = ?
            WHERE c.class_name = ?
            ORDER BY s.student_number ASC, a.attempt_number ASC
        """, (question_title, class_name))
        
        return self.cur.fetchall()

    def get_student_submissions(self, discord_id, question_title=None):
        """
        獲取學生的作業提交記錄
        
        Args:
            discord_id (str): Discord ID
            question_title (str, optional): 題目標題（如果指定則只查詢該題目）
            
        Returns:
            list: 提交記錄列表
        """
        if question_title:
            self.cur.execute(
                """
                SELECT file_id, upload_time, file_path, attempt_number
                FROM AssignmentFiles 
                WHERE user_id = ? AND question_title = ? AND file_type = 'grading'
                ORDER BY attempt_number DESC
            """,
                (discord_id, question_title),
            )
        else:
            self.cur.execute(
                """
                SELECT file_id, upload_time, file_path, question_title, attempt_number
                FROM AssignmentFiles 
                WHERE user_id = ? AND file_type = 'grading'
                ORDER BY question_title, attempt_number DESC
            """,
                (discord_id,),
            )
        return self.cur.fetchall()

    def get_submission_details(self, file_id):
        """獲取單一提交的詳細資訊"""
        self.cur.execute(
            """
            SELECT file_path
            FROM AssignmentFiles
            WHERE file_id = ?
        """,
            (file_id,),
        )
        result = self.cur.fetchone()
        if result:
            return {
                'file_path': result[0]
            }
        return None

    def get_class_statistics(self, class_id):
        """
        獲取班級統計資料
        
        Args:
            class_id (int): 班級 ID
            
        Returns:
            tuple: (學生總數, 作業提交總數)
        """
        self.cur.execute(
            """
            SELECT 
                COUNT(DISTINCT s.student_id) as total_students,
                COUNT(af.file_id) as total_submissions
            FROM Students s
            LEFT JOIN AssignmentFiles af ON s.discord_id = af.user_id
            WHERE s.class_id = ?
        """,
            (class_id,),
        )
        return self.cur.fetchone()

    def close(self):
        """關閉資料庫連線"""
        self.conn.close()

    def login_with_password(self, password, discord_id):
        """使用密碼登入並綁定Discord ID"""
        try:
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
                self.cur.execute("SELECT COUNT(*) FROM Students WHERE password = ?", (password,))
                password_exists = self.cur.fetchone()[0] > 0

                if password_exists:
                    return {"success": False, "error": "此密碼已被其他帳戶使用"}
                else:
                    return {"success": False, "error": "密碼錯誤"}

            student_id, student_name, student_number, current_discord_id, class_id, class_name, stored_password = student_record

            self.cur.execute(
                """
                UPDATE Students 
                SET discord_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE student_id = ?
            """,
                (discord_id, student_id),
            )

            self.conn.commit()

            updated_student_data = (student_id, student_name, student_number, discord_id, class_id, class_name)

            return {"success": True, "student_data": updated_student_data, "message": f"成功綁定：{student_name}"}

        except Exception as e:
            return {"success": False, "error": f"登入錯誤：{e}"}

    def update_student_discord_id(self, student_id, discord_id):
        """更新學生的Discord ID"""
        try:
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
        """根據密碼查找學生"""
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

    def get_or_create_student(self, student_name, student_number, class_id, password=None, discord_id=None):
        """
        檢查學生是否存在，如果存在則更新密碼，如果不存在則創建新學生
        
        Args:
            student_name (str): 學生姓名
            student_number (str): 學號（可選）
            class_id (int): 班級ID
            password (str): 密碼（可選）
            discord_id (str): Discord ID（可選）
            
        Returns:
            int or None: 學生ID，如果操作失敗返回None
        """
        try:
            # 優先通過學號檢查（如果提供學號）
            if student_number:
                existing = self.get_student_by_student_id_with_password_and_class(student_number, class_id)
                if existing:
                    # 更新密碼
                    self.cur.execute(
                        "UPDATE Students SET password = ?, updated_at = CURRENT_TIMESTAMP WHERE student_number = ? AND class_id = ?",
                        (password, student_number, class_id)
                    )
                    self.conn.commit()
                    return existing[0]  # 返回現有學生ID
            
            # 如果沒有學號或通過學號找不到，通過姓名和班級檢查
            self.cur.execute(
                "SELECT student_id FROM Students WHERE student_name = ? AND class_id = ?",
                (student_name, class_id)
            )
            existing = self.cur.fetchone()
            
            if existing:
                # 更新密碼
                self.cur.execute(
                    "UPDATE Students SET password = ?, updated_at = CURRENT_TIMESTAMP WHERE student_id = ?",
                    (password, existing[0])
                )
                self.conn.commit()
                return existing[0]  # 返回現有學生ID
            
            # 不存在，創建新學生
            return self.create_student(student_name, discord_id, class_id, password, student_number)
            
        except Exception as e:
            print(f"❌ 處理學生資料時發生錯誤: {e}")
            self.conn.rollback()
            return None

def main():
    """主程式 - 用於獨立運行資料庫管理"""
    import sys
    
    print("=" * 60)
    print("📊 統計學智慧評分系統 - 資料庫管理工具")
    print("📊 Statistics AI Grading System - Database Manager")
    print("=" * 60)
    
    try:
        # 初始化資料庫
        print("\n🔧 正在初始化資料庫 / Initializing database...")
        db = DatabaseManager()
        print("✅ 資料庫連接成功 / Database connected successfully")
        print(f"📁 資料庫路徑 / Database path: {DB_PATH}")
        
        # 顯示資料庫統計
        print("\n" + "=" * 60)
        print("📈 資料庫統計 / Database Statistics")
        print("=" * 60)
        
        # 顯示所有班級
        classes = db.get_all_classes()
        print(f"\n🏫 班級數量 / Number of classes: {len(classes)}")
        for class_id, class_name in classes:
            students = db.get_students_by_class_id(class_id)
            print(f"  • {class_name} (ID: {class_id}): {len(students)} 位學生 / students")
        
        # 顯示總學生數
        db.cur.execute("SELECT COUNT(*) FROM Students")
        total_students = db.cur.fetchone()[0]
        print(f"\n👥 總學生數 / Total students: {total_students}")
        
        # 顯示已綁定 Discord 的學生數
        db.cur.execute("SELECT COUNT(*) FROM Students WHERE discord_id IS NOT NULL AND discord_id != ''")
        bound_students = db.cur.fetchone()[0]
        print(f"🔗 已綁定 Discord / Discord bound: {bound_students}")
        print(f"⏳ 未綁定 Discord / Not bound: {total_students - bound_students}")
        
        # 顯示作業提交統計
        db.cur.execute("SELECT COUNT(*) FROM AssignmentFiles")
        total_submissions = db.cur.fetchone()[0]
        print(f"\n📝 總作業提交數 / Total submissions: {total_submissions}")
        
        # 互動式選單
        while True:
            print("\n" + "=" * 60)
            print("🔧 管理功能選單 / Management Menu")
            print("=" * 60)
            print("1. 查看所有班級 / View all classes")
            print("2. 查看班級學生列表 / View class students")
            print("3. 查看學生詳細資料 / View student details")
            print("4. 創建新班級 / Create new class")
            print("5. 資料庫完整統計 / Full database statistics")
            print("6. 檢查資料庫完整性 / Check database integrity")
            print("0. 退出 / Exit")
            
            choice = input("\n請選擇功能 / Please choose (0-6): ").strip()
            
            if choice == "1":
                show_all_classes(db)
            elif choice == "2":
                show_class_students(db)
            elif choice == "3":
                show_student_details(db)
            elif choice == "4":
                create_new_class(db)
            elif choice == "5":
                show_full_statistics(db)
            elif choice == "6":
                check_database_integrity(db)
            elif choice == "0":
                print("\n👋 再見！/ Goodbye!")
                break
            else:
                print("❌ 無效的選擇 / Invalid choice")
        
        db.close()
        print("\n✅ 資料庫連接已關閉 / Database connection closed")
        
    except Exception as e:
        print(f"\n❌ 發生錯誤 / Error occurred: {e}")
        import traceback
        traceback.print_exc()


def show_all_classes(db):
    """顯示所有班級"""
    print("\n" + "=" * 60)
    print("🏫 所有班級列表 / All Classes")
    print("=" * 60)
    
    classes = db.get_all_classes()
    if not classes:
        print("目前沒有任何班級 / No classes found")
        return
    
    for class_id, class_name in classes:
        students = db.get_students_by_class_id(class_id)
        bound_count = sum(1 for s in students if s[3])  # s[3] 是 discord_id
        
        print(f"\n📚 {class_name}")
        print(f"  • 班級 ID / Class ID: {class_id}")
        print(f"  • 學生數 / Students: {len(students)}")
        print(f"  • 已綁定 Discord / Bound: {bound_count}")
        print(f"  • 未綁定 Discord / Not bound: {len(students) - bound_count}")


def show_class_students(db):
    """顯示班級學生列表"""
    class_name = input("\n請輸入班級名稱 / Enter class name (NCUFN/NCUEC/CYCUIUBM): ").strip()
    
    class_data = db.get_class_by_name(class_name)
    if not class_data:
        print(f"❌ 找不到班級 / Class not found: {class_name}")
        return
    
    class_id = class_data[0]
    students = db.get_students_by_class_id(class_id)
    
    print(f"\n📋 {class_name} 學生列表 / Student List")
    print("=" * 80)
    print(f"{'學號 / ID':<15} {'姓名 / Name':<20} {'Discord ID':<20} {'狀態 / Status'}")
    print("-" * 80)
    
    for student_id, student_name, student_number, discord_id in students:
        status = "✅ 已綁定 / Bound" if discord_id else "⏳ 未綁定 / Not bound"
        discord_display = discord_id if discord_id else "N/A"
        student_num_display = student_number if student_number else "N/A"
        print(f"{student_num_display:<15} {student_name:<20} {discord_display:<20} {status}")
    
    print("-" * 80)
    print(f"總計 / Total: {len(students)} 位學生 / students")


def show_student_details(db):
    """顯示學生詳細資料"""
    search_type = input("\n搜尋方式 / Search by (1=學號/Student ID, 2=Discord ID): ").strip()
    
    if search_type == "1":
        student_number = input("請輸入學號 / Enter student ID: ").strip()
        student_data = db.get_student_by_number(student_number)
    elif search_type == "2":
        discord_id = input("請輸入 Discord ID: ").strip()
        student_data = db.get_student_by_discord_id(discord_id)
    else:
        print("❌ 無效的選擇 / Invalid choice")
        return
    
    if not student_data:
        print("❌ 找不到學生 / Student not found")
        return
    
    print("\n" + "=" * 60)
    print("👤 學生詳細資料 / Student Details")
    print("=" * 60)
    print(f"學生 ID / Student ID: {student_data[0]}")
    print(f"姓名 / Name: {student_data[1]}")
    print(f"學號 / Student Number: {student_data[2] if student_data[2] else 'N/A'}")
    print(f"Discord ID: {student_data[3] if student_data[3] else 'N/A'}")
    print(f"班級 ID / Class ID: {student_data[4]}")
    print(f"班級名稱 / Class Name: {student_data[5]}")
    
    # 查詢作業提交記錄
    submissions = db.get_student_submissions(student_data[3] if student_data[3] else str(student_data[0]))
    print(f"\n📝 作業提交記錄 / Submission History: {len(submissions)} 筆 / records")


def create_new_class(db):
    """創建新班級"""
    class_name = input("\n請輸入新班級名稱 / Enter new class name: ").strip()
    
    if not class_name:
        print("❌ 班級名稱不能為空 / Class name cannot be empty")
        return
    
    class_id = db.create_class(class_name)
    if class_id:
        print(f"✅ 成功創建班級 / Class created successfully: {class_name} (ID: {class_id})")
    else:
        print(f"❌ 創建班級失敗（可能已存在）/ Failed to create class (may already exist)")


def show_full_statistics(db):
    """顯示完整統計"""
    print("\n" + "=" * 60)
    print("📊 完整資料庫統計 / Full Database Statistics")
    print("=" * 60)
    
    # 班級統計
    classes = db.get_all_classes()
    print(f"\n🏫 班級統計 / Class Statistics:")
    print(f"  • 總班級數 / Total classes: {len(classes)}")
    
    for class_id, class_name in classes:
        stats = db.get_class_statistics(class_id)
        print(f"\n  📚 {class_name}:")
        print(f"    - 學生數 / Students: {stats[0]}")
        print(f"    - 作業提交數 / Submissions: {stats[1]}")
    
    # 全域統計
    db.cur.execute("SELECT COUNT(*) FROM Students")
    total_students = db.cur.fetchone()[0]
    
    db.cur.execute("SELECT COUNT(*) FROM Students WHERE discord_id IS NOT NULL AND discord_id != ''")
    bound_students = db.cur.fetchone()[0]
    
    db.cur.execute("SELECT COUNT(*) FROM AssignmentFiles")
    total_submissions = db.cur.fetchone()[0]
    
    db.cur.execute("SELECT AVG(eng_total_score), AVG(stats_total_score) FROM AssignmentFiles")
    avg_scores = db.cur.fetchone()
    
    print(f"\n🌐 全域統計 / Global Statistics:")
    print(f"  • 總學生數 / Total students: {total_students}")
    print(f"  • 已綁定 Discord / Discord bound: {bound_students} ({bound_students/total_students*100:.1f}%)" if total_students > 0 else "  • 已綁定 Discord / Discord bound: 0 (0%)")
    print(f"  • 總作業提交 / Total submissions: {total_submissions}")
    print(f"  • 全域平均英文分數 / Global avg English: {avg_scores[0]:.2f if avg_scores[0] else 0:.2f}")
    print(f"  • 全域平均統計分數 / Global avg Statistics: {avg_scores[1]:.2f if avg_scores[1] else 0:.2f}")


def check_database_integrity(db):
    """檢查資料庫完整性"""
    print("\n" + "=" * 60)
    print("🔍 資料庫完整性檢查 / Database Integrity Check")
    print("=" * 60)
    
    issues = []
    
    # 檢查孤立的學生（沒有對應班級）
    db.cur.execute("""
        SELECT COUNT(*) FROM Students 
        WHERE class_id NOT IN (SELECT class_id FROM Classes)
    """)
    orphan_students = db.cur.fetchone()[0]
    if orphan_students > 0:
        issues.append(f"⚠️ 發現 {orphan_students} 個孤立學生記錄（班級不存在）")
    
    # 檢查重複的 Discord ID
    db.cur.execute("""
        SELECT discord_id, COUNT(*) as count 
        FROM Students 
        WHERE discord_id IS NOT NULL AND discord_id != ''
        GROUP BY discord_id 
        HAVING count > 1
    """)
    duplicate_discords = db.cur.fetchall()
    if duplicate_discords:
        issues.append(f"⚠️ 發現 {len(duplicate_discords)} 個重複的 Discord ID")
        for discord_id, count in duplicate_discords:
            print(f"  • Discord ID {discord_id}: {count} 個學生")
    
    # 檢查沒有密碼的學生
    db.cur.execute("SELECT COUNT(*) FROM Students WHERE password IS NULL OR password = ''")
    no_password = db.cur.fetchone()[0]
    if no_password > 0:
        issues.append(f"ℹ️ {no_password} 個學生沒有設定密碼")
    
    if not issues:
        print("✅ 資料庫完整性檢查通過 / Database integrity check passed")
    else:
        print("發現以下問題 / Found following issues:\n")
        for issue in issues:
            print(issue)


if __name__ == "__main__":
    main()
