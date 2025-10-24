# src/widgets/direction_editor_dialog.py (旧 add_direction_form.py)
import time
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QMessageBox,
    QFormLayout,  # QFormLayout を追加
)
from PySide6.QtCore import Slot
from typing import Optional, Dict, Any

from .base_editor_dialog import BaseEditorDialog
from ..models import Direction  # 必要なモデルをインポート


class DirectionEditorDialog(BaseEditorDialog):
    def __init__(
        self, initial_data: Optional[Direction], db_dict: Dict[str, Dict], parent=None
    ):
        super().__init__(initial_data, db_dict, "演出 (Direction)", parent)
        # UI構築 (_populate_fields が呼ばれる)

    def _populate_fields(self):
        # UI Elements
        self.name_edit = QLineEdit(getattr(self.initial_data, "name", ""))
        self.tags_edit = QLineEdit(", ".join(getattr(self.initial_data, "tags", [])))
        self.prompt_edit = QTextEdit(getattr(self.initial_data, "prompt", ""))
        self.prompt_edit.setFixedHeight(60)  # 高さを設定
        self.negative_prompt_edit = QTextEdit(
            getattr(self.initial_data, "negative_prompt", "")
        )
        self.negative_prompt_edit.setFixedHeight(60)  # 高さを設定

        # Combo Boxes (using helper)
        self.costume_combo = self._create_combo_box(
            getattr(self.initial_data, "costume_id", None),
            self.db_dict.get("costumes", {}),
            allow_none=True,
            none_text="(上書きしない)",
        )
        self.pose_combo = self._create_combo_box(
            getattr(self.initial_data, "pose_id", None),
            self.db_dict.get("poses", {}),
            allow_none=True,
            none_text="(上書きしない)",
        )
        self.expression_combo = self._create_combo_box(
            getattr(self.initial_data, "expression_id", None),
            self.db_dict.get("expressions", {}),
            allow_none=True,
            none_text="(上書きしない)",
        )

        # Layout (using base class's form_layout)
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
        self.form_layout.addRow("衣装 (上書き):", self.costume_combo)
        self.form_layout.addRow("ポーズ (上書き):", self.pose_combo)
        self.form_layout.addRow("表情 (上書き):", self.expression_combo)

        # _widgets への登録
        self._widgets["name"] = self.name_edit
        self._widgets["tags"] = self.tags_edit
        self._widgets["prompt"] = self.prompt_edit
        self._widgets["negative_prompt"] = self.negative_prompt_edit
        self._widgets["costume_id"] = self.costume_combo
        self._widgets["pose_id"] = self.pose_combo
        self._widgets["expression_id"] = self.expression_combo

        # --- 不要なコード削除 ---
        # Populate Combos は _create_combo_box で実施
        # 初期値設定はウィジェット作成時に実施済み
        # button_box の作成と接続は基底クラス

    # --- accept を get_data に変更 ---
    def get_data(self) -> Optional[Direction]:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "名前は必須です。")
            return None

        # コンボボックスの値は _update_object_from_widgets で取得・設定される

        if self.initial_data:  # 更新
            updated_direction = self.initial_data
            self._update_object_from_widgets(updated_direction)
            return updated_direction
        else:  # 新規作成
            tags_text = self.tags_edit.text()
            prompt_text = self.prompt_edit.toPlainText().strip()
            neg_prompt_text = self.negative_prompt_edit.toPlainText().strip()
            costume_id = self.costume_combo.currentData()  # None or str
            pose_id = self.pose_combo.currentData()  # None or str
            expression_id = self.expression_combo.currentData()  # None or str

            new_direction = Direction(
                id=f"dir_{int(time.time())}",
                name=name,
                tags=[t.strip() for t in tags_text.split(",") if t.strip()],
                prompt=prompt_text,
                negative_prompt=neg_prompt_text,
                costume_id=costume_id,  # None も許容される
                pose_id=pose_id,
                expression_id=expression_id,
            )
            return new_direction

    # --- 元の get_data は削除 ---


# --- スタイル定義は削除 ---
