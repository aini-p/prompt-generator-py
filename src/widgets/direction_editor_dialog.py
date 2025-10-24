# src/widgets/direction_editor_dialog.py
import time
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QMessageBox,
    QFormLayout,
    QWidget,  # QWidget を追加
)
from PySide6.QtCore import Slot
from typing import Optional, Dict, Any

from .base_editor_dialog import BaseEditorDialog
from ..models import Direction


class DirectionEditorDialog(BaseEditorDialog):
    def __init__(
        self, initial_data: Optional[Direction], db_dict: Dict[str, Dict], parent=None
    ):
        super().__init__(initial_data, db_dict, "演出 (Direction)", parent)
        # UI構築 (_populate_fields が呼ばれる)

    def _populate_fields(self):
        self.form_layout = self.setup_form_layout()  # 基底クラスのヘルパーを呼び出す
        if not self.form_layout:
            return  # エラー処理 (念のため)
        # UI Elements (変更なし)
        self.name_edit = QLineEdit(getattr(self.initial_data, "name", ""))
        self.tags_edit = QLineEdit(", ".join(getattr(self.initial_data, "tags", [])))
        self.prompt_edit = QTextEdit(getattr(self.initial_data, "prompt", ""))
        self.prompt_edit.setFixedHeight(60)
        self.negative_prompt_edit = QTextEdit(
            getattr(self.initial_data, "negative_prompt", "")
        )
        self.negative_prompt_edit.setFixedHeight(60)

        # --- ▼▼▼ Combo Boxes を _create_reference_editor_widget に変更 ▼▼▼ ---
        costume_ref_widget = self._create_reference_editor_widget(
            field_name="costume_id",
            current_id=getattr(self.initial_data, "costume_id", None),
            reference_db_key="costumes",
            reference_modal_type="COSTUME",
            allow_none=True,
            none_text="(上書きしない)",
        )
        pose_ref_widget = self._create_reference_editor_widget(
            field_name="pose_id",
            current_id=getattr(self.initial_data, "pose_id", None),
            reference_db_key="poses",
            reference_modal_type="POSE",
            allow_none=True,
            none_text="(上書きしない)",
        )
        expression_ref_widget = self._create_reference_editor_widget(
            field_name="expression_id",
            current_id=getattr(self.initial_data, "expression_id", None),
            reference_db_key="expressions",
            reference_modal_type="EXPRESSION",
            allow_none=True,
            none_text="(上書きしない)",
        )
        # --- ▲▲▲ 変更ここまで ▲▲▲ ---

        # Layout
        self.form_layout.addRow("名前:", self.name_edit)
        self.form_layout.addRow("タグ:", self.tags_edit)
        self.form_layout.addRow("追加プロンプト (Positive):", self.prompt_edit)
        self.form_layout.addRow(
            "追加ネガティブプロンプト (Negative):", self.negative_prompt_edit
        )
        self.form_layout.addRow(
            QLabel(
                "--- 状態の上書き (オプション) ---",
                styleSheet="color: #555; margin-top: 10px;",
            )
        )
        # --- ▼▼▼ ウィジェットをレイアウトに追加 ▼▼▼ ---
        self.form_layout.addRow("衣装 (上書き):", costume_ref_widget)
        self.form_layout.addRow("ポーズ (上書き):", pose_ref_widget)
        self.form_layout.addRow("表情 (上書き):", expression_ref_widget)
        # --- ▲▲▲ 変更ここまで ▲▲▲ ---

        # _widgets への登録 (参照ウィジェットは _reference_widgets に自動登録)
        self._widgets["name"] = self.name_edit
        self._widgets["tags"] = self.tags_edit
        self._widgets["prompt"] = self.prompt_edit
        self._widgets["negative_prompt"] = self.negative_prompt_edit
        # self._widgets["costume_id"] = self.costume_combo # 削除
        # self._widgets["pose_id"] = self.pose_combo       # 削除
        # self._widgets["expression_id"] = self.expression_combo # 削除

    def get_data(self) -> Optional[Direction]:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "名前は必須です。")
            return None

        # costume_id などは _update_object_from_widgets で取得・設定される

        if self.initial_data:  # 更新
            updated_direction = self.initial_data
            if not self._update_object_from_widgets(updated_direction):
                return None  # 更新失敗
            return updated_direction
        else:  # 新規作成
            tags_text = self.tags_edit.text()
            prompt_text = self.prompt_edit.toPlainText().strip()
            neg_prompt_text = self.negative_prompt_edit.toPlainText().strip()
            costume_id = self._get_widget_value("costume_id")  # ヘルパー使用
            pose_id = self._get_widget_value("pose_id")  # ヘルパー使用
            expression_id = self._get_widget_value("expression_id")  # ヘルパー使用

            new_direction = Direction(
                id=f"dir_{int(time.time())}",
                name=name,
                tags=[t.strip() for t in tags_text.split(",") if t.strip()],
                prompt=prompt_text,
                negative_prompt=neg_prompt_text,
                costume_id=costume_id,
                pose_id=pose_id,
                expression_id=expression_id,
            )
            return new_direction
