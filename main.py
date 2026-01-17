# main.py
import sys
import os
import json
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from src.main_window import MainWindow
from src import database as db

PREFERENCE_FILE = "preference.json"


def load_db_path_from_preference():
    if os.path.exists(PREFERENCE_FILE):
        with open(PREFERENCE_FILE, "r") as f:
            try:
                prefs = json.load(f)
                return prefs.get("db_path")
            except json.JSONDecodeError:
                return None
    return None


def save_db_path_to_preference(path):
    prefs = {}
    if os.path.exists(PREFERENCE_FILE):
        with open(PREFERENCE_FILE, "r", encoding="utf-8") as f:
            try:
                prefs = json.load(f)
            except json.JSONDecodeError:
                pass  # ファイルが空または壊れている場合は、新しい設定で上書き
    prefs["db_path"] = path.replace("\\", "/")  # パスを正規化
    with open(PREFERENCE_FILE, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    db_path = load_db_path_from_preference()

    if not db_path or not os.path.exists(db_path):
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setText("データベースファイルが見つかりません。")
        msg_box.setInformativeText(
            "既存のデータベースファイルを選択するか、新しいファイルを作成してください。"
        )
        select_button = msg_box.addButton(
            "既存のファイルを選択", QMessageBox.ButtonRole.ActionRole
        )
        create_button = msg_box.addButton(
            "新しいファイルを作成", QMessageBox.ButtonRole.ActionRole
        )
        msg_box.addButton("キャンセル", QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()

        clicked_button = msg_box.clickedButton()
        if clicked_button == select_button:
            db_path, _ = QFileDialog.getOpenFileName(
                None,
                "データベースファイルを選択",
                "",
                "データベースファイル (*.db *.sqlite)",
            )
        elif clicked_button == create_button:
            dir_path = QFileDialog.getExistingDirectory(
                None, "データベースを作成するフォルダを選択"
            )
            if dir_path:
                db_path = os.path.join(dir_path, "prompt_data.db")
            else:
                db_path = None
        else:  # キャンセル
            sys.exit(0)

        if db_path:
            save_db_path_to_preference(db_path)
        else:
            # ユーザーがファイルダイアログをキャンセルした場合
            sys.exit(0)

    db.set_db_path(db_path)

    try:
        db.initialize_db()
    except Exception as e:
        print(f"FATAL: Could not initialize database: {e}")
        QMessageBox.critical(
            None, "データベースエラー", f"データベースの初期化に失敗しました: {e}"
        )
        sys.exit(1)

    try:
        window = MainWindow()
        window.show()
    except Exception as e:
        print(f"FATAL: Could not create main window: {e}")
        QMessageBox.critical(
            None, "アプリケーションエラー", f"メインウィンドウの作成に失敗しました: {e}"
        )
        sys.exit(1)

    sys.exit(app.exec())
