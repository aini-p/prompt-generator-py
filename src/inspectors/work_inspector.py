# src/inspectors/work_inspector.py
from PySide6.QtWidgets import QLabel, QLineEdit
from .base_inspector import BaseInspector
from ..models import Work
from typing import Optional, Any


class WorkInspector(BaseInspector):
    """Work オブジェクト用インスペクター。"""

    def _populate_fields(self):
        super()._clear_widget()
        item_data: Optional[Work] = self._current_item_data
        if not item_data:
            return

        title_jp_edit = QLineEdit(getattr(item_data, "title_jp", ""))
        title_en_edit = QLineEdit(getattr(item_data, "title_en", ""))
        tags_edit = QLineEdit(", ".join(getattr(item_data, "tags", [])))
        sns_tags_edit = QLineEdit(getattr(item_data, "sns_tags", ""))

        self.layout.addRow("Title (JP):", title_jp_edit)
        self.layout.addRow("Title (EN):", title_en_edit)
        self.layout.addRow("Tags:", tags_edit)
        self.layout.addRow("SNS Tags:", sns_tags_edit)

        self._widgets["title_jp"] = title_jp_edit
        self._widgets["title_en"] = title_en_edit
        self._widgets["tags"] = tags_edit
        self._widgets["sns_tags"] = sns_tags_edit
