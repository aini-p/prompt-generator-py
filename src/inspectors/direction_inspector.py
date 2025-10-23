# src/inspectors/direction_inspector.py
from PySide6.QtWidgets import QLabel, QLineEdit, QTextEdit, QComboBox
from typing import Optional, Any
from .base_inspector import BaseInspector
from ..models import Direction  # 対応するデータモデル


class DirectionInspector(BaseInspector):
    """Direction オブジェクト用インスペクター。"""

    def _populate_fields(self):
        super()._clear_widget()
        item_data: Optional[Direction] = self._current_item_data

        if not item_data:
            return

        # --- Common fields ---
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

        self._widgets["name"] = name_edit
        self._widgets["tags"] = tags_edit
        self._widgets["prompt"] = prompt_edit
        self._widgets["negative_prompt"] = neg_prompt_edit

        # --- Direction specific fields ---
        dir_fields = ["costume_id", "pose_id", "expression_id"]
        combo_map = {
            "costume_id": ("costumes", self._db_data_ref.get("costumes", {})),
            "pose_id": ("poses", self._db_data_ref.get("poses", {})),
            "expression_id": ("expressions", self._db_data_ref.get("expressions", {})),
        }
        for field_name in dir_fields:
            current_value = getattr(item_data, field_name, None)  # Optional[str]
            # _create_combo_box ヘルパーを使用してコンボボックスを作成
            widget = self._create_combo_box(
                current_value,
                combo_map[field_name][1],  # items_dict を渡す
                allow_none=True,
                none_text="(None / Inherit)",  # 空の場合の表示テキスト
            )
            self.layout.addRow(f"{field_name.replace('_', ' ').capitalize()}:", widget)
            self._widgets[field_name] = widget
