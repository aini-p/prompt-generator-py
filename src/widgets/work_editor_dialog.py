# src/widgets/work_editor_dialog.py (旧 add_work_form.py)
import time
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QMessageBox,
    QFormLayout,
)  # QFormLayout を追加
from PySide6.QtCore import Slot
from typing import Optional, Dict, Any

from .base_editor_dialog import BaseEditorDialog
from ..models import Work


class WorkEditorDialog(BaseEditorDialog):
    def __init__(
        self, initial_data: Optional[Work], db_dict: Dict[str, Dict], parent=None
    ):
        super().__init__(initial_data, db_dict, "作品 (Work)", parent)
        # UI構築 (_populate_fields が呼ばれる)

    def _populate_fields(self):
        self.form_layout = self.setup_form_layout()  # 基底クラスのヘルパーを呼び出す
        if not self.form_layout:
            return  # エラー処理 (念のため)
        # UI Elements
        self.title_jp_edit = QLineEdit(getattr(self.initial_data, "title_jp", ""))
        self.title_en_edit = QLineEdit(getattr(self.initial_data, "title_en", ""))
        self.tags_edit = QLineEdit(", ".join(getattr(self.initial_data, "tags", [])))
        self.sns_tags_edit = QLineEdit(getattr(self.initial_data, "sns_tags", ""))

        # Layout (基底クラスの form_layout を使用)
        self.form_layout.addRow("タイトル (日本語):", self.title_jp_edit)
        self.form_layout.addRow("タイトル (英語):", self.title_en_edit)
        self.form_layout.addRow("タグ (カンマ区切り):", self.tags_edit)
        self.form_layout.addRow("SNS ハッシュタグ:", self.sns_tags_edit)

        # _widgets への登録
        self._widgets["title_jp"] = self.title_jp_edit
        self._widgets["title_en"] = self.title_en_edit
        self._widgets["tags"] = self.tags_edit
        self._widgets["sns_tags"] = self.sns_tags_edit

    def get_data(self) -> Optional[Work]:
        title_jp = self.title_jp_edit.text().strip()
        if not title_jp:
            QMessageBox.warning(self, "入力エラー", "タイトル (日本語) は必須です。")
            return None  # バリデーションエラー

        if self.initial_data:  # 更新
            updated_work = self.initial_data
            self._update_object_from_widgets(updated_work)  # ヘルパーで更新
            return updated_work
        else:  # 新規作成
            new_work = Work(
                id=f"work_{int(time.time())}",
                title_jp=title_jp,
                title_en=self.title_en_edit.text().strip(),
                tags=[t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
                sns_tags=self.sns_tags_edit.text().strip(),
            )
            return new_work
