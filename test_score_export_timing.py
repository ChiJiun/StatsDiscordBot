import asyncio
import io
import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock

import pandas as pd

from database import DatabaseManager
from discord_bot import HomeworkBot


class ScoreExportTimingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp.name)
        self.db = DatabaseManager()
        self.class_id = self.db.create_class("TEST")
        self.db.create_student("Test Student", "12345", self.class_id, student_number="S001")

    def tearDown(self):
        self.db.close()
        os.chdir(self.original_cwd)
        self.temp.cleanup()

    def test_persist_and_export(self):
        self.assertTrue(self.db.insert_submission(
            "12345", "Test Student", "S001", "Example", 1, "sample.html",
            parsed_scores={"統計分數": 90}, score_keys=["統計分數"],
            upload_time="2026-11-19T10:00:00+08:00", grading_duration_sec=12.34,
        ))
        rows = self.db.get_all_scores_for_class("TEST", "Example")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][5], "2026-11-19T10:00:00+08:00")
        self.assertEqual(rows[0][6], 12.34)

        bot = HomeworkBot.__new__(HomeworkBot)
        bot.db = self.db
        message = MagicMock()
        message.content = "!score TEST Example"
        message.author.send = AsyncMock()
        asyncio.run(bot.export_class_scores(message))
        message.author.send.assert_awaited_once()
        file = message.author.send.await_args.kwargs["file"]
        df = pd.read_excel(io.BytesIO(file.fp.getvalue()))
        self.assertEqual(df.loc[0, "上傳檔案時刻"], "2026-11-19T10:00:00+08:00")
        self.assertAlmostEqual(df.loc[0, "系統評分時長（sec）"], 12.34)
        self.assertEqual(df.loc[0, "統計分數"], 90)

    def test_missing_submission_keeps_blank_columns(self):
        bot = HomeworkBot.__new__(HomeworkBot)
        bot.db = self.db
        message = MagicMock()
        message.content = "!score TEST Example"
        message.author.send = AsyncMock()
        asyncio.run(bot.export_class_scores(message))
        file = message.author.send.await_args.kwargs["file"]
        df = pd.read_excel(io.BytesIO(file.fp.getvalue()))
        self.assertIn("上傳檔案時刻", df.columns)
        self.assertIn("系統評分時長（sec）", df.columns)
        self.assertTrue(pd.isna(df.loc[0, "系統評分時長（sec）"]))

    def test_migration_is_idempotent(self):
        self.db._create_tables()
        self.db._create_tables()
        columns = [row[1] for row in self.db.cur.execute("PRAGMA table_info(AssignmentFiles)")]
        self.assertIn("grading_duration_sec", columns)


if __name__ == "__main__":
    unittest.main()
