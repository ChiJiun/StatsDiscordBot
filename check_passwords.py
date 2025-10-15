from database import DatabaseManager


def main():
    """檢查密碼導入狀況"""
    db = DatabaseManager()

    try:
        print("🔐 檢查密碼導入狀況")
        print("=" * 50)

        # 檢查每個班級的密碼設定
        all_classes = db.get_all_classes()

        for class_id, class_name in all_classes:
            print(f"\n🏫 班級：{class_name}")

            # 獲取該班級的學生
            db.cur.execute(
                """
                SELECT student_id, student_name, student_number, discord_id, password
                FROM Students 
                WHERE class_id = ?
                ORDER BY student_name
                LIMIT 5
            """,
                (class_id,),
            )

            students = db.cur.fetchall()

            for student_id, student_name, student_number, discord_id, password in students:
                password_status = "✅有密碼" if password else "❌無密碼"
                dc_status = "已綁定DC" if discord_id else "未綁定DC"
                number_info = f"({student_number})" if student_number else "(無學號)"

                print(f"  {student_name} {number_info} - {password_status} - {dc_status}")
                if password:
                    print(f"    密碼: {password}")

            # 統計該班級的密碼狀況
            db.cur.execute(
                """
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN password IS NOT NULL THEN 1 END) as with_password,
                    COUNT(CASE WHEN discord_id IS NOT NULL THEN 1 END) as with_discord
                FROM Students 
                WHERE class_id = ?
            """,
                (class_id,),
            )

            total, with_password, with_discord = db.cur.fetchone()
            print(f"  📊 統計：總共{total}人，{with_password}人有密碼，{with_discord}人已綁定Discord")

    except Exception as e:
        print(f"❌ 檢查過程中發生錯誤: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
