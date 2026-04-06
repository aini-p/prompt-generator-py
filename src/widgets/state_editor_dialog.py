# src/widgets/state_editor_dialog.py
import time
from PySide6.QtWidgets import QLineEdit, QTextEdit, QMessageBox
from typing import Optional, Dict

from .base_editor_dialog import BaseEditorDialog
from ..models import State


class StateEditorDialog(BaseEditorDialog):  # ★ クラス名を変更
    def __init__(
        self,
        initial_data: Optional[State],
        db_dict: Dict,
        db_key: str,
        parent=None,
    ):
        super().__init__(initial_data, db_dict, db_key, "State", parent)
        # self.object_type_key = "state" # ID生成用に保持 (BaseEditorDialog でやるので不要)

    def _populate_fields(self):
        self.form_layout = self.setup_form_layout()
        if not self.form_layout:
            return

        # UI Elements
        self.name_edit = QLineEdit(getattr(self.initial_data, "name", ""))
        # ▼▼▼ category フィールドを追加 ▼▼▼
        self.tags_edit = QLineEdit(", ".join(getattr(self.initial_data, "tags", [])))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlainText(
            getattr(self.initial_data, "prompt", "")
        )  # ★ 変更
        self.prompt_edit.setFixedHeight(60)

        self.negative_prompt_edit = QTextEdit()
        self.negative_prompt_edit.setPlainText(
            getattr(self.initial_data, "negative_prompt", "")
        )
        self.negative_prompt_edit.setFixedHeight(60)

        category_ref_widget = self._create_reference_editor_widget(
            field_name="category",
            current_id=getattr(self.initial_data, "category", None),
            reference_db_key="state_categories",
            reference_modal_type="STATE_CATEGORY",
            allow_none=False,
            none_text="- カテゴリを選択 -",
        )

        # Layout
        self.form_layout.addRow("名前 (Name):", self.name_edit)
        self.form_layout.addRow("カテゴリ (Category):", category_ref_widget)
        self.form_layout.addRow("タグ (Tags):", self.tags_edit)
        self.form_layout.addRow("プロンプト (Positive):", self.prompt_edit)
        self.form_layout.addRow("ネガティブ (Negative):", self.negative_prompt_edit)

        # _widgets
        self._widgets["name"] = self.name_edit
        self._widgets["tags"] = self.tags_edit
        self._widgets["prompt"] = self.prompt_edit
        self._widgets["negative_prompt"] = self.negative_prompt_edit

    def get_data(self) -> Optional[State]:  # ★ 戻り値型を State に変更
        name = self.name_edit.text().strip()
        category = self._get_widget_value("category")

        if not name:
            QMessageBox.warning(self, "入力エラー", "Name は必須です。")
            return None
        if not category:
            QMessageBox.warning(self, "入力エラー", "Category は必須です。")
            return None

        # State としてデータを生成/更新
        if self.initial_data:
            updated_state = self.initial_data  # ★ 変数名変更
            self._update_object_from_widgets(updated_state)
            updated_state.category = category
            return updated_state
        else:
            new_state = State(  # ★ State で初期化
                id=f"state_{int(time.time())}",  # ★ ID プレフィックス変更
                name=name,
                category=category,  # ★ 設定
                tags=[t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
                prompt=self.prompt_edit.toPlainText().strip(),
                negative_prompt=self.negative_prompt_edit.toPlainText().strip(),
            )
            return new_state
