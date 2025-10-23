# src/widgets/add_character_form.py
import time
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QDialogButtonBox,
    QMessageBox,
)
from PySide6.QtCore import Slot
from typing import Optional, Dict, Any, List
from ..models import Character, Work  # Character, Work モデルをインポート


class AddCharacterForm(QDialog):
    def __init__(
        self, initial_data: Optional[Character], db_dict: Dict[str, Dict], parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle(
            "キャラクター (Character) の編集"
            if initial_data
            else "新規 キャラクター (Character) の追加"
        )
        self.initial_data = initial_data
        self.db_dict = db_dict  # Workリスト表示用
        self.saved_data: Optional[Character] = None

        # UI Elements
        self.name_edit = QLineEdit()
        self.work_combo = QComboBox()
        self.tags_edit = QLineEdit()

        # Populate Work Combo
        self._populate_work_combo()

        # Set Initial Data
        if initial_data:
            self.name_edit.setText(getattr(initial_data, "name", ""))
            self.tags_edit.setText(", ".join(getattr(initial_data, "tags", [])))
            # Work コンボを選択
            work_id = getattr(initial_data, "work_id", None)
            index = self.work_combo.findData(work_id)
            if index >= 0:
                self.work_combo.setCurrentIndex(index)
            else:
                self.work_combo.setCurrentIndex(0)  # 見つからなければ先頭 (未選択)
        else:
            self.work_combo.setCurrentIndex(0)  # 新規の場合も先頭

        # Layout
        layout = QVBoxLayout(self)
        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("名前:"))
        form_layout.addWidget(self.name_edit)
        form_layout.addWidget(QLabel("登場作品:"))
        form_layout.addWidget(self.work_combo)
        form_layout.addWidget(QLabel("タグ (カンマ区切り):"))
        form_layout.addWidget(self.tags_edit)
        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _populate_work_combo(self):
        """Work 選択コンボボックスの内容を作成します。"""
        self.work_combo.addItem("- 作品を選択 -", None)  # itemData に None
        works = self.db_dict.get("works", {})
        # 作品を日本語タイトルでソート
        sorted_works = sorted(
            works.values(), key=lambda w: getattr(w, "title_jp", "").lower()
        )
        for work in sorted_works:
            work_id = getattr(work, "id", None)
            work_title = getattr(work, "title_jp", "Unnamed")
            if work_id:
                self.work_combo.addItem(
                    f"{work_title} ({work_id})", work_id
                )  # itemData に ID

    @Slot()
    def accept(self):
        name = self.name_edit.text().strip()
        work_id = self.work_combo.currentData()  # itemData (ID または None) を取得

        if not name:
            QMessageBox.warning(self, "入力エラー", "名前は必須です。")
            return
        if not work_id:
            QMessageBox.warning(self, "入力エラー", "登場作品を選択してください。")
            return

        self.saved_data = Character(
            id=getattr(self.initial_data, "id", None) or f"char_{int(time.time())}",
            name=name,
            work_id=work_id,
            tags=[t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
        )
        super().accept()

    def get_data(self) -> Optional[Character]:
        return self.saved_data
