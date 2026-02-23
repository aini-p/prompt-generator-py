# src/widgets/simple_part_editor_dialog.py (旧 add_simple_part_form.py)
import time
from PySide6.QtWidgets import QLabel, QLineEdit, QTextEdit, QMessageBox, QFormLayout
from PySide6.QtCore import Slot
from typing import Optional, Dict, Any

from .base_editor_dialog import BaseEditorDialog
from ..models import (
    PromptPartBase,
    Pose,
    Expression,
    Background,
    Lighting,
    Composition,
    Style,
    AdditionalPrompt,
)


class SimplePartEditorDialog(BaseEditorDialog):
    def __init__(
        self,
        initial_data: Optional[PromptPartBase],
        objectType: str,
        db_dict: Dict[str, Dict],
        parent=None,
    ):
        # db_dict は使わないが、呼び出し側との互換性のために受け取る
        super().__init__(initial_data, db_dict, objectType.capitalize(), parent)
        self.object_type_key = objectType.lower()  # ID生成用に保持
        self.type_map = {
            "pose": Pose,
            "expression": Expression,
            "background": Background,
            "lighting": Lighting,
            "composition": Composition,
            "style": Style,
            "additional_prompt": AdditionalPrompt,
        }

    def _populate_fields(self):
        self.form_layout = self.setup_form_layout()  # 基底クラスのヘルパーを呼び出す
        if not self.form_layout:
            return  # エラー処理 (念のため)
        # UI Elements
        self.name_edit = QLineEdit(getattr(self.initial_data, "name", ""))
        self.tags_edit = QLineEdit(", ".join(getattr(self.initial_data, "tags", [])))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlainText(getattr(self.initial_data, "prompt", ""))
        self.prompt_edit.setFixedHeight(60)

        self.negative_prompt_edit = QTextEdit()
        self.negative_prompt_edit.setPlainText(
            getattr(self.initial_data, "negative_prompt", "")
        )
        self.negative_prompt_edit.setFixedHeight(60)

        # Layout
        self.form_layout.addRow("Name:", self.name_edit)
        self.form_layout.addRow("Tags (カンマ区切り):", self.tags_edit)
        self.form_layout.addRow("プロンプト (Positive):", self.prompt_edit)
        self.form_layout.addRow(
            "ネガティブプロンプト (Negative):", self.negative_prompt_edit
        )

        # _widgets
        self._widgets["name"] = self.name_edit
        self._widgets["tags"] = self.tags_edit
        self._widgets["prompt"] = self.prompt_edit
        self._widgets["negative_prompt"] = self.negative_prompt_edit

    def get_data(self) -> Optional[PromptPartBase]:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "Name は必須です。")
            return None

        # PromptPartBase としてデータを生成/更新
        if self.initial_data:
            updated_part = self.initial_data
            self._update_object_from_widgets(updated_part)
            return updated_part
        else:
            ObjectClass = self.type_map.get(self.object_type_key, PromptPartBase)
            new_part = ObjectClass(
                id=f"{self.object_type_key}_{int(time.time())}",
                name=name,
                tags=[t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
                prompt=self.prompt_edit.toPlainText().strip(),
                negative_prompt=self.negative_prompt_edit.toPlainText().strip(),
            )
            return new_part


# --- スタイル定義は削除 ---
