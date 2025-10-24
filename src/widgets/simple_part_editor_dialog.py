# src/widgets/simple_part_editor_dialog.py (旧 add_simple_part_form.py)
import time
from PySide6.QtWidgets import QLabel, QLineEdit, QTextEdit, QMessageBox, QFormLayout
from PySide6.QtCore import Slot
from typing import Optional, Dict, Any

from .base_editor_dialog import BaseEditorDialog
from ..models import PromptPartBase  # 型を具体的に


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

    def _populate_fields(self):
        self.form_layout = self.setup_form_layout()  # 基底クラスのヘルパーを呼び出す
        if not self.form_layout:
            return  # エラー処理 (念のため)
        # UI Elements
        self.name_edit = QLineEdit(getattr(self.initial_data, "name", ""))
        self.tags_edit = QLineEdit(", ".join(getattr(self.initial_data, "tags", [])))
        self.prompt_edit = QTextEdit(getattr(self.initial_data, "prompt", ""))
        self.prompt_edit.setFixedHeight(60)
        self.negative_prompt_edit = QTextEdit(
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
            new_part = PromptPartBase(
                id=f"{self.object_type_key}_{int(time.time())}",
                name=name,
                tags=[t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
                prompt=self.prompt_edit.toPlainText().strip(),
                negative_prompt=self.negative_prompt_edit.toPlainText().strip(),
            )
            # ★注意: 本来は Pose, Expression など具体的な型で返すべきだが、
            # このフォームは汎用的なので PromptPartBase で返す。
            # 呼び出し側 (MainWindow) で適切な型に変換するか、
            # または SimplePartEditorDialog を使わず各モデル専用の Dialog を作る方が望ましい。
            # ここでは PromptPartBase のまま返す実装とする。
            return new_part


# --- スタイル定義は削除 ---
