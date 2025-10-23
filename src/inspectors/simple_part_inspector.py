# src/inspectors/simple_part_inspector.py
from PySide6.QtWidgets import QLabel, QLineEdit, QTextEdit
from .base_inspector import BaseInspector
from ..models import PromptPartBase  # 対応するデータモデル
from typing import Optional, Any


class SimplePartInspector(BaseInspector):
    """Costume, Pose など PromptPartBase ベースのシンプルなオブジェクト用インスペクター。"""

    def _populate_fields(self):
        super()._clear_widget()
        item_data: Optional[PromptPartBase] = self._current_item_data

        if not item_data:
            return

        # フィールドを追加
        name_edit = QLineEdit(getattr(item_data, "name", ""))
        tags_edit = QLineEdit(", ".join(getattr(item_data, "tags", [])))
        prompt_edit = QTextEdit(getattr(item_data, "prompt", ""))
        prompt_edit.setFixedHeight(60)
        neg_prompt_edit = QTextEdit(getattr(item_data, "negative_prompt", ""))
        neg_prompt_edit.setFixedHeight(60)

        self.layout.addRow("Name:", name_edit)
        self.layout.addRow("Tags:", tags_edit)
        self.layout.addRow("Prompt:", prompt_edit)
        self.layout.addRow("Negative Prompt:", neg_prompt_edit)

        # ウィジェットを保存
        self._widgets["name"] = name_edit
        self._widgets["tags"] = tags_edit
        self._widgets["prompt"] = prompt_edit
        self._widgets["negative_prompt"] = neg_prompt_edit
