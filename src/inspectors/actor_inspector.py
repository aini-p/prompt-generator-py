# src/inspectors/actor_inspector.py
from PySide6.QtWidgets import QLabel, QLineEdit, QTextEdit, QComboBox
from PySide6.QtCore import Slot
from .base_inspector import BaseInspector
from ..models import Actor, Character
from typing import Optional, Any, Dict


class ActorInspector(BaseInspector):
    """Actor オブジェクト用インスペクター。"""

    def _populate_fields(self):
        super()._clear_widget()
        item_data: Optional[Actor] = self._current_item_data
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

        # --- Work / Character selection ---
        current_character_id = getattr(item_data, "character_id", None)
        current_work_id = self._get_work_id_for_character(current_character_id)

        work_combo = self._create_combo_box(
            current_work_id,
            self._db_data_ref.get("works", {}),
            allow_none=True,
            none_text="(Unassigned)",
            display_attr="title_jp",
        )
        work_combo.currentIndexChanged.connect(self._on_work_changed)
        self.layout.addRow("Work:", work_combo)
        self._widgets["_work_selection"] = work_combo  # 内部管理用

        self.character_combo = QComboBox()  # Characterコンボをインスタンス変数に
        self.layout.addRow("Character:", self.character_combo)
        self._widgets["character_id"] = (
            self.character_combo
        )  # character_id フィールドに対応
        self._update_character_combo(current_work_id, current_character_id)

        # --- Base selections ---
        base_fields = ["base_costume_id", "base_pose_id", "base_expression_id"]
        combo_map = {
            "base_costume_id": ("costumes", self._db_data_ref.get("costumes", {})),
            "base_pose_id": ("poses", self._db_data_ref.get("poses", {})),
            "base_expression_id": (
                "expressions",
                self._db_data_ref.get("expressions", {}),
            ),
        }
        for field_name in base_fields:
            current_value = getattr(item_data, field_name, "")
            widget = self._create_combo_box(
                current_value, combo_map[field_name][1], allow_none=True
            )
            self.layout.addRow(f"{field_name.replace('_', ' ').capitalize()}:", widget)
            self._widgets[field_name] = widget

    def _get_work_id_for_character(self, character_id: Optional[str]) -> Optional[str]:
        """Character ID から Work ID を取得します。"""
        if character_id:
            character = self._db_data_ref.get("characters", {}).get(character_id)
            if character:
                return character.work_id
        return None

    @Slot(int)
    def _on_work_changed(self):
        """Work選択が変更されたらCharacterリストを更新します。"""
        work_combo = self._widgets.get("_work_selection")
        if isinstance(work_combo, QComboBox):
            selected_work_id = work_combo.currentData()
            self._update_character_combo(selected_work_id, None)  # 選択はリセット

    def _update_character_combo(
        self, selected_work_id: Optional[str], current_character_id: Optional[str]
    ):
        """Characterコンボボックスの内容を更新・選択します。"""
        # (InspectorPanelから移動してきたロジックと同じ)
        self.character_combo.blockSignals(True)
        self.character_combo.clear()
        self.character_combo.addItem("(None)", None)
        ids = [None]
        filtered_characters = {}
        if selected_work_id:
            all_characters = self._db_data_ref.get("characters", {})
            filtered_characters = {
                cid: c
                for cid, c in all_characters.items()
                if c.work_id == selected_work_id
            }
        sorted_chars = sorted(
            filtered_characters.values(), key=lambda c: c.name.lower()
        )
        for char in sorted_chars:
            self.character_combo.addItem(f"{char.name} ({char.id})", char.id)
            ids.append(char.id)
        try:
            index = (
                ids.index(current_character_id) if current_character_id in ids else 0
            )
            self.character_combo.setCurrentIndex(index)
        except ValueError:
            self.character_combo.setCurrentIndex(0)
        self.character_combo.blockSignals(False)
