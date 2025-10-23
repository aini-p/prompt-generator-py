# src/panels/inspector_panel.py
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QPushButton,
    QGroupBox,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal, Slot
import traceback
from typing import Dict, Optional, Any, List, Type

# --- ★ インスペクタークラスをインポート ---
from ..inspectors.base_inspector import BaseInspector
from ..inspectors.work_inspector import WorkInspector
from ..inspectors.character_inspector import CharacterInspector
from ..inspectors.actor_inspector import ActorInspector
from ..inspectors.scene_inspector import SceneInspector
from ..inspectors.direction_inspector import DirectionInspector
from ..inspectors.simple_part_inspector import SimplePartInspector
from ..inspectors.sd_params_inspector import SDParamsInspector

# --- ここまで ---
from ..models import StableDiffusionParams, DatabaseKey


class InspectorPanel(QWidget):
    changesSaved = Signal(str, str, object)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._db_data_ref: Dict[str, Dict[str, Any]] = {}
        self._sd_params_ref: Optional[StableDiffusionParams] = None
        self._current_db_key: Optional[DatabaseKey] = None
        self._current_item_id: Optional[str] = None
        # --- ★ 現在アクティブな詳細インスペクターウィジェットへの参照 ---
        self._active_inspector: Optional[BaseInspector] = None
        # --- ここまで ---
        # self._widgets は BaseInspector に移動したので削除
        self._init_ui()

    def set_data_reference(
        self, db_data: Dict[str, Dict[str, Any]], sd_params: StableDiffusionParams
    ):
        self._db_data_ref = db_data
        self._sd_params_ref = sd_params

    def _init_ui(self):
        """UI要素を初期化します。"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.group_box = QGroupBox("Inspector")
        outer_layout = QVBoxLayout(self.group_box)
        self.scroll_area = QScrollArea()  # スクロールエリアを保持
        self.scroll_area.setWidgetResizable(True)
        # self.content_widget は不要、スクロールエリアに直接インスペクターウィジェットを設定する
        # self.form_layout_container は不要
        outer_layout.addWidget(self.scroll_area)
        main_layout.addWidget(self.group_box)

        self.clear_inspector()  # 初期状態はクリア

    def clear_inspector(self):
        """インスペクターの内容をクリアします。"""
        self._current_db_key = None
        self._current_item_id = None
        # --- ★ アクティブなインスペクターを削除 ---
        if self._active_inspector:
            self._active_inspector.deleteLater()
            self._active_inspector = None
        # --- ここまで ---

        self.group_box.setTitle("Inspector")
        # プレースホルダーラベルをスクロールエリアに直接設定
        placeholder_label = QLabel("Select an item from the list to inspect and edit.")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label.setWordWrap(True)
        self.scroll_area.setWidget(
            placeholder_label
        )  # スクロールエリアにウィジェットを設定

    def update_inspector(self, db_key: DatabaseKey, item_id: str):
        """指定されたアイテムでインスペクターを更新します。"""
        if self._current_db_key == db_key and self._current_item_id == item_id:
            return

        # --- ★ タイプに応じたインスペクタークラスを選択 ---
        InspectorClass: Optional[Type[BaseInspector]] = None
        if db_key == "sdParams":
            InspectorClass = SDParamsInspector
        elif db_key == "works":
            InspectorClass = WorkInspector
        elif db_key == "characters":
            InspectorClass = CharacterInspector
        elif db_key == "actors":
            InspectorClass = ActorInspector
        elif db_key == "scenes":
            InspectorClass = SceneInspector
        elif db_key == "directions":
            InspectorClass = DirectionInspector
        elif db_key in [
            "costumes",
            "poses",
            "expressions",
            "backgrounds",
            "lighting",
            "compositions",
        ]:
            InspectorClass = SimplePartInspector
        # --- ここまで ---

        if not InspectorClass:
            print(f"[DEBUG] No inspector class found for db_key: {db_key}")
            self.clear_inspector()
            error_label = QLabel(f"No editor available for type '{db_key}'.")
            self.scroll_area.setWidget(error_label)
            return

        # データを取得
        item_data: Optional[Any] = None
        item_name = item_id
        if db_key == "sdParams":
            item_data = self._sd_params_ref
            item_name = "Stable Diffusion Parameters"
        elif db_key in self._db_data_ref:
            item_data = self._db_data_ref.get(db_key, {}).get(item_id)
            if item_data:
                item_name = getattr(item_data, "title_jp", None) or getattr(
                    item_data, "name", item_id
                )

        if item_data is None:
            print(f"[DEBUG] Item data not found for {db_key} - {item_id}")
            self.clear_inspector()
            error_label = QLabel(f"Item '{item_id}' not found in '{db_key}'.")
            self.scroll_area.setWidget(error_label)
            return

        # --- ★ 新しいインスペクターを作成して表示 ---
        self.clear_inspector()  # 古いものをクリア
        self._current_db_key = db_key
        self._current_item_id = item_id

        try:
            # 新しいインスペクターインスタンスを作成
            self._active_inspector = InspectorClass(self._db_data_ref)
            self._active_inspector.set_item(item_data)  # データを設定してUIを構築

            # 保存ボタンを追加
            button_layout = QVBoxLayout()  # 保存ボタン用のレイアウト
            save_button = QPushButton("💾 Save Changes")
            save_button.clicked.connect(self._on_save_clicked)
            button_layout.addWidget(save_button)
            button_layout.addStretch()  # ボタンを上に寄せる

            # インスペクター本体と保存ボタンを保持するウィジェット
            container_widget = QWidget()
            container_layout = QVBoxLayout(container_widget)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.addWidget(self._active_inspector)  # 詳細インスペクター
            container_layout.addLayout(button_layout)  # 保存ボタン

            self.scroll_area.setWidget(container_widget)  # スクロールエリアに設定
            self.group_box.setTitle(f"Editing: {item_name} ({item_id})")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Inspector Error",
                f"Failed to create inspector for {item_name}: {e}",
            )
            print(f"[DEBUG] Error creating inspector: {e}")
            traceback.print_exc()
            self.clear_inspector()  # エラー時はクリア
        # --- ここまで ---

    @Slot()
    def _on_save_clicked(self):
        """保存ボタンがクリックされたときの処理。"""
        if self._active_inspector and self._current_db_key and self._current_item_id:
            updated_object = (
                self._active_inspector.get_data()
            )  # 詳細インスペクターから更新済みデータを取得
            if updated_object is not None:  # get_data でエラーがなければ
                self.changesSaved.emit(
                    self._current_db_key, self._current_item_id, updated_object
                )  # シグナル発行
        else:
            QMessageBox.warning(
                self, "Save Error", "No active inspector or item to save."
            )

    # --- ★ _add_..._fields, _create_combo_box は BaseInspector と詳細クラスに移動したので削除 ---
