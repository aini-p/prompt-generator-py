# src/widgets/actor_editor_dialog.py (旧 add_actor_form.py)
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
from typing import Optional, Dict, Any, List

from .base_editor_dialog import BaseEditorDialog
from ..models import Actor, Work, Character  # 必要なモデルをインポート


class ActorEditorDialog(BaseEditorDialog):
    def __init__(
        self, initial_data: Optional[Actor], db_dict: Dict[str, Dict], parent=None
    ):
        super().__init__(initial_data, db_dict, "役者 (Actor)", parent)
        # UI構築 (_populate_fields が呼ばれる)

    def _populate_fields(self):
        # UI Elements
        self.name_edit = QLineEdit(getattr(self.initial_data, "name", ""))
        self.tags_edit = QLineEdit(", ".join(getattr(self.initial_data, "tags", [])))
        self.prompt_edit = QTextEdit(getattr(self.initial_data, "prompt", ""))
        self.prompt_edit.setFixedHeight(60)  # 高さを設定
        self.negative_prompt_edit = QTextEdit(
            getattr(self.initial_data, "negative_prompt", "ugly, watermark")
        )  # デフォルト値
        self.negative_prompt_edit.setFixedHeight(60)  # 高さを設定

        # --- Work / Character selection ---
        current_character_id = getattr(self.initial_data, "character_id", None)
        current_work_id = self._get_work_id_for_character(
            current_character_id
        )  # ヘルパー関数

        self.work_combo = self._create_combo_box(
            current_work_id,
            self.db_dict.get("works", {}),
            allow_none=True,  # 未割り当ても許可
            none_text="(未割り当て)",
            display_attr="title_jp",
        )
        self.character_combo = QComboBox()  # Characterコンボをインスタンス変数に

        # --- Base selections ---
        self.costume_combo = self._create_combo_box(
            getattr(self.initial_data, "base_costume_id", None),
            self.db_dict.get("costumes", {}),
            allow_none=True,
        )
        self.pose_combo = self._create_combo_box(
            getattr(self.initial_data, "base_pose_id", None),
            self.db_dict.get("poses", {}),
            allow_none=True,
        )
        self.expression_combo = self._create_combo_box(
            getattr(self.initial_data, "base_expression_id", None),
            self.db_dict.get("expressions", {}),
            allow_none=True,
        )

        # Layout (using base class's form_layout)
        self.form_layout.addRow("名前:", self.name_edit)
        self.form_layout.addRow("タグ (カンマ区切り):", self.tags_edit)
        self.form_layout.addRow("登場作品 (Work):", self.work_combo)
        self.form_layout.addRow("キャラクター (Character):", self.character_combo)
        self.form_layout.addRow("基本プロンプト (Positive):", self.prompt_edit)
        self.form_layout.addRow(
            "基本ネガティブプロンプト (Negative):", self.negative_prompt_edit
        )
        self.form_layout.addRow("基本衣装:", self.costume_combo)
        self.form_layout.addRow("基本ポーズ:", self.pose_combo)
        self.form_layout.addRow("基本表情:", self.expression_combo)

        # _widgets への登録
        self._widgets["name"] = self.name_edit
        self._widgets["tags"] = self.tags_edit
        self._widgets["prompt"] = self.prompt_edit
        self._widgets["negative_prompt"] = self.negative_prompt_edit
        self._widgets["character_id"] = (
            self.character_combo
        )  # character_id は character_combo の currentData
        self._widgets["base_costume_id"] = self.costume_combo
        self._widgets["base_pose_id"] = self.pose_combo
        self._widgets["base_expression_id"] = self.expression_combo
        # work_combo は character_id の選択に使うため _widgets には含めない (直接アクセス)

        # Connect signals
        self.work_combo.currentIndexChanged.connect(self._on_work_changed)

        # Initialize character combo
        self._update_character_combo(current_work_id, current_character_id)

        # --- 不要なコード削除 ---
        # _populate_combos メソッドは _create_combo_box で代替
        # 初期値設定はウィジェット作成時に実施済み
        # button_box の作成と接続は基底クラス

    # --- Helper to get work_id (from ActorInspector) ---
    def _get_work_id_for_character(self, character_id: Optional[str]) -> Optional[str]:
        """Character ID から Work ID を取得します。"""
        if character_id:
            # 基底クラスから db_dict を参照
            character = self.db_dict.get("characters", {}).get(character_id)
            if character:
                return character.work_id
        return None

    # --- Slot for work_combo change (from ActorInspector) ---
    @Slot(int)
    def _on_work_changed(self, index: int):
        """Work コンボボックスの選択が変更されたときの処理。"""
        selected_work_id = self.work_combo.itemData(index)
        self._update_character_combo(selected_work_id, None)  # Character 選択はリセット

    # --- Method to update character_combo (from ActorInspector) ---
    def _update_character_combo(
        self, work_id: Optional[str], select_char_id: Optional[str]
    ):
        """Character コンボボックスの内容を更新し、指定IDを選択します。"""
        self.character_combo.blockSignals(True)
        self.character_combo.clear()
        self.character_combo.addItem("(未選択)", None)  # itemData に None
        ids = [None]

        filtered_chars = {}
        if work_id:
            # 基底クラスから db_dict を参照
            all_chars = self.db_dict.get("characters", {})
            filtered_chars = {
                cid: c
                for cid, c in all_chars.items()
                if getattr(c, "work_id", None) == work_id
            }

        sorted_chars = sorted(
            filtered_chars.values(), key=lambda c: getattr(c, "name", "").lower()
        )
        for char in sorted_chars:
            char_id = getattr(char, "id", None)
            char_name = getattr(char, "name", "Unknown")
            if char_id:
                self.character_combo.addItem(
                    f"{char_name} ({char_id})", char_id
                )  # itemData に ID
                ids.append(char_id)

        try:
            index = ids.index(select_char_id) if select_char_id in ids else 0
            self.character_combo.setCurrentIndex(index)
        except ValueError:
            self.character_combo.setCurrentIndex(0)  # 見つからなければ先頭 (未選択)

        self.character_combo.blockSignals(False)

    # --- accept を get_data に変更 ---
    def get_data(self) -> Optional[Actor]:
        name = self.name_edit.text().strip()
        prompt = self.prompt_edit.toPlainText().strip()
        character_id = self.character_combo.currentData()  # Can be None

        if not name or not prompt:
            QMessageBox.warning(
                self, "入力エラー", "名前 (Actor Name) と 基本プロンプト は必須です。"
            )
            return None
        # Character ID は必須ではないとする

        if self.initial_data:  # 更新
            updated_actor = self.initial_data
            self._update_object_from_widgets(updated_actor)
            # character_id もヘルパー内で更新される
            return updated_actor
        else:  # 新規作成
            tags_text = self.tags_edit.text()
            neg_prompt_text = self.negative_prompt_edit.toPlainText().strip()
            costume_id = self.costume_combo.currentData()
            pose_id = self.pose_combo.currentData()
            expression_id = self.expression_combo.currentData()

            new_actor = Actor(
                id=f"actor_{int(time.time())}",
                name=name,
                tags=[t.strip() for t in tags_text.split(",") if t.strip()],
                prompt=prompt,
                negative_prompt=neg_prompt_text,
                character_id=character_id or "",  # DB保存のために None を "" に
                base_costume_id=costume_id or "",
                base_pose_id=pose_id or "",
                base_expression_id=expression_id or "",
            )
            return new_actor

    # --- 元の get_data は削除 ---
