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
        self.form_layout = self.setup_form_layout()  # 基底クラスのヘルパーを呼び出す
        if not self.form_layout:
            return  # エラー処理 (念のため)
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

        work_ref_widget = self._create_reference_editor_widget(
            field_name="work_id",  # ★ work_id を指定
            current_id=current_work_id,
            reference_db_key="works",
            reference_modal_type="WORK",
            allow_none=True,  # ★ allow_none に修正
            none_text="(未割り当て)",
            display_attr="title_jp",
        )
        self.character_combo = QComboBox()  # Characterコンボをインスタンス変数に

        # --- Base selections ---
        costume_ref_widget = self._create_reference_editor_widget(
            field_name="base_costume_id",
            current_id=getattr(self.initial_data, "base_costume_id", None),
            reference_db_key="costumes",
            reference_modal_type="COSTUME",  # MainWindow のマッピングキー
            allow_none=True,
        )
        pose_ref_widget = self._create_reference_editor_widget(
            field_name="base_pose_id",
            current_id=getattr(self.initial_data, "base_pose_id", None),
            reference_db_key="poses",
            reference_modal_type="POSE",
            allow_none=True,
        )
        expression_ref_widget = self._create_reference_editor_widget(
            field_name="base_expression_id",
            current_id=getattr(self.initial_data, "base_expression_id", None),
            reference_db_key="expressions",
            reference_modal_type="EXPRESSION",
            allow_none=True,
        )

        # Layout (using base class's form_layout)
        self.form_layout.addRow("名前:", self.name_edit)
        self.form_layout.addRow("タグ (カンマ区切り):", self.tags_edit)
        self.form_layout.addRow("登場作品 (Work):", work_ref_widget)
        self.form_layout.addRow("キャラクター (Character):", self.character_combo)
        self.form_layout.addRow("基本プロンプト (Positive):", self.prompt_edit)
        self.form_layout.addRow(
            "基本ネガティブプロンプト (Negative):", self.negative_prompt_edit
        )
        self.form_layout.addRow("基本衣装:", costume_ref_widget)
        self.form_layout.addRow("基本ポーズ:", pose_ref_widget)
        self.form_layout.addRow("基本表情:", expression_ref_widget)
        # _widgets への登録
        self._widgets["name"] = self.name_edit
        self._widgets["tags"] = self.tags_edit
        self._widgets["prompt"] = self.prompt_edit
        self._widgets["negative_prompt"] = self.negative_prompt_edit
        self._widgets["character_id"] = (
            self.character_combo
        )  # character_id は character_combo の currentData

        work_combo_widget = self._reference_widgets.get("work_id", {}).get("combo")
        if isinstance(work_combo_widget, QComboBox):
            work_combo_widget.currentIndexChanged.connect(self._on_work_changed)

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
        # --- ▼▼▼ _reference_widgets からコンボボックスを取得 ▼▼▼ ---
        work_combo_widget = self._reference_widgets.get("work_id", {}).get("combo")
        selected_work_id = None
        if isinstance(work_combo_widget, QComboBox):
            selected_work_id = work_combo_widget.itemData(
                index
            )  # itemData から ID を取得
        # --- ▲▲▲ 修正ここまで ▲▲▲ ---
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
        try:
            name = self._widgets["name"].text().strip()
            if not name:
                QMessageBox.warning(self, "入力エラー", "名前は必須です。")
                return None

            # --- ▼▼▼ プルダウンリストから最新の ID を取得 ▼▼▼ ---
            character_id = self._get_widget_value("character_id")
            base_costume_id = self._get_widget_value("base_costume_id")
            base_pose_id = self._get_widget_value("base_pose_id")
            base_expression_id = self._get_widget_value("base_expression_id")
            # --- ▲▲▲ 修正 ▲▲▲ ---

            if self.initial_data:
                updated_actor = self.initial_data
                # _update_object_from_widgets は name, tags, prompt, negative_prompt を更新
                if not self._update_object_from_widgets(updated_actor):
                    print("[ERROR] _update_object_from_widgets failed.")
                    return None
                # --- ▼▼▼ 取得したIDをオブジェクトに設定 ▼▼▼ ---
                updated_actor.character_id = character_id or ""
                updated_actor.base_costume_id = base_costume_id or ""
                updated_actor.base_pose_id = base_pose_id or ""
                updated_actor.base_expression_id = base_expression_id or ""
                # --- ▲▲▲ 修正 ▲▲▲ ---
                print(f"[DEBUG] Returning updated actor: {updated_actor}")
                return updated_actor
            else:
                tags_text = self._widgets["tags"].text()
                prompt_text = self._widgets["prompt"].toPlainText().strip()
                neg_prompt_text = self._widgets["negative_prompt"].toPlainText().strip()
                new_actor = Actor(
                    id=f"actor_{int(time.time())}",
                    name=name,
                    tags=[t.strip() for t in tags_text.split(",") if t.strip()],
                    prompt=prompt_text,
                    negative_prompt=neg_prompt_text,
                    # --- ▼▼▼ 取得したIDをオブジェクトに設定 ▼▼▼ ---
                    character_id=character_id or "",
                    base_costume_id=base_costume_id or "",
                    base_pose_id=base_pose_id or "",
                    base_expression_id=base_expression_id or "",
                    # --- ▲▲▲ 修正 ▲▲▲ ---
                )
                print(f"[DEBUG] Returning new actor: {new_actor}")
                return new_actor
        except Exception as e:
            print(f"[ERROR] Exception in ActorEditorDialog.get_data: {e}")
            QMessageBox.critical(
                self, "Error", f"An error occurred while getting actor data: {e}"
            )
            return None
