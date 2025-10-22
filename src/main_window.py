# src/main_window.py
import sys
import os
import json
import time
import traceback
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QComboBox,
    QLabel,
    QScrollArea,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QFileDialog,
    QMessageBox,
    QSplitter,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QDialog,
    QLayout,
    QFrame,
)
from PySide6.QtCore import Qt, Slot
from . import database as db
from .models import (  # 必要なモデルと型をインポート
    Scene,
    Actor,
    Direction,
    PromptPartBase,
    StableDiffusionParams,
    Costume,
    Pose,
    Expression,
    Background,
    Lighting,
    Composition,
    SceneRole,
    RoleDirection,
    GeneratedPrompt,
    ImageGenerationTask,
    STORAGE_KEYS,
    DatabaseKey,
    FullDatabase,
)

# --- 分割したファイルをインポート ---
from .handlers.data_handler import DataHandler
from .panels.library_panel import LibraryPanel
from .panels.inspector_panel import InspectorPanel

# --- フォームは新規追加時にのみ使用 ---
from .widgets.add_actor_form import AddActorForm
from .widgets.add_scene_form import AddSceneForm
from .widgets.add_direction_form import AddDirectionForm
from .widgets.add_simple_part_form import AddSimplePartForm

# ------------------------------------
from .prompt_generator import generate_batch_prompts, create_image_generation_tasks
from .batch_runner import run_stable_diffusion
from typing import Dict, Optional, Any, List, Tuple, Literal, Union, TypeAlias, get_args

# (プレースホルダー定義は変更なし)
# ...


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Object-Oriented Prompt Builder")
        self.setGeometry(100, 100, 1400, 850)

        # --- データ関連 ---
        self.db_data: Dict[str, Dict[str, Any]] = {}
        self.sd_params: StableDiffusionParams = StableDiffusionParams()
        self.data_handler = DataHandler(self)  # DataHandler を初期化
        self.db_data, self.sd_params, initial_scene_id = (
            self.data_handler.load_all_data()
        )
        self.current_scene_id: Optional[str] = initial_scene_id  # 初期シーンIDを設定
        self.actor_assignments: Dict[str, str] = {}
        self.generated_prompts: List[GeneratedPrompt] = []

        # --- UI要素 ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # --- 左パネル ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(400)
        left_panel.setMaximumWidth(600)
        splitter.addWidget(left_panel)

        self._setup_data_management_ui(left_layout)  # Save/Load/Import/Export ボタン
        self._setup_prompt_generation_ui(
            left_layout
        )  # シーン選択、役割割り当て、生成ボタン

        # LibraryPanel をインスタンス化して配置
        self.library_panel = LibraryPanel()
        self.library_panel.set_data_reference(
            self.db_data, self.sd_params
        )  # データ参照を渡す
        left_layout.addWidget(self.library_panel)

        left_layout.addStretch()

        # --- 右パネル ---
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(right_splitter)

        # プロンプト表示エリア
        prompt_display_group = QGroupBox("Generated Prompts (Batch)")
        prompt_display_layout = QVBoxLayout(prompt_display_group)
        self.prompt_display_area = QTextEdit()
        self.prompt_display_area.setReadOnly(True)
        prompt_display_layout.addWidget(self.prompt_display_area)
        right_splitter.addWidget(prompt_display_group)

        # InspectorPanel をインスタンス化して配置
        self.inspector_panel = InspectorPanel()
        self.inspector_panel.set_data_reference(
            self.db_data, self.sd_params
        )  # データ参照を渡す
        right_splitter.addWidget(self.inspector_panel.group_box)  # QGroupBox を直接配置

        # スプリッターサイズ
        splitter.setSizes([450, 950])
        right_splitter.setSizes([400, 450])

        # --- シグナル接続 ---
        self._connect_signals()

        # 初期UI更新
        self.update_scene_combo()  # シーン選択コンボボックスの初期化
        self.build_role_assignment_ui()  # 役割割り当てUIの初期化
        # ライブラリリストとインスペクターはパネル内で初期化される

    def _connect_signals(self):
        """パネル間のシグナルを接続します。"""
        # LibraryPanel からのシグナル
        self.library_panel.itemSelected.connect(self.inspector_panel.update_inspector)
        self.library_panel.itemSelectionCleared.connect(
            self.inspector_panel.clear_inspector
        )
        self.library_panel.addNewItemClicked.connect(self._handle_add_new_item)
        self.library_panel.deleteItemClicked.connect(self._handle_delete_item)
        # InspectorPanel からのシグナル
        self.inspector_panel.changesSaved.connect(self._handle_inspector_save)

    # --- UIセットアップヘルパー ---
    def _setup_data_management_ui(self, parent_layout):
        """Save/Load/Import/Export ボタンのUIをセットアップします。"""
        group = QGroupBox("Data Management")
        layout = QHBoxLayout()
        group.setLayout(layout)
        save_btn = QPushButton("💾 Save to DB")
        # data_handler のメソッドを呼び出すように変更
        save_btn.clicked.connect(
            lambda: self.data_handler.save_all_data(self.db_data, self.sd_params)
        )
        export_btn = QPushButton("📤 Export JSON")
        export_btn.clicked.connect(
            lambda: self.data_handler.export_data(self.db_data, self.sd_params)
        )
        import_btn = QPushButton("📥 Import JSON")
        import_btn.clicked.connect(
            self._handle_import
        )  # インポートはデータ更新が伴うため別メソッド
        layout.addWidget(save_btn)
        layout.addWidget(export_btn)
        layout.addWidget(import_btn)
        parent_layout.addWidget(group)

    def _setup_prompt_generation_ui(self, parent_layout):
        """プロンプト生成関連のUI (シーン選択、役割割り当て、ボタン) をセットアップします。"""
        print("[DEBUG] _setup_prompt_generation_ui called.")
        group = QGroupBox("Prompt Generation")
        self.prompt_gen_layout = QVBoxLayout(group)  # レイアウトを直接グループに設定

        # シーン選択
        scene_layout = QHBoxLayout()
        scene_layout.addWidget(QLabel("1. Select Scene:"))
        self.scene_combo = QComboBox()
        # update_scene_combo は __init__ の最後で呼ばれる
        self.scene_combo.currentIndexChanged.connect(self.on_scene_changed)
        scene_layout.addWidget(self.scene_combo)
        self.prompt_gen_layout.addLayout(scene_layout)

        # 役割割り当て (動的UI用ウィジェット)
        self.role_assignment_widget = QWidget()
        self.role_assignment_widget.setObjectName("RoleAssignmentWidgetContainer")
        # build_role_assignment_ui は __init__ の最後で呼ばれる
        self.prompt_gen_layout.addWidget(self.role_assignment_widget)

        # ボタン
        generate_preview_btn = QPushButton("🔄 Generate Prompt Preview")
        generate_preview_btn.setStyleSheet("background-color: #ffc107;")
        generate_preview_btn.clicked.connect(self.generate_prompts)
        execute_btn = QPushButton("🚀 Execute Image Generation (Run Batch)")
        execute_btn.setStyleSheet("background-color: #28a745; color: white;")
        execute_btn.clicked.connect(self.execute_generation)
        self.prompt_gen_layout.addWidget(generate_preview_btn)
        self.prompt_gen_layout.addWidget(execute_btn)

        parent_layout.addWidget(group)
        print("[DEBUG] _setup_prompt_generation_ui complete.")

    # --- スロット (シグナルハンドラ) ---
    @Slot()
    def _handle_import(self):
        """インポートボタンが押されたときの処理。"""
        imported = self.data_handler.import_data()
        if imported:
            self.db_data, self.sd_params = imported
            # 新しいデータ参照を各パネルに設定
            self.library_panel.set_data_reference(self.db_data, self.sd_params)
            self.inspector_panel.set_data_reference(self.db_data, self.sd_params)
            # current_scene_id を再設定
            scenes_dict = self.db_data.get("scenes", {})
            if self.current_scene_id not in scenes_dict:
                self.current_scene_id = next(iter(scenes_dict), None)
            # UI全体更新
            self.update_ui_after_data_change()

    @Slot(str, str)  # DatabaseKey -> str に変更
    def _handle_add_new_item(
        self, db_key_str: str, modal_title: str
    ):  # db_key -> db_key_str に変更
        """LibraryPanel の Add New ボタンに対応するスロット。"""
        # 受け取った文字列が有効な DatabaseKey か確認
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in get_args(DatabaseKey) else None
        )  # get_args を使用
        if not db_key:
            print(
                f"[DEBUG] Error: _handle_add_new_item received invalid db_key: {db_key_str}"
            )
            return

        # modal_title から最後の 's' を取り除き、大文字に変換して modal_type を作成
        modal_type = (
            modal_title[:-1].upper()
            if modal_title.endswith("s")
            else modal_title.upper()
        )
        # 新規追加ダイアログを開く
        self.open_edit_dialog(modal_type, None)

    @Slot(str, str)  # DatabaseKey -> str に変更
    def _handle_delete_item(
        self, db_key_str: str, item_id: str
    ):  # db_key -> db_key_str に変更
        """LibraryPanel の Delete ボタンに対応するスロット。"""
        # 受け取った文字列が有効な DatabaseKey か確認
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in get_args(DatabaseKey) else None
        )  # get_args を使用
        if not db_key:
            print(
                f"[DEBUG] Error: _handle_delete_item received invalid db_key: {db_key_str}"
            )
            return
        # 削除処理を実行（確認ダイアログ表示含む）
        self.delete_item(db_key, item_id)

    # --- ★★★ 修正箇所 (Slot と 型ヒント) ★★★ ---
    @Slot(str, str, object)  # DatabaseKey -> str に変更
    def _handle_inspector_save(
        self, db_key_str: str, item_id: str, updated_object: Any
    ):  # db_key -> db_key_str
        """InspectorPanel で変更が保存されたときの処理。"""
        # 受け取った文字列が有効な DatabaseKey か確認
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in get_args(DatabaseKey) else None
        )
        if not db_key:
            print(
                f"[DEBUG] Error: _handle_inspector_save received invalid db_key: {db_key_str}"
            )
            return

        print(
            f"[DEBUG] Received changesSaved signal for {db_key} - {item_id}"
        )  # db_key を使用
        # --- ★★★ 修正ここまで ★★★ ---

        # メモリ上のデータを更新 (InspectorPanel内でも更新されているが念のため)
        if db_key == "sdParams":
            self.sd_params = updated_object  # 更新されたオブジェクトで置き換え
            # SD Params は直接DBに保存する (DataHandlerを使っても良い)
            db.save_sd_params(self.sd_params)
        elif db_key in self.db_data:
            self.db_data[db_key][item_id] = updated_object

        # UI更新 (リストの表示名が変わった場合など)
        self.library_panel.update_list()  # リストを再描画
        # 必要ならシーンコンボボックスも更新
        if db_key == "scenes":
            self.update_scene_combo()
        # 保存後にリストの選択状態を維持（update_listで選択が解除されるため再選択）
        self.library_panel.select_item_by_id(item_id)

    # --- UI更新メソッド ---
    def update_scene_combo(self):
        """シーン選択コンボボックスの内容を更新します。"""
        print("[DEBUG] update_scene_combo called.")
        current_scene_id_before_update = self.current_scene_id

        self.scene_combo.blockSignals(True)
        self.scene_combo.clear()
        scene_list = sorted(
            self.db_data.get("scenes", {}).values(), key=lambda s: s.name.lower()
        )
        print(f"[DEBUG] update_scene_combo: Found {len(scene_list)} scenes.")
        if not scene_list:
            self.scene_combo.addItem("No scenes available")
            self.scene_combo.setEnabled(False)
            print("[DEBUG] update_scene_combo: No scenes available.")
            self.current_scene_id = None
        else:
            scene_ids = [s.id for s in scene_list]
            self.scene_combo.addItems([s.name for s in scene_list])

            current_scene_index = 0
            target_id = (
                current_scene_id_before_update
                if current_scene_id_before_update in scene_ids
                else (scene_ids[0] if scene_ids else None)
            )

            if target_id and target_id in scene_ids:
                try:
                    current_scene_index = scene_ids.index(target_id)
                    self.current_scene_id = target_id
                except ValueError:
                    print(
                        f"[DEBUG] update_scene_combo: target_id '{target_id}' not found unexpectedly."
                    )
                    if scene_ids:
                        self.current_scene_id = scene_ids[0]
                        current_scene_index = 0
                    else:
                        self.current_scene_id = None
                        current_scene_index = -1
            elif scene_ids:
                self.current_scene_id = scene_ids[0]
                current_scene_index = 0
                print(
                    f"[DEBUG] update_scene_combo: set to first: {self.current_scene_id}"
                )
            else:
                self.current_scene_id = None
                current_scene_index = -1

            if self.current_scene_id is not None and current_scene_index >= 0:
                print(
                    f"[DEBUG] update_scene_combo: Setting index to {current_scene_index} (ID: {self.current_scene_id})"
                )
                self.scene_combo.setCurrentIndex(current_scene_index)
                self.scene_combo.setEnabled(True)
            else:
                self.scene_combo.setCurrentIndex(-1)
                self.scene_combo.setEnabled(False)

        self.scene_combo.blockSignals(False)
        # シーンが変わった可能性があるので役割割り当てUIも更新
        if current_scene_id_before_update != self.current_scene_id:
            self.build_role_assignment_ui()
            self.actor_assignments = {}  # シーンが変わったら割り当てリセット
            self.generated_prompts = []
            self.update_prompt_display()
        print("[DEBUG] update_scene_combo complete.")

    def build_role_assignment_ui(self):
        """役割割り当てUIを動的に構築します。"""
        print(
            f"[DEBUG] build_role_assignment_ui called for scene ID: {self.current_scene_id}"
        )

        layout = self.role_assignment_widget.layout()
        if layout is None:
            layout = QVBoxLayout(self.role_assignment_widget)
        else:
            # 既存ウィジェット削除
            item = layout.takeAt(0)
            while item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    layout_item = item.layout()
                    if layout_item is not None:
                        while layout_item.count():
                            inner_item = layout_item.takeAt(0)
                            inner_widget = inner_item.widget()
                            if inner_widget:
                                inner_widget.deleteLater()
                        layout_item.deleteLater()
                item = layout.takeAt(0)

        layout.addWidget(QLabel("2. Assign Actors to Roles:"))
        current_scene = (
            self.db_data.get("scenes", {}).get(self.current_scene_id)
            if self.current_scene_id
            else None
        )

        if not current_scene:
            layout.addWidget(QLabel("No scene selected."))
            layout.addStretch()
            return

        actor_list = list(self.db_data.get("actors", {}).values())
        actor_names = ["-- Select Actor --"] + [a.name for a in actor_list]
        actor_ids = [""] + [a.id for a in actor_list]

        if not current_scene.roles:
            layout.addWidget(QLabel("(このシーンには配役が定義されていません)"))

        for role in current_scene.roles:
            role_layout = QHBoxLayout()
            label_text = f"{role.name_in_scene} ([{role.id.upper()}])"
            role_layout.addWidget(QLabel(label_text))
            combo = QComboBox()
            combo.addItems(actor_names)
            assigned_actor_id = self.actor_assignments.get(role.id)
            current_index = 0
            if assigned_actor_id and assigned_actor_id in actor_ids:
                try:
                    current_index = actor_ids.index(assigned_actor_id)
                except ValueError:
                    pass
            combo.setCurrentIndex(current_index)
            combo.currentIndexChanged.connect(
                lambda index, r_id=role.id, ids=list(actor_ids): self.on_actor_assigned(
                    r_id, ids[index] if 0 <= index < len(ids) else ""
                )
            )
            role_layout.addWidget(combo)
            layout.addLayout(role_layout)

        layout.addStretch()
        print("[DEBUG] build_role_assignment_ui complete.")

    @Slot(int)
    def on_scene_changed(self, index):
        """シーン選択コンボボックスの選択が変更されたときの処理。"""
        print(f"[DEBUG] on_scene_changed called with index: {index}")
        scene_list = sorted(
            self.db_data.get("scenes", {}).values(), key=lambda s: s.name.lower()
        )
        if 0 <= index < len(scene_list):
            new_scene_id = scene_list[index].id
            print(f"[DEBUG] Selected scene ID from list: {new_scene_id}")
            if new_scene_id != self.current_scene_id:
                print(
                    f"[DEBUG] Scene ID changed! Old: {self.current_scene_id}, New: {new_scene_id}"
                )
                self.current_scene_id = new_scene_id
                self.actor_assignments = {}  # 割り当てリセット
                self.generated_prompts = []  # 生成プロンプトリセット
                self.build_role_assignment_ui()  # 役割割り当てUI更新
                self.update_prompt_display()  # プロンプト表示クリア
            else:
                print("[DEBUG] Scene index changed, but ID is the same.")
        else:
            print(f"[DEBUG] Invalid scene index selected: {index}")

    @Slot(str, str)
    def on_actor_assigned(self, role_id, actor_id):
        """役割割り当てコンボボックスの選択が変更されたときの処理。"""
        print(
            f"[DEBUG] on_actor_assigned called for Role ID: {role_id}, Actor ID: '{actor_id}'"
        )
        if actor_id:
            self.actor_assignments[role_id] = actor_id
        else:
            if role_id in self.actor_assignments:
                del self.actor_assignments[role_id]
        print(f"[DEBUG] Current assignments: {self.actor_assignments}")
        self.generated_prompts = []  # 割り当てが変わったらプロンプトはリセット
        self.update_prompt_display()

    @Slot()
    def generate_prompts(self):
        """プロンプト生成ボタンがクリックされたときの処理。"""
        if not self.current_scene_id:
            QMessageBox.warning(self, "Generate", "Please select a scene first.")
            return
        current_scene = self.db_data["scenes"].get(self.current_scene_id)
        if not current_scene:
            QMessageBox.warning(self, "Generate", "Selected scene data not found.")
            return
        missing_roles = [
            r.name_in_scene
            for r in current_scene.roles
            if r.id not in self.actor_assignments
        ]
        if missing_roles:
            QMessageBox.warning(
                self,
                "Generate",
                f"Assign actors to all roles: {', '.join(missing_roles)}",
            )
            return
        try:
            self.generated_prompts = generate_batch_prompts(
                self.current_scene_id, self.actor_assignments, self.db_data
            )
            self.update_prompt_display()
        except Exception as e:
            QMessageBox.critical(
                self, "Generation Error", f"Error generating prompts: {e}"
            )
            print(f"[DEBUG] Prompt generation error: {e}")
            traceback.print_exc()

    @Slot()
    def execute_generation(self):
        """画像生成実行ボタンがクリックされたときの処理。"""
        if not self.generated_prompts:
            QMessageBox.warning(
                self, "Execute", "Please generate prompt previews first."
            )
            return
        current_scene = self.db_data["scenes"].get(self.current_scene_id)
        if not current_scene:
            QMessageBox.warning(
                self, "Execute", "Cannot execute without a selected scene."
            )
            return
        try:
            tasks = create_image_generation_tasks(
                self.generated_prompts, self.sd_params, current_scene
            )
            if not tasks:
                QMessageBox.warning(self, "Execute", "No tasks were generated.")
                return
            success, message = run_stable_diffusion(tasks)
            if success:
                QMessageBox.information(self, "Execute", message)
            else:
                QMessageBox.critical(self, "Execution Error", message)
        except Exception as e:
            QMessageBox.critical(
                self, "Execution Error", f"An unexpected error occurred: {e}"
            )
            print(f"[DEBUG] Execution error: {e}")
            traceback.print_exc()

    def update_prompt_display(self):
        """プロンプト表示エリアを更新します。"""
        print("[DEBUG] update_prompt_display called.")
        if not self.generated_prompts:
            self.prompt_display_area.setPlainText("Press 'Generate Prompt Preview'.")
            print("[DEBUG] No prompts to display.")
            return
        display_text = ""
        for p in self.generated_prompts:
            display_text += f"--- {p.name} ---\nPositive:\n{p.positive}\n\nNegative:\n{p.negative}\n------------------------------------\n\n"
        self.prompt_display_area.setPlainText(display_text)
        print("[DEBUG] Prompt display area updated.")

    def update_ui_after_data_change(self):
        """データ変更（インポート、新規追加、削除など）後にUI全体を更新します。"""
        print("[DEBUG] update_ui_after_data_change called.")
        # リストの現在の選択状態を保持（試行）
        current_list_selection_id = (
            self.library_panel.library_list_widget.currentItem().data(
                Qt.ItemDataRole.UserRole
            )
            if self.library_panel.library_list_widget.currentItem()
            else None
        )

        self.update_scene_combo()  # シーンコンボ更新
        self.library_panel.update_list()  # ライブラリリスト更新

        # リスト選択状態の復元 (update_list で選択がクリアされるため)
        if current_list_selection_id:
            self.library_panel.select_item_by_id(current_list_selection_id)
            # select_item_by_id の後、インスペクターを手動更新
            self.inspector_panel.update_inspector(
                self.library_panel._current_db_key, current_list_selection_id
            )
        else:
            self.inspector_panel.clear_inspector()

        self.build_role_assignment_ui()  # 役割割り当てUI更新
        # 必要ならプロンプト表示もクリア
        # self.generated_prompts = []
        # self.update_prompt_display()

        print("[DEBUG] update_ui_after_data_change complete.")

    def open_edit_dialog(self, modal_type: str, item_data: Optional[Any]):
        """新規アイテム追加用の編集ダイアログを開きます。"""
        # (この関数の中身は変更なし、主に新規追加用)
        dialog: Optional[QDialog] = None
        db_key_map = {
            "ACTOR": "actors",
            "SCENE": "scenes",
            "DIRECTION": "directions",
            "COSTUME": "costumes",
            "POSE": "poses",
            "EXPRESSION": "expressions",
            "BACKGROUND": "backgrounds",
            "LIGHTING": "lighting",
            "COMPOSITION": "compositions",
        }
        db_key = db_key_map.get(modal_type)
        if not db_key:
            QMessageBox.warning(
                self, "Error", f"Invalid modal type for dialog: {modal_type}"
            )
            return

        print(
            f"[DEBUG] open_edit_dialog called for type: {modal_type}, data: {'Exists' if item_data else 'None'}"
        )
        try:
            # フォームクラスのインスタンス化
            FormClass = None
            if modal_type == "ACTOR":
                FormClass = AddActorForm
            elif modal_type == "SCENE":
                FormClass = AddSceneForm
            elif modal_type == "DIRECTION":
                FormClass = AddDirectionForm
            elif modal_type in [
                "COSTUME",
                "POSE",
                "EXPRESSION",
                "BACKGROUND",
                "LIGHTING",
                "COMPOSITION",
            ]:
                FormClass = AddSimplePartForm

            if FormClass:
                # AddSimplePartForm は引数が異なるので分岐
                if FormClass == AddSimplePartForm:
                    dialog = FormClass(
                        item_data, modal_type, self
                    )  # 第2引数は modal_type 文字列
                else:
                    dialog = FormClass(
                        item_data, self.db_data, self
                    )  # 他は db_data を渡す
                print(f"[DEBUG] Dialog instance created: {dialog}")
            else:
                QMessageBox.warning(
                    self,
                    "Not Implemented",
                    f"Dialog for '{modal_type}' not implemented.",
                )
                return

        except Exception as e:
            QMessageBox.critical(
                self, "Dialog Error", f"Failed to create dialog for {modal_type}: {e}"
            )
            print(f"[DEBUG] Error creating dialog: {e}")
            traceback.print_exc()
            return

        if dialog:
            result = dialog.exec()
            if result == QDialog.DialogCode.Accepted:
                if hasattr(dialog, "get_data") and callable(dialog.get_data):
                    saved_data = dialog.get_data()
                    if saved_data and db_key in self.db_data:
                        print(
                            f"[DEBUG] Dialog returned data: {saved_data.id}. Adding to db_data."
                        )
                        # 新規追加データをメモリに追加
                        self.db_data[db_key][saved_data.id] = saved_data
                        # UI全体を更新してリストに反映
                        self.update_ui_after_data_change()
                        # 追加したアイテムを選択状態にする
                        self.library_panel.select_item_by_id(saved_data.id)
                        self.inspector_panel.update_inspector(db_key, saved_data.id)
                    # (エラー処理などは省略)
            else:
                print("[DEBUG] Dialog cancelled or closed.")

    def delete_item(self, db_key: DatabaseKey, item_id: str):
        """指定されたアイテムを削除します（確認含む）。"""
        item_to_delete = self.db_data.get(db_key, {}).get(item_id)
        item_name = (
            getattr(item_to_delete, "name", item_id) if item_to_delete else item_id
        )
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"'{item_name}' ({item_id}) を削除しますか？\nこの操作はメモリ上のデータのみに影響し、元に戻せません。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            # DataHandler を使って削除
            deleted = self.data_handler.handle_delete_part(
                db_key, item_id, self.db_data
            )
            if deleted:
                print(f"[DEBUG] Item {item_id} deleted successfully.")
                # MainWindow 側の関連データ更新
                if db_key == "actors":
                    # 割り当てから削除
                    self.actor_assignments = {
                        k: v for k, v in self.actor_assignments.items() if v != item_id
                    }
                if db_key == "scenes" and item_id == self.current_scene_id:
                    # 現在のシーンが削除されたらリセット
                    self.current_scene_id = next(
                        iter(self.db_data.get("scenes", {})), None
                    )
                # UI全体更新
                self.update_ui_after_data_change()
            else:
                QMessageBox.warning(
                    self, "Delete Error", f"Failed to delete item '{item_id}'."
                )
        else:
            print(f"[DEBUG] Deletion cancelled by user for {item_id}.")


# --- Style Definitions (変更なし) ---
# ... (以前のスタイル定義) ...
buttonStyle: Dict[str, Any] = {
    "padding": "10px",
    "color": "white",
    "border": "none",
    "cursor": "pointer",
    "fontSize": "14px",
    "borderRadius": "4px",
    "lineHeight": "1.5",
}


def buttonGridStyle(columns: int) -> Dict[str, Any]:
    return {
        "display": "grid",
        "gridTemplateColumns": f"repeat({columns}, 1fr)",
        "gap": "10px",
    }


sectionStyle: Dict[str, Any] = {
    "marginBottom": "15px",
    "paddingBottom": "15px",
    "borderBottom": "2px solid #eee",
}
tinyButtonStyle: Dict[str, Any] = {
    "fontSize": "10px",
    "padding": "2px 4px",
    "margin": "0 2px",
}
libraryListStyle: Dict[str, Any] = {
    "maxHeight": "150px",
    "overflowY": "auto",
    "border": "1px solid #eee",
    "marginTop": "5px",
    "padding": "5px",
}
libraryItemStyle: Dict[str, Any] = {
    "display": "flex",
    "justifyContent": "space-between",
    "padding": "3px 0",
    "borderBottom": "1px solid #f9f9f9",
}
promptAreaStyle: Dict[str, Any] = {
    "width": "95%",
    "fontSize": "0.9em",
    "padding": "4px",
    "margin": "2px 0 5px 0",
    "display": "block",
    "boxSizing": "border-box",
}
sdParamRowStyle: Dict[str, Any] = {
    "display": "flex",
    "justifyContent": "space-between",
    "alignItems": "center",
    "margin": "3px 0",
}
sdInputStyle: Dict[str, Any] = {"width": "60%"}
directionItemStyle: Dict[str, Any] = {
    "display": "flex",
    "justifyContent": "space-between",
    "padding": "2px 4px",
    "fontSize": "0.9em",
    "backgroundColor": "#f9f9f9",
    "margin": "2px 0",
    "borderRadius": "3px",
}

# (メイン実行部分は main.py にある)
