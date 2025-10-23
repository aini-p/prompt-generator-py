# src/inspectors/character_inspector.py
from PySide6.QtWidgets import QLabel, QLineEdit, QComboBox
from .base_inspector import BaseInspector
from ..models import Character
from typing import Optional, Any


class CharacterInspector(BaseInspector):
    """Character オブジェクト用インスペクター。"""

    def _populate_fields(self):
        super()._clear_widget()
        item_data: Optional[Character] = self._current_item_data
        if not item_data:
            return

        name_edit = QLineEdit(getattr(item_data, "name", ""))
        # Work 選択コンボボックス
        work_combo = self._create_combo_box(
            getattr(item_data, "work_id", None),
            self._db_data_ref.get("works", {}),  # works データを参照
            allow_none=False,  # Work は必須とする
            none_text="- Select Work -",
            display_attr="title_jp",
        )
        tags_edit = QLineEdit(", ".join(getattr(item_data, "tags", [])))

        self.layout.addRow("Name:", name_edit)
        self.layout.addRow("Work:", work_combo)
        self.layout.addRow("Tags:", tags_edit)

        self._widgets["name"] = name_edit
        self._widgets["work_id"] = work_combo  # コンボボックス自体を work_id に紐付け
        self._widgets["tags"] = tags_edit
