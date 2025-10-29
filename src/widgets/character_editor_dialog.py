# src/widgets/character_editor_dialog.py (旧 add_character_form.py)
import time
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QComboBox,
    QMessageBox,
    QFormLayout,
    QWidget,  # QFormLayout を追加
)
from PySide6.QtCore import Slot
from typing import Optional, Dict, Any, List

from .base_editor_dialog import BaseEditorDialog  # 基底クラスをインポート
from ..models import Character, Work


class CharacterEditorDialog(BaseEditorDialog):
    def __init__(
        self, initial_data: Optional[Character], db_dict: Dict[str, Dict], parent=None
    ):
        super().__init__(initial_data, db_dict, "キャラクター (Character)", parent)
        # UI構築 (_populate_fields が呼ばれる)

    def _populate_fields(self):
        self.form_layout = self.setup_form_layout()  # 基底クラスのヘルパーを呼び出す
        if not self.form_layout:
            return  # エラー処理 (念のため)
        # UI Elements
        self.name_edit = QLineEdit(getattr(self.initial_data, "name", ""))
        self.tags_edit = QLineEdit(", ".join(getattr(self.initial_data, "tags", [])))
        self.personal_color_edit = QLineEdit(
            getattr(self.initial_data, "personal_color", "")
        )
        self.underwear_color_edit = QLineEdit(
            getattr(self.initial_data, "underwear_color", "")
        )

        # Work Combo Box (using helper from base class)
        work_ref_widget = self._create_reference_editor_widget(
            field_name="work_id",  # 対応する属性名
            current_id=getattr(self.initial_data, "work_id", None),
            reference_db_key="works",
            reference_modal_type="WORK",  # MainWindow のマッピングキー
            allow_none=False,  # Work は必須
            none_text="- 作品を選択 -",
            display_attr="title_jp",
        )

        # Layout (using base class's form_layout)
        self.form_layout.addRow("名前:", self.name_edit)
        self.form_layout.addRow("登場作品:", work_ref_widget)
        self.form_layout.addRow("タグ (カンマ区切り):", self.tags_edit)
        self.form_layout.addRow("パーソナルカラー:", self.personal_color_edit)
        self.form_layout.addRow("下着カラー:", self.underwear_color_edit)

        # _widgets への登録
        self._widgets["name"] = self.name_edit
        self._widgets["tags"] = self.tags_edit
        self._widgets["personal_color"] = self.personal_color_edit
        self._widgets["underwear_color"] = self.underwear_color_edit

        # --- 不要なコード削除 ---
        # _populate_work_combo メソッドは不要
        # 初期値設定はウィジェット作成時に実施済み
        # button_box の作成と接続は基底クラス

    # --- accept を get_data に変更 ---
    def get_data(self) -> Optional[Character]:
        name = self.name_edit.text().strip()
        work_id = self._get_widget_value("work_id")

        if not name:
            QMessageBox.warning(self, "入力エラー", "名前は必須です。")
            return None
        if not work_id:
            QMessageBox.warning(self, "入力エラー", "登場作品を選択してください。")
            return None

        work_id = self._get_widget_value("work_id")

        if self.initial_data:  # 更新
            updated_char = self.initial_data
            if not self._update_object_from_widgets(updated_char):
                return None  # 更新失敗
            # work_id もヘルパー内で更新される
            updated_char.work_id = work_id
            return updated_char
        else:  # 新規作成
            tags_text = self.tags_edit.text()
            personal_color = self.personal_color_edit.text().strip()
            underwear_color = self.underwear_color_edit.text().strip()
            new_char = Character(
                id=f"char_{int(time.time())}",
                name=name,
                work_id=work_id or "",  # None でないことはチェック済み
                tags=[t.strip() for t in tags_text.split(",") if t.strip()],
                personal_color=personal_color,
                underwear_color=underwear_color,
            )
            return new_char

    # --- 元の get_data は削除 ---
