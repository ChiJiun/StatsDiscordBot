import sqlite3
from config import DB_PATH


class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.cur = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        """建立必要的資料表"""
        self.cur.execute(
            """
        CREATE TABLE IF NOT EXISTS homework_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            student_name TEXT,
            student_id TEXT,
            question_number INTEGER,
            attempt_number INTEGER,
            html_path TEXT,
            score INTEGER,
            feedback TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        )
        self.conn.commit()

    def get_max_attempt(self, user_id, question_number):
        """獲取使用者對特定題目的最大嘗試次數"""
        self.cur.execute(
            """
            SELECT MAX(attempt_number) FROM homework_submissions
            WHERE user_id = ? AND question_number = ?
            """,
            (user_id, question_number),
        )
        result = self.cur.fetchone()[0]
        return result if result is not None else 0

    def insert_submission(self, user_id, student_name, student_id, question_number, attempt_number, html_path, score, feedback):
        """插入新的作業提交記錄"""
        self.cur.execute(
            """
            INSERT INTO homework_submissions (
                user_id, student_name, student_id, question_number,
                attempt_number, html_path, score, feedback
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, student_name, student_id, question_number, attempt_number, html_path, score, feedback),
        )
        self.conn.commit()

    def close(self):
        """關閉資料庫連線"""
        self.conn.close()
