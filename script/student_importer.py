import pandas as pd
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from database import DatabaseManager


class StudentImporter:
    def __init__(self):
        self.db = DatabaseManager()

    def import_from_excel(self, excel_file_path, class_name=None, sheet_name=None):
        """
        從 Excel 檔案導入學生資料到資料庫

        Args:
            excel_file_path (str): Excel 檔案路徑
            class_name (str, optional): 班級名稱，如果為 None 則從工作表名稱或檔案名稱推測
            sheet_name (str, optional): 工作表名稱，如果為 None 則使用第一個工作表

        Returns:
            dict: 導入結果統計
        """
        if not os.path.exists(excel_file_path):
            return {"success": False, "error": f"找不到檔案: {excel_file_path}"}

        try:
            # 讀取 Excel 檔案，並取得工作表名稱
            if sheet_name:
                df = pd.read_excel(excel_file_path, sheet_name=sheet_name)
                actual_sheet_name = sheet_name
            else:
                # 獲取第一個工作表的名稱
                excel_file = pd.ExcelFile(excel_file_path)
                actual_sheet_name = excel_file.sheet_names[0]
                df = pd.read_excel(excel_file_path, sheet_name=actual_sheet_name)

            # 決定班級名稱的優先順序：命令列參數 > 工作表名稱 > 檔案名稱
            if not class_name:
                # 優先使用工作表名稱
                if actual_sheet_name and actual_sheet_name not in ["Sheet1", "Sheet 1", " 工作表1"]:
                    class_name = actual_sheet_name
                else:
                    # 如果工作表是預設名稱，則使用檔案名稱
                    filename = os.path.basename(excel_file_path)
                    class_name = filename.replace(".xlsx", "").replace(".xls", "")

            print(f"🏫 目標班級: {class_name}")
            print(f"📄 工作表名稱: {actual_sheet_name}")

            # 檢查班級是否存在，如果不存在則創建或選擇現有班級
            class_data = self.db.get_class_by_name(class_name)
            if not class_data:
                # 檢查是否為已知的班級代碼
                known_classes = ["NCUFN", "NCUEC", "CYCUIUBM", "CYCUBA", "HWIS"]
                if class_name.upper() in known_classes:
                    # 創建已知班級
                    class_id = self.db.create_class(class_name.upper())
                    if class_id:
                        print(f"✅ 已創建新班級: {class_name.upper()}")
                        class_name = class_name.upper()
                    else:
                        return {"success": False, "error": f"無法創建班級: {class_name}"}
                else:
                    # 列出現有班級，讓用戶選擇
                    existing_classes = self.db.get_all_classes()
                    if existing_classes:
                        print(f"❌ 班級 '{class_name}' 不存在")
                        print("📋 現有班級列表:")
                        for cls_id, cls_name in existing_classes:
                            print(f"  - {cls_name} (ID: {cls_id})")

                        # 提供選擇現有班級的選項
                        print(f"\n⚠️ 請選擇操作:")
                        print(f"1. 創建新班級 '{class_name}'")
                        print(f"2. 手動指定現有班級")

                        choice = input("請輸入選項 (1/2): ").strip()

                        if choice == "1":
                            class_id = self.db.create_class(class_name)
                            if not class_id:
                                return {"success": False, "error": f"無法創建班級: {class_name}"}
                        elif choice == "2":
                            selected_class = input("請輸入要使用的班級名稱: ").strip()
                            class_data = self.db.get_class_by_name(selected_class)
                            if class_data:
                                class_id = class_data[0]
                                class_name = selected_class
                            else:
                                return {"success": False, "error": f"指定的班級不存在: {selected_class}"}
                        else:
                            return {"success": False, "error": "取消導入"}
                    else:
                        # 如果沒有任何班級，直接創建
                        class_id = self.db.create_class(class_name)
                        if not class_id:
                            return {"success": False, "error": f"無法創建班級: {class_name}"}
            else:
                class_id = class_data[0]
                print(f"✅ 使用現有班級: {class_name} (ID: {class_id})")

            # 分析欄位名稱
            columns = df.columns.tolist()
            name_column = self._find_name_column(columns)
            number_column = self._find_number_column(columns)
            discord_column = self._find_discord_column(columns)
            password_column = self._find_password_column(columns)

            print(f"🔍 檢測到的欄位:")
            print(f"  姓名欄位: {name_column}")
            print(f"  學號欄位: {number_column}")
            print(f"  Discord ID欄位: {discord_column}")
            print(f"  密碼欄位: {password_column}")

            if not name_column:
                return {"success": False, "error": "找不到姓名欄位，請確認Excel檔案包含姓名相關欄位"}

            # 導入學生資料
            imported_count = 0
            skipped_count = 0
            error_count = 0
            errors = []

            for index, row in df.iterrows():
                try:
                    student_name = str(row[name_column]).strip() if pd.notna(row[name_column]) else None
                    student_number = str(row[number_column]).strip() if number_column and pd.notna(row[number_column]) else None
                    discord_id = str(row[discord_column]).strip() if discord_column and pd.notna(row[discord_column]) else None
                    password = str(row[password_column]).strip() if password_column and pd.notna(row[password_column]) else None

                    # 跳過空白姓名
                    if not student_name or student_name == "nan":
                        skipped_count += 1
                        continue

                    # 清理空值
                    if student_number and student_number == "nan":
                        student_number = None
                    if discord_id and discord_id == "nan":
                        discord_id = None
                    if password and password == "nan":
                        password = None

                    # 檢查必要欄位
                    if not student_name:
                        error_count += 1
                        errors.append(f"第{index+2}行: 學生姓名為空")
                        continue

                    # 移除重複檢查，允許所有學生直接導入
                    # 這樣可以支援跨班級重複，甚至同班級內重複

                    # 創建或更新學生記錄 - 確保參數順序正確
                    db_student_id = self.db.get_or_create_student(
                        student_name=student_name,
                        student_number=student_number,
                        class_id=class_id,
                        password=password,
                        discord_id=discord_id,  # 在導入時通常為None
                    )

                    if db_student_id:
                        imported_count += 1
                        info_parts = [f"姓名: {student_name}"]
                        if student_number:
                            info_parts.append(f"學號: {student_number}")
                        if password:
                            info_parts.append(f"密碼: {password}")
                        if discord_id:
                            info_parts.append(f"Discord ID: {discord_id}")

                        print(f"✅ 已導入: {', '.join(info_parts)} -> {class_name} (DB ID: {db_student_id})")
                    else:
                        skipped_count += 1
                        print(f"⚠️ 跳過學生: {student_name} (處理失敗)")

                except Exception as e:
                    error_count += 1
                    error_msg = f"第{index+2}行錯誤: {e}"
                    errors.append(error_msg)
                    print(f"❌ {error_msg}")

            return {
                "success": True,
                "class_name": class_name,
                "class_id": class_id,
                "imported_count": imported_count,
                "skipped_count": skipped_count,
                "error_count": error_count,
                "errors": errors,
                "total_rows": len(df),
                "sheet_name": actual_sheet_name,
            }

        except Exception as e:
            return {"success": False, "error": f"處理Excel檔案時發生錯誤: {e}"}

    def _find_name_column(self, columns):
        """尋找姓名欄位"""
        name_keywords = ["姓名", "name", "學生姓名", "學生名稱", "student_name", "student name", "名字"]
        for col in columns:
            if any(keyword in str(col).lower() for keyword in name_keywords):
                return col
        return None

    def _find_number_column(self, columns):
        """尋找學號欄位"""
        number_keywords = ["學號", "id", "student_id", "student id", "學生編號", "編號", "student_number", "number", "no"]
        for col in columns:
            if any(keyword in str(col).lower() for keyword in number_keywords):
                return col
        return None

    def _find_discord_column(self, columns):
        """尋找Discord ID欄位"""
        discord_keywords = ["discord", "discord_id", "discord id", "discordid", "dc_id"]
        for col in columns:
            if any(keyword in str(col).lower() for keyword in discord_keywords):
                return col
        return None

    def _find_password_column(self, columns):
        """尋找密碼欄位"""
        password_keywords = ["密碼", "password", "pwd", "學生密碼", "登入密碼", "pass"]
        for col in columns:
            if any(keyword in str(col).lower() for keyword in password_keywords):
                return col
        return None

    def import_all_excel_files(self, directory_path="Course List"):
        """
        導入指定目錄下的所有Excel檔案，支援多工作表

        Args:
            directory_path (str): 包含Excel檔案的目錄路徑

        Returns:
            list: 每個檔案的導入結果
        """
        if not os.path.exists(directory_path):
            return [{"success": False, "error": f"找不到目錄: {directory_path}"}]

        results = []
        excel_files = []

        # 查找所有Excel檔案，但排除暫存檔案
        for filename in os.listdir(directory_path):
            if filename.lower().endswith((".xlsx", ".xls")) and not filename.startswith("~$") and not filename.startswith(".~"):
                excel_files.append(filename)

        if not excel_files:
            return [{"success": False, "error": f"在 {directory_path} 目錄中找不到Excel檔案"}]

        print(f"🔍 發現 {len(excel_files)} 個Excel檔案:")
        for filename in excel_files:
            print(f"  - {filename}")

        # 逐一處理每個檔案
        for filename in excel_files:
            file_path = os.path.join(directory_path, filename)
            print(f"\n📁 正在處理: {filename}")

            try:
                # 讀取Excel檔案並獲取所有工作表
                excel_file = pd.ExcelFile(file_path)
                sheet_names = excel_file.sheet_names

                print(f"📄 發現 {len(sheet_names)} 個工作表: {', '.join(sheet_names)}")

                # 已知的班級代碼
                known_classes = ["NCUFN", "NCUEC", "CYCUIUBM", "CYCUBA", "HWIS"]

                # 處理每個工作表
                file_results = []
                for sheet_name in sheet_names:
                    print(f"\n📋 正在處理工作表: {sheet_name}")

                    # 檢查是否為已知班級
                    if sheet_name.upper() in known_classes:
                        result = self.import_from_excel(file_path, class_name=sheet_name.upper(), sheet_name=sheet_name)
                    else:
                        # 如果不是已知班級，使用工作表名稱作為班級名稱
                        result = self.import_from_excel(file_path, sheet_name=sheet_name)

                    result["filename"] = filename
                    result["sheet_name"] = sheet_name
                    file_results.append(result)

                    if result["success"]:
                        print(f"✅ 工作表 '{sheet_name}' 導入完成: {result['imported_count']} 個學生")
                    else:
                        print(f"❌ 工作表 '{sheet_name}' 導入失敗: {result['error']}")

                results.extend(file_results)

            except Exception as e:
                error_result = {"success": False, "error": f"讀取檔案時發生錯誤: {e}", "filename": filename}
                results.append(error_result)
                print(f"❌ {filename} 處理失敗: {e}")

        return results

    def import_specific_sheets(self, excel_file_path, target_sheets=None):
        """
        從單一Excel檔案導入指定的工作表

        Args:
            excel_file_path (str): Excel檔案路徑
            target_sheets (list, optional): 要導入的工作表名稱列表，如果為None則導入所有工作表

        Returns:
            list: 每個工作表的導入結果
        """
        if not os.path.exists(excel_file_path):
            return [{"success": False, "error": f"找不到檔案: {excel_file_path}"}]

        try:
            excel_file = pd.ExcelFile(excel_file_path)
            all_sheets = excel_file.sheet_names

            # 如果沒有指定工作表，則處理所有工作表
            if target_sheets is None:
                target_sheets = all_sheets
            else:
                # 檢查指定的工作表是否存在
                missing_sheets = [sheet for sheet in target_sheets if sheet not in all_sheets]
                if missing_sheets:
                    return [{"success": False, "error": f"找不到工作表: {', '.join(missing_sheets)}"}]

            print(f"📁 正在處理檔案: {os.path.basename(excel_file_path)}")
            print(f"📄 目標工作表: {', '.join(target_sheets)}")

            results = []
            for sheet_name in target_sheets:
                print(f"\n📋 正在處理工作表: {sheet_name}")

                # 已知的班級代碼
                known_classes = ["NCUFN", "NCUEC", "CYCUIUBM", "CYCUBA", "HWIS"]

                if sheet_name.upper() in known_classes:
                    result = self.import_from_excel(excel_file_path, class_name=sheet_name.upper(), sheet_name=sheet_name)
                else:
                    result = self.import_from_excel(excel_file_path, sheet_name=sheet_name)

                result["filename"] = os.path.basename(excel_file_path)
                result["sheet_name"] = sheet_name
                results.append(result)

                if result["success"]:
                    print(f"✅ 工作表 '{sheet_name}' 導入完成: {result['imported_count']} 個學生")
                else:
                    print(f"❌ 工作表 '{sheet_name}' 導入失敗: {result['error']}")

            return results

        except Exception as e:
            return [{"success": False, "error": f"處理Excel檔案時發生錯誤: {e}"}]

    def export_student_summary(self, output_file="student_summary.xlsx"):
        """導出學生資料摘要到Excel檔案"""
        try:
            # 獲取所有班級和學生資料
            all_classes = self.db.get_all_classes()

            summary_data = []
            for class_id, class_name in all_classes:
                try:
                    # 嘗試使用不同的方法獲取學生資料
                    if hasattr(self.db, "get_students_by_class_id"):
                        students = self.db.get_students_by_class_id(class_id)
                    elif hasattr(self.db, "get_students_by_class"):
                        students = self.db.get_students_by_class(class_id)
                    else:
                        print(f"⚠️ 無法獲取班級 {class_name} 的學生資料：缺少相應的資料庫方法")
                        continue

                    for student_data in students:
                        if len(student_data) >= 4:
                            student_id, student_name, student_number, discord_id = student_data[:4]
                            summary_data.append(
                                {
                                    "班級": class_name,
                                    "學生ID": student_id,
                                    "姓名": student_name,
                                    "學號": student_number or "未設定",
                                    "Discord ID": discord_id or "未綁定",
                                    "狀態": "已綁定" if discord_id else "未綁定",
                                }
                            )
                except Exception as e:
                    print(f"⚠️ 處理班級 {class_name} 時發生錯誤: {e}")
                    continue

            # 創建DataFrame並導出
            if summary_data:
                df = pd.DataFrame(summary_data)
                df.to_excel(output_file, index=False, engine="openpyxl")

                print(f"✅ 學生資料摘要已導出到: {output_file}")
                print(f"📊 總計: {len(summary_data)} 個學生記錄")
                return True
            else:
                print("⚠️ 沒有學生資料可以導出")
                return False

        except Exception as e:
            print(f"❌ 導出學生摘要時發生錯誤: {e}")
            return False

    def close(self):
        """關閉資料庫連線"""
        self.db.close()


def main():
    """命令列介面"""
    importer = StudentImporter()

    try:
        if len(sys.argv) > 1:
            command = sys.argv[1].lower()

            if command == "export":
                # 導出學生資料摘要
                output_file = sys.argv[2] if len(sys.argv) > 2 else "student_summary.xlsx"
                importer.export_student_summary(output_file)
                return

            elif command == "sheets":
                # 導入指定檔案的特定工作表
                if len(sys.argv) < 3:
                    print("❌ 使用方法: python student_importer.py sheets <檔案路徑> [工作表1] [工作表2] ...")
                    return

                file_path = sys.argv[2]
                target_sheets = sys.argv[3:] if len(sys.argv) > 3 else None

                print(f"📂 正在導入檔案: {file_path}")
                if target_sheets:
                    print(f"📄 指定工作表: {', '.join(target_sheets)}")
                else:
                    print("📄 將導入所有工作表")

                results = importer.import_specific_sheets(file_path, target_sheets)

                # 顯示結果摘要
                total_imported = 0
                total_skipped = 0
                total_errors = 0

                print("\n📊 導入結果摘要:")
                print("=" * 50)

                for result in results:
                    if result["success"]:
                        print(f"✅ 工作表: {result.get('sheet_name', '未知')}")
                        print(f"   班級: {result['class_name']}")
                        print(f"   已導入: {result['imported_count']} 個學生")
                        print(f"   已跳過: {result['skipped_count']} 個學生")
                        if result["error_count"] > 0:
                            print(f"   錯誤: {result['error_count']} 個")

                        total_imported += result["imported_count"]
                        total_skipped += result["skipped_count"]
                        total_errors += result["error_count"]
                    else:
                        print(f"❌ 工作表: {result.get('sheet_name', '未知')}")
                        print(f"   錯誤: {result['error']}")
                    print()

                print("=" * 50)
                print(f"🎯 總計:")
                print(f"   成功導入: {total_imported} 個學生")
                print(f"   跳過重複: {total_skipped} 個學生")
                if total_errors > 0:
                    print(f"   錯誤數量: {total_errors} 個")

                return

            elif command.endswith((".xlsx", ".xls")):
                # 如果提供了檔案路徑，導入指定檔案的所有工作表
                file_path = command
                class_name = sys.argv[2] if len(sys.argv) > 2 else None

                print(f"📂 正在導入檔案: {file_path}")
                if class_name:
                    print(f"🏫 目標班級: {class_name}")

                # 使用新的多工作表導入功能
                results = importer.import_specific_sheets(file_path)

                # 顯示結果摘要
                total_imported = 0
                total_skipped = 0
                total_errors = 0

                print("\n📊 導入結果摘要:")
                print("=" * 50)

                for result in results:
                    if result["success"]:
                        print(f"✅ 工作表: {result.get('sheet_name', '未知')}")
                        print(f"   班級: {result['class_name']}")
                        print(f"   已導入: {result['imported_count']} 個學生")
                        print(f"   已跳過: {result['skipped_count']} 個學生")
                        if result["error_count"] > 0:
                            print(f"   錯誤: {result['error_count']} 個")

                        total_imported += result["imported_count"]
                        total_skipped += result["skipped_count"]
                        total_errors += result["error_count"]
                    else:
                        print(f"❌ 工作表: {result.get('sheet_name', '未知')}")
                        print(f"   錯誤: {result['error']}")
                    print()

                print("=" * 50)
                print(f"🎯 總計:")
                print(f"   成功導入: {total_imported} 個學生")
                print(f"   跳過重複: {total_skipped} 個學生")
                if total_errors > 0:
                    print(f"   錯誤數量: {total_errors} 個")

                return

        # 預設行為：導入Course List目錄下的所有檔案和所有工作表
        print("📁 正在導入Course List目錄下的所有Excel檔案和工作表...")
        results = importer.import_all_excel_files()

        total_imported = 0
        total_skipped = 0
        total_errors = 0

        print("\n📊 導入結果摘要:")
        print("=" * 50)

        current_file = ""
        for result in results:
            # 如果是新檔案，顯示檔案名稱
            if result.get("filename", "") != current_file:
                current_file = result.get("filename", "")
                print(f"\n📁 檔案: {current_file}")

            if result["success"]:
                print(f"  ✅ 工作表: {result.get('sheet_name', '未知')}")
                print(f"     班級: {result['class_name']}")
                print(f"     已導入: {result['imported_count']} 個學生")
                print(f"     已跳過: {result['skipped_count']} 個學生")
                if result["error_count"] > 0:
                    print(f"     錯誤: {result['error_count']} 個")

                total_imported += result["imported_count"]
                total_skipped += result["skipped_count"]
                total_errors += result["error_count"]
            else:
                print(f"  ❌ 工作表: {result.get('sheet_name', '未知')}")
                print(f"     錯誤: {result['error']}")

        print("\n" + "=" * 50)
        print(f"🎯 總計:")
        print(f"   成功導入: {total_imported} 個學生")
        print(f"   跳過重複: {total_skipped} 個學生")
        if total_errors > 0:
            print(f"   錯誤數量: {total_errors} 個")

        # 提供使用提示
        print(f"\n💡 使用提示:")
        print(f"   • python student_importer.py export - 導出學生資料摘要")
        print(f"   • python student_importer.py sheets <檔案> [工作表...] - 導入指定工作表")
        print(f"   • python student_importer.py <檔案> - 導入檔案的所有工作表")

    except KeyboardInterrupt:
        print("\n⚠️ 用戶中斷導入程序")
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
    finally:
        importer.close()


if __name__ == "__main__":
    main()
