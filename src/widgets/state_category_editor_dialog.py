import time
from PySide6.QtWidgets import QLineEdit, QMessageBox
from typing import Optional, Dict

from .base_editor_dialog import BaseEditorDialog
from ..models import StateCategory


class StateCategoryEditorDialog(BaseEditorDialog):
    def __init__(
        self,
        initial_data: Optional[StateCategory],
        db_dict: Dict,
        db_key: str,
        parent=None,
    ):
        super().__init__(initial_data, db_dict, db_key, "State Category", parent)

    def _populate_fields(self):
        self.form_layout = self.setup_form_layout()
        if not self.form_layout:
            return

        self.name_edit = QLineEdit(getattr(self.initial_data, "name", ""))
        self.form_layout.addRow("名前 (Name):", self.name_edit)

        self._widgets["name"] = self.name_edit

    def get_data(self) -> Optional[StateCategory]:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "Name は必須です。")
            return None

        if self.initial_data:
            updated_category = self.initial_data
            self._update_object_from_widgets(updated_category)
            return updated_category

        return StateCategory(
            id=f"state_category_{int(time.time() * 1000)}",
            name=name,
        )