# src/widgets/add_work_form.py
import time
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QDialogButtonBox,
    QMessageBox,
)
from PySide6.QtCore import Slot
from typing import Optional, Dict, Any
from ..models import Work  # Work モデルをインポート


class AddWorkForm(QDialog):
    def __init__(
        self, initial_data: Optional[Work], db_dict: Dict[str, Dict], parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle(
            "作品 (Work) の編集" if initial_data else "新規 作品 (Work) の追加"
        )
        self.initial_data = initial_data
        self.saved_data: Optional[Work] = None

        # UI Elements
        self.title_jp_edit = QLineEdit()
        self.title_en_edit = QLineEdit()
        self.tags_edit = QLineEdit()
        self.sns_tags_edit = QLineEdit()

        # Set Initial Data
        if initial_data:
            self.title_jp_edit.setText(getattr(initial_data, "title_jp", ""))
            self.title_en_edit.setText(getattr(initial_data, "title_en", ""))
            self.tags_edit.setText(", ".join(getattr(initial_data, "tags", [])))
            self.sns_tags_edit.setText(getattr(initial_data, "sns_tags", ""))

        # Layout
        layout = QVBoxLayout(self)
        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("タイトル (日本語):"))
        form_layout.addWidget(self.title_jp_edit)
        form_layout.addWidget(QLabel("タイトル (英語):"))
        form_layout.addWidget(self.title_en_edit)
        form_layout.addWidget(QLabel("タグ (カンマ区切り):"))
        form_layout.addWidget(self.tags_edit)
        form_layout.addWidget(QLabel("SNS ハッシュタグ:"))
        form_layout.addWidget(self.sns_tags_edit)
        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    @Slot()
    def accept(self):
        title_jp = self.title_jp_edit.text().strip()
        if not title_jp:
            QMessageBox.warning(self, "入力エラー", "タイトル (日本語) は必須です。")
            return

        self.saved_data = Work(
            id=getattr(self.initial_data, "id", None) or f"work_{int(time.time())}",
            title_jp=title_jp,
            title_en=self.title_en_edit.text().strip(),
            tags=[t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
            sns_tags=self.sns_tags_edit.text().strip(),
        )
        super().accept()

    def get_data(self) -> Optional[Work]:
        return self.saved_data
