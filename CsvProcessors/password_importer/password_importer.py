import os
import pandas as pd
from pathlib import Path


class PasswordImporter:
    """密碼導入工具 - 從 txt 檔案讀取密碼並更新到 Excel 課程清單"""

    def __init__(self, base_dir=None):
        """
        初始化密碼導入工具

        Args:
            base_dir: 基礎目錄，預設為當前檔案所在目錄的上兩層
        """
        if base_dir is None:
            # 預設為 Bot 目錄
            base_dir = Path(__file__).parent.parent.parent

        self.base_dir = Path(base_dir)
        # Excel 檔案路徑：Bot/Course List/course list.xlsx
        self.excel_path = self.base_dir / "Course List" / "course list.xlsx"
        # 密碼 txt 檔案所在目錄：Bot/CsvProcessors/password_importer/
        self.password_dir = Path(__file__).parent

        # 班級配置：工作表名稱對應 txt 檔案所在資料夾
        self.classes = {
            "NCUFN": "NCUFN",
            "NCUEC": "NCUEC",
            "CYCUIUBM": "CYCUIUBM",
        }

    def parse_txt_files_in_folder(self, folder_path):
        """
        遞迴解析資料夾中的所有 txt 檔案（包括子資料夾）
        檔名格式：學號_姓名.txt
        檔案內容：密碼

        Args:
            folder_path: 資料夾路徑

        Returns:
            dict: {學號: (姓名, 密碼)} 的字典
        """
        student_data = {}

        try:
            if not folder_path.exists():
                print(f"❌ 找不到資料夾: {folder_path}")
                return {}

            # 遞迴列出所有 .txt 檔案（包括子資料夾）
            txt_files = list(folder_path.rglob("*.txt"))

            if not txt_files:
                print(f"⚠️ 資料夾中沒有找到任何 .txt 檔案（包括子資料夾）: {folder_path}")
                return {}

            print(f"📁 找到 {len(txt_files)} 個 txt 檔案（包括子資料夾）")

            for txt_file in txt_files:
                try:
                    # 顯示相對路徑
                    relative_path = txt_file.relative_to(folder_path)

                    # 解析檔名：學號_姓名.txt
                    filename = txt_file.stem  # 去掉 .txt 副檔名

                    if "_" not in filename:
                        print(f"  ⚠️ 檔名格式錯誤（缺少底線）: {relative_path}")
                        continue

                    parts = filename.split("_", 1)  # 只分割第一個底線
                    if len(parts) != 2:
                        print(f"  ⚠️ 檔名格式錯誤: {relative_path}")
                        continue

                    student_id = parts[0].strip()
                    student_name = parts[1].strip()

                    # 讀取檔案內容（密碼）
                    with open(txt_file, "r", encoding="utf-8") as f:
                        password = f.read().strip()

                    if not password:
                        print(f"  ⚠️ 檔案內容為空: {relative_path}")
                        continue

                    # 檢查是否有重複的學號
                    if student_id in student_data:
                        print(f"  ⚠️ 重複的學號 {student_id}:")
                        print(f"     已存在: {student_data[student_id]}")
                        print(f"     新檔案: {relative_path} - {student_name} - {password}")
                        print(f"     將使用新檔案的資料")

                    student_data[student_id] = (student_name, password)
                    print(f"  ✓ {relative_path}: {student_id} - {student_name} - {password}")

                except Exception as e:
                    print(f"  ❌ 處理檔案時發生錯誤 {txt_file.name}: {e}")
                    continue

            print(f"✅ 成功讀取 {len(student_data)} 筆學生資料")
            return student_data

        except Exception as e:
            print(f"❌ 讀取資料夾時發生錯誤: {e}")
            import traceback

            traceback.print_exc()
            return {}

    def update_excel_passwords(self, sheet_name, student_data):
        """
        更新 Excel 工作表的密碼欄位

        Args:
            sheet_name: 工作表名稱 (NCUFN, NCUEC, CYCUIUBM)
            student_data: {學號: (姓名, 密碼)} 的字典

        Returns:
            bool: 是否成功更新
        """
        try:
            # 檢查 Excel 檔案是否存在
            if not self.excel_path.exists():
                print(f"❌ 找不到 Excel 檔案: {self.excel_path}")
                return False

            # 讀取指定工作表
            df = pd.read_excel(self.excel_path, sheet_name=sheet_name)
            print(f"\n📊 工作表資訊:")
            print(f"  • 工作表名稱: {sheet_name}")
            print(f"  • 總行數: {len(df)}")
            print(f"  • 欄位: {list(df.columns)}")

            # 檢查必要欄位是否存在（英文欄位名稱）
            required_columns = ["StudentID", "Name", "Password"]
            missing_columns = [col for col in required_columns if col not in df.columns]

            if missing_columns:
                print(f"❌ 工作表缺少必要欄位: {missing_columns}")
                print(f"   實際欄位: {list(df.columns)}")
                return False

            # 統計資訊
            updated_count = 0
            not_found_count = 0
            already_has_password = 0
            name_mismatch_count = 0

            # 更新密碼
            for student_id, (txt_name, password) in student_data.items():
                # 在 DataFrame 中查找對應的學號
                mask = df["StudentID"].astype(str) == str(student_id)
                matching_rows = df[mask]

                if len(matching_rows) > 0:
                    # 取得 Excel 中的姓名
                    excel_name = df.loc[mask, "Name"].iloc[0]

                    # 檢查姓名是否一致（警告但仍繼續更新）
                    if str(excel_name).strip() != txt_name:
                        print(f"  ⚠️ 學號 {student_id} 姓名不一致:")
                        print(f"     txt 檔名: {txt_name}")
                        print(f"     Excel: {excel_name}")
                        name_mismatch_count += 1

                    # 檢查是否已有密碼
                    current_password = df.loc[mask, "Password"].iloc[0]
                    if pd.notna(current_password) and str(current_password).strip() != "":
                        print(f"  ⚠️ 學號 {student_id} 已有密碼，將覆寫: {current_password} → {password}")
                        already_has_password += 1

                    # 更新密碼
                    df.loc[mask, "Password"] = password
                    updated_count += 1

                    print(f"  ✓ 已更新: {student_id} ({excel_name}) - {password}")
                else:
                    print(f"  ⚠️ 工作表中找不到學號: {student_id} ({txt_name})")
                    not_found_count += 1

            # 使用 ExcelWriter 更新指定工作表
            with pd.ExcelWriter(self.excel_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)

            print(f"\n📈 更新統計:")
            print(f"  • 成功更新: {updated_count} 筆")
            print(f"  • 覆寫已有密碼: {already_has_password} 筆")
            print(f"  • 姓名不一致: {name_mismatch_count} 筆")
            print(f"  • 找不到對應學號: {not_found_count} 筆")
            print(f"✅ 工作表已儲存: {sheet_name}")

            return True

        except ValueError as e:
            if "Worksheet" in str(e):
                print(f"❌ 找不到工作表: {sheet_name}")
                print(f"   請確認 Excel 檔案中有此工作表")
                # 列出所有可用的工作表
                try:
                    xls = pd.ExcelFile(self.excel_path)
                    print(f"   可用的工作表: {xls.sheet_names}")
                except:
                    pass
            else:
                print(f"❌ 讀取工作表時發生錯誤: {e}")
            return False
        except Exception as e:
            print(f"❌ 更新 Excel 時發生錯誤: {e}")
            import traceback

            traceback.print_exc()
            return False

    def process_class(self, class_name):
        """
        處理單一班級的密碼導入

        Args:
            class_name: 班級名稱 (CYCUIUBM, NCUFN, NCUEC)

        Returns:
            bool: 是否成功處理
        """
        if class_name not in self.classes:
            print(f"❌ 未知的班級名稱: {class_name}")
            print(f"   可用的班級: {list(self.classes.keys())}")
            return False

        folder_name = self.classes[class_name]

        print(f"\n{'='*60}")
        print(f"🏫 處理班級: {class_name}")
        print(f"{'='*60}")

        # 1. 讀取資料夾中的所有 txt 檔案（遞迴搜尋）
        folder_path = self.password_dir / folder_name
        print(f"\n📄 讀取密碼檔案資料夾（遞迴搜尋）: {folder_path}")

        # 檢查資料夾是否存在
        if not folder_path.exists():
            print(f"❌ 資料夾不存在: {folder_path}")
            return False

        student_data = self.parse_txt_files_in_folder(folder_path)

        if not student_data:
            print(f"❌ 沒有讀取到任何學生資料")
            return False

        # 2. 更新 Excel 工作表
        print(f"\n📝 更新 Excel 工作表: {class_name}")
        print(f"   Excel 檔案路徑: {self.excel_path}")

        return self.update_excel_passwords(class_name, student_data)

    def process_all_classes(self):
        """處理所有班級的密碼導入"""
        print("\n" + "=" * 60)
        print("🚀 開始批次處理所有班級的密碼導入")
        print(f"📁 Excel 檔案: {self.excel_path}")
        print("=" * 60)

        # 檢查 Excel 檔案是否存在
        if not self.excel_path.exists():
            print(f"❌ 找不到 Excel 檔案: {self.excel_path}")
            print(f"   請確認檔案路徑是否正確")
            return

        results = {}

        for class_name in self.classes.keys():
            results[class_name] = self.process_class(class_name)

        # 顯示總結
        print("\n" + "=" * 60)
        print("📊 處理結果總結")
        print("=" * 60)

        for class_name, success in results.items():
            status = "✅ 成功" if success else "❌ 失敗"
            print(f"  {class_name}: {status}")

        success_count = sum(1 for s in results.values() if s)
        print(f"\n總計: {success_count}/{len(results)} 個班級處理成功")


def main():
    """主程式"""
    import sys

    importer = PasswordImporter()

    # 顯示路徑資訊
    print("📂 路徑資訊:")
    print(f"  • Bot 目錄: {importer.base_dir}")
    print(f"  • Excel 檔案: {importer.excel_path}")
    print(f"  • 密碼檔案目錄: {importer.password_dir}")
    print()

    # 檢查命令列參數
    if len(sys.argv) > 1:
        # 處理指定班級
        class_name = sys.argv[1].upper()
        importer.process_class(class_name)
    else:
        # 處理所有班級
        importer.process_all_classes()


if __name__ == "__main__":
    main()
