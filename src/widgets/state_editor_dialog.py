# src/widgets/state_editor_dialog.py
import time
from PySide6.QtWidgets import QLabel, QLineEdit, QTextEdit, QMessageBox, QFormLayout
from PySide6.QtCore import Slot
from typing import Optional, Dict, Any

from .base_editor_dialog import BaseEditorDialog
from ..models import State  # ★ モデルを State に変更


class StateEditorDialog(BaseEditorDialog):  # ★ クラス名を変更
    def __init__(
        self,
        initial_data: Optional[State],  # ★ 型ヒントを State に変更
        # objectType: str, # 不要
        db_dict: Dict[str, Dict],  # db_dict は BaseEditorDialog が必要とする
        parent=None,
    ):
        # ★ objectType を固定で渡す
        super().__init__(initial_data, db_dict, "状態 (State)", parent)
        # self.object_type_key = "state" # ID生成用に保持 (BaseEditorDialog でやるので不要)

    def _populate_fields(self):
        self.form_layout = self.setup_form_layout()
        if not self.form_layout:
            return

        # UI Elements
        self.name_edit = QLineEdit(getattr(self.initial_data, "name", ""))
        # ▼▼▼ category フィールドを追加 ▼▼▼
        self.category_edit = QLineEdit(getattr(self.initial_data, "category", ""))
        self.category_edit.setPlaceholderText("例: damaged, wet, casual")
        # ▲▲▲ 追加ここまで ▲▲▲
        self.tags_edit = QLineEdit(", ".join(getattr(self.initial_data, "tags", [])))
        self.prompt_edit = QTextEdit(getattr(self.initial_data, "prompt", ""))
        self.prompt_edit.setFixedHeight(60)
        self.negative_prompt_edit = QTextEdit(
            getattr(self.initial_data, "negative_prompt", "")
        )
        self.negative_prompt_edit.setFixedHeight(60)

        # Layout
        self.form_layout.addRow("名前 (Name):", self.name_edit)
        # ▼▼▼ category フィールドを配置 ▼▼▼
        self.form_layout.addRow("カテゴリ (Category):", self.category_edit)
        # ▲▲▲ 追加ここまで ▲▲▲
        self.form_layout.addRow("タグ (Tags):", self.tags_edit)
        self.form_layout.addRow("プロンプト (Positive):", self.prompt_edit)
        self.form_layout.addRow("ネガティブ (Negative):", self.negative_prompt_edit)

        # _widgets
        self._widgets["name"] = self.name_edit
        self._widgets["category"] = self.category_edit  # ★ 追加
        self._widgets["tags"] = self.tags_edit
        self._widgets["prompt"] = self.prompt_edit
        self._widgets["negative_prompt"] = self.negative_prompt_edit

    def get_data(self) -> Optional[State]:  # ★ 戻り値型を State に変更
        name = self.name_edit.text().strip()
        category = self.category_edit.text().strip()  # ★ カテゴリ取得

        if not name:
            QMessageBox.warning(self, "入力エラー", "Name は必須です。")
            return None
        if not category:  # ★ カテゴリも必須とする
            QMessageBox.warning(self, "入力エラー", "Category は必須です。")
            return None

        # State としてデータを生成/更新
        if self.initial_data:
            updated_state = self.initial_data  # ★ 変数名変更
            self._update_object_from_widgets(updated_state)
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
