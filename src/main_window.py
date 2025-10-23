# src/main_window.py
import sys, os, json, time, traceback
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
from .models import (
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
    Work,
    Character,  # Work, Character もインポート
)
from typing import Dict, Optional, Any, List, Tuple, Literal, Union, TypeAlias, get_args

# --- パネルとハンドラをインポート ---
from .handlers.data_handler import DataHandler
from .panels.library_panel import LibraryPanel
from .panels.inspector_panel import InspectorPanel
from .panels.prompt_panel import PromptPanel
from .panels.data_management_panel import DataManagementPanel

# --- フォームは新規追加時にのみ使用 ---
from .widgets.add_actor_form import AddActorForm
from .widgets.add_scene_form import AddSceneForm
from .widgets.add_direction_form import AddDirectionForm
from .widgets.add_simple_part_form import AddSimplePartForm
from .widgets.add_work_form import AddWorkForm
from .widgets.add_character_form import AddCharacterForm

# ------------------------------------
from .prompt_generator import generate_batch_prompts, create_image_generation_tasks
from .batch_runner import run_stable_diffusion

# (プレースホルダー定義は変更なし)
# ...


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Object-Oriented Prompt Builder")
        self.setGeometry(100, 100, 1400, 850)

        self.form_mapping = {
            "WORK": (AddWorkForm, "works"),
            "CHARACTER": (AddCharacterForm, "characters"),
            "ACTOR": (AddActorForm, "actors"),
            "SCENE": (AddSceneForm, "scenes"),
            "DIRECTION": (AddDirectionForm, "directions"),
            "COSTUME": (AddSimplePartForm, "costumes"),
            "POSE": (AddSimplePartForm, "poses"),
            "EXPRESSION": (AddSimplePartForm, "expressions"),
            "BACKGROUND": (AddSimplePartForm, "backgrounds"),
            "LIGHTING": (AddSimplePartForm, "lighting"),
            "COMPOSITION": (AddSimplePartForm, "compositions"),
        }

        # --- データ関連 ---
        self.db_data: Dict[str, Dict[str, Any]] = {}
        self.sd_params: StableDiffusionParams = StableDiffusionParams()
        self.data_handler = DataHandler(self)
        self.db_data, self.sd_params, initial_scene_id = (
            self.data_handler.load_all_data()
        )
        self.current_scene_id: Optional[str] = initial_scene_id
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

        # Data Management Panel
        self.data_management_panel = DataManagementPanel()
        left_layout.addWidget(self.data_management_panel)

        # Prompt Panel
        self.prompt_panel = PromptPanel()
        self.prompt_panel.set_data_reference(self.db_data)
        left_layout.addWidget(self.prompt_panel)

        # Library Panel
        self.library_panel = LibraryPanel()
        self.library_panel.set_data_reference(self.db_data, self.sd_params)
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

        # Inspector Panel
        self.inspector_panel = InspectorPanel()
        self.inspector_panel.set_data_reference(self.db_data, self.sd_params)
        right_splitter.addWidget(self.inspector_panel.group_box)  # GroupBox を直接配置

        # スプリッターサイズ
        splitter.setSizes([450, 950])
        right_splitter.setSizes([400, 450])

        # --- シグナル接続 ---
        self._connect_signals()

        # --- 初期UI状態設定 ---
        # PromptPanel の初期シーンを設定 (これにより関連UIも更新される)
        self.prompt_panel.set_current_scene(self.current_scene_id)
        # LibraryPanel は内部で初期リスト表示を行う
        # InspectorPanel は内部で初期クリア状態

    def _connect_signals(self):
        """パネル間のシグナルを接続します。"""
        # Data Management Panel
        self.data_management_panel.saveClicked.connect(
            lambda: self.data_handler.save_all_data(self.db_data, self.sd_params)
        )
        self.data_management_panel.exportClicked.connect(
            lambda: self.data_handler.export_data(self.db_data, self.sd_params)
        )
        self.data_management_panel.importClicked.connect(self._handle_import)

        # Prompt Panel
        self.prompt_panel.generatePromptsClicked.connect(self.generate_prompts)
        self.prompt_panel.executeGenerationClicked.connect(self.execute_generation)
        self.prompt_panel.sceneChanged.connect(self._handle_scene_change)
        self.prompt_panel.assignmentChanged.connect(self._handle_assignment_change)

        # Library Panel
        self.library_panel.itemSelected.connect(self.inspector_panel.update_inspector)
        self.library_panel.itemSelectionCleared.connect(
            self.inspector_panel.clear_inspector
        )
        self.library_panel.addNewItemClicked.connect(self._handle_add_new_item)
        self.library_panel.deleteItemClicked.connect(self._handle_delete_item)
        # self.library_panel.libraryTypeChanged.connect(...) # 必要なら接続

        # Inspector Panel
        self.inspector_panel.changesSaved.connect(self._handle_inspector_save)

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
            self.prompt_panel.set_data_reference(
                self.db_data, self.actor_assignments
            )  # PromptPanel も更新
            # current_scene_id を再設定
            scenes_dict = self.db_data.get("scenes", {})
            new_scene_id = next(iter(scenes_dict), None)
            if self.current_scene_id not in scenes_dict:
                self.current_scene_id = new_scene_id

            # UI全体更新
            self.update_ui_after_data_change()
            # インポート後に最初のシーンを選択状態にする
            self.prompt_panel.set_current_scene(self.current_scene_id)

    @Slot(str, str)
    def _handle_add_new_item(self, db_key_str: str, modal_title: str):
        """LibraryPanel の Add New ボタンに対応するスロット。"""
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in get_args(DatabaseKey) else None
        )
        if not db_key:
            return
        modal_type = ""
        if db_key == "scenes":
            modal_type = "SCENE"
        elif db_key == "actors":
            modal_type = "ACTOR"
        elif db_key == "works":
            modal_type = "WORK"
        elif db_key == "characters":
            modal_type = "CHARACTER"
        elif db_key == "directions":
            modal_type = "DIRECTION"
        elif db_key == "costumes":
            modal_type = "COSTUME"
        elif db_key == "poses":
            modal_type = "POSE"
        elif db_key == "expressions":
            modal_type = "EXPRESSION"
        elif db_key == "backgrounds":
            modal_type = "BACKGROUND"
        elif db_key == "lighting":
            modal_type = "LIGHTING"
        elif db_key == "compositions":
            modal_type = "COMPOSITION"

        if modal_type:
            print(f"[DEBUG] Add New button clicked for type: {db_key} -> {modal_type}")
            self.open_edit_dialog(modal_type, None)
        else:
            print(f"[DEBUG] Error: Cannot determine modal_type for db_key '{db_key}'")

    @Slot(str, str)
    def _handle_delete_item(self, db_key_str: str, item_id: str):
        """LibraryPanel の Delete ボタンに対応するスロット。"""
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in get_args(DatabaseKey) else None
        )
        if not db_key:
            return
        self.delete_item(db_key, item_id)

    @Slot(str, str, object)
    def _handle_inspector_save(
        self, db_key_str: str, item_id: str, updated_object: Any
    ):
        """InspectorPanel で変更が保存されたときの処理。"""
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in get_args(DatabaseKey) else None
        )
        if not db_key:
            return

        print(f"[DEBUG] Received changesSaved signal for {db_key} - {item_id}")
        # メモリ上のデータを更新
        if db_key == "sdParams":
            self.sd_params = updated_object
            # self.data_handler.save_sd_params(self.sd_params) # DataHandler経由に変更も可
        elif db_key in self.db_data:
            self.db_data[db_key][item_id] = updated_object

        # UI更新
        self.library_panel.update_list()
        # シーン名、Work名、Character名が変更されたら関連コンボボックス更新
        if db_key in ["scenes", "works", "characters"]:
            self.prompt_panel.update_scene_combo()  # シーンコンボ更新
            # 必要なら ActorインスペクターのWork/Characterコンボも更新？ (InspectorPanel内で行うべきか)
        # 保存後にリストの選択状態を維持
        self.library_panel.select_item_by_id(item_id)
        # 役割割り当ても更新（ActorやSceneが変更された場合）
        if db_key in ["actors", "scenes"]:
            self.prompt_panel.build_role_assignment_ui()

    @Slot(str)
    def _handle_scene_change(self, new_scene_id: str):
        """PromptPanel からシーン変更の通知を受け取るスロット。"""
        print(f"[DEBUG] MainWindow received sceneChanged signal: {new_scene_id}")
        current_scene_id_before = self.current_scene_id
        self.current_scene_id = new_scene_id if new_scene_id else None
        # ★ シーンが変わった場合のみプロンプトリセット (actor_assignments のリセットは不要)
        if current_scene_id_before != self.current_scene_id:
            # self.actor_assignments = {} # ← 不要になったので削除
            self.generated_prompts = []
            self.update_prompt_display()
            # PromptPanel 側で build_role_assignment_ui が呼ばれる

    @Slot(dict)
    def _handle_assignment_change(self, new_assignments: dict):
        """PromptPanel から割り当て変更の通知を受け取るスロット。"""
        print(f"[DEBUG] MainWindow received assignmentChanged: {new_assignments}")
        self.actor_assignments = new_assignments.copy()  # 受け取った辞書のコピーで更新
        # 割り当てが変わったら生成済みプロンプトはリセット
        self.generated_prompts = []
        self.update_prompt_display()

    # --- コアロジックメソッド ---
    @Slot()
    def generate_prompts(self):
        """プロンプト生成を実行します (PromptPanelから呼ばれる)。"""
        if not self.current_scene_id:
            QMessageBox.warning(self, "Generate", "Please select a scene first.")
            return
        current_scene = self.db_data["scenes"].get(self.current_scene_id)
        if not current_scene:
            QMessageBox.warning(self, "Generate", "Selected scene data not found.")
            return
        print(f"[DEBUG] generate_prompts: Checking scene ID: {self.current_scene_id}")
        print(
            f"[DEBUG] generate_prompts: Expected Role IDs: {[r.id for r in current_scene.roles]}"
        )
        print(
            f"[DEBUG] generate_prompts: Current assignments: {self.actor_assignments}"
        )
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
            # --- ★ generate_batch_prompts に渡す FullDatabase オブジェクトを作成 ---
            full_db = FullDatabase(
                works=self.db_data.get("works", {}),
                characters=self.db_data.get("characters", {}),
                actors=self.db_data.get("actors", {}),
                costumes=self.db_data.get("costumes", {}),
                poses=self.db_data.get("poses", {}),
                expressions=self.db_data.get("expressions", {}),
                directions=self.db_data.get("directions", {}),
                backgrounds=self.db_data.get("backgrounds", {}),
                lighting=self.db_data.get("lighting", {}),
                compositions=self.db_data.get("compositions", {}),
                scenes=self.db_data.get("scenes", {}),
                sdParams=self.sd_params,
            )
            # --- ★ 修正ここまで ---
            # self.generated_prompts = generate_batch_prompts(
            #     self.current_scene_id, self.actor_assignments, self.db_data # 古い呼び出し方
            # )
            self.generated_prompts = generate_batch_prompts(
                self.current_scene_id,
                self.actor_assignments,
                full_db,  # ★ 修正後
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
        """画像生成を実行します (PromptPanelから呼ばれる)。"""
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
            # firstActorInfo の表示（オプション）
            actor_info_str = ""
            if p.firstActorInfo:
                char = p.firstActorInfo.get("character")
                work = p.firstActorInfo.get("work")
                if char and work:
                    actor_info_str = f" ({getattr(work, 'title_jp', '')} - {getattr(char, 'name', '')})"

            display_text += f"--- {p.name}{actor_info_str} ---\nPositive:\n{p.positive}\n\nNegative:\n{p.negative}\n------------------------------------\n\n"
        self.prompt_display_area.setPlainText(display_text)
        print("[DEBUG] Prompt display area updated.")

    def update_ui_after_data_change(self):
        """データ変更（インポート、新規追加、削除など）後にUI全体を更新します。"""
        print("[DEBUG] update_ui_after_data_change called.")
        # リストの現在の選択状態を保持
        current_list_selection_id = None
        if self.library_panel.library_list_widget.currentItem():
            current_list_selection_id = (
                self.library_panel.library_list_widget.currentItem().data(
                    Qt.ItemDataRole.UserRole
                )
            )
        current_type_index = self.library_panel.library_type_combo.currentIndex()

        self.prompt_panel.set_data_reference(self.db_data)
        # update_scene_combo は set_data_reference 内で呼ばれる場合があるので確認
        # self.prompt_panel.update_scene_combo() # 必要に応じて呼び出し
        self.library_panel.update_list()

        # リストタイプと選択状態を復元
        if current_type_index >= 0:
            self.library_panel.library_type_combo.blockSignals(True)
            self.library_panel.library_type_combo.setCurrentIndex(current_type_index)
            self.library_panel.library_type_combo.blockSignals(False)
            # update_list が呼ばれるので二重更新に注意が必要な場合がある

        if current_list_selection_id:
            self.library_panel.select_item_by_id(current_list_selection_id)
            # 再選択後にインスペクターを更新
            if self.library_panel._current_db_key:  # タイプが確定していることを確認
                self.inspector_panel.update_inspector(
                    self.library_panel._current_db_key, current_list_selection_id
                )
        else:
            self.inspector_panel.clear_inspector()

        # プロンプト表示はシーンが変わった場合のみリセット
        # (on_scene_changed / _handle_scene_change で対応)

        print("[DEBUG] update_ui_after_data_change complete.")

    def open_edit_dialog(self, modal_type: str, item_data: Optional[Any]):
        """新規アイテム追加用の編集ダイアログを開きます。"""
        # マッピングからフォームクラスと db_key を取得
        form_info = self.form_mapping.get(modal_type)
        if not form_info:
            QMessageBox.warning(
                self, "Error", f"Invalid modal type for dialog: {modal_type}"
            )
            return

        FormClass, db_key_str = form_info
        # db_key_str を DatabaseKey に変換 (バリデーション)
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in get_args(DatabaseKey) else None
        )
        if not db_key:
            QMessageBox.critical(
                self,
                "Error",
                f"Internal error: Invalid db_key '{db_key_str}' mapped for type '{modal_type}'",
            )
            return

        print(
            f"[DEBUG] open_edit_dialog called for type: {modal_type}, data: {'Exists' if item_data else 'None'}"
        )
        dialog: Optional[QDialog] = None

        try:
            # マッピングに基づいてフォームをインスタンス化
            if FormClass in [
                AddWorkForm,
                AddCharacterForm,
                AddActorForm,
                AddSceneForm,
                AddDirectionForm,
            ]:
                # これらのフォームは db_dict (全データ) を必要とする
                dialog = FormClass(item_data, self.db_data, self)
            elif FormClass == AddSimplePartForm:
                # AddSimplePartForm は modal_type 文字列を必要とする
                dialog = FormClass(item_data, modal_type, self)
            else:
                QMessageBox.warning(
                    self,
                    "Not Implemented",
                    f"Dialog logic for '{modal_type}' needs implementation.",
                )
                return
            print(f"[DEBUG] Dialog instance created: {dialog}")

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
                    saved_data = (
                        dialog.get_data()
                    )  # 各フォームは正しいデータ型を返すように実装されている想定

                    if saved_data and db_key in self.db_data:  # db_key は有効なはず
                        print(
                            f"[DEBUG] Dialog returned data: {saved_data.id} of type {type(saved_data).__name__}. Adding to db_data."
                        )
                        # 1. メモリに追加
                        self.db_data[db_key][saved_data.id] = saved_data
                        # 2. DBに即時保存
                        try:
                            self.data_handler.save_single_item(db_key, saved_data)
                        except Exception as db_save_e:
                            print(
                                f"[ERROR] Failed to immediately save new item {saved_data.id} to DB: {db_save_e}"
                            )
                            QMessageBox.warning(
                                self,
                                "DB Save Error",
                                f"Failed to save the new item {getattr(saved_data, 'name', saved_data.id)} to the database immediately. Please use 'Save to DB' later.",
                            )
                        # 3. UI更新
                        self.update_ui_after_data_change()
                        self.library_panel.select_item_by_id(saved_data.id)
                    else:
                        print(
                            "[DEBUG] Dialog accepted but returned no valid data or db_key mismatch."
                        )
            else:
                print("[DEBUG] Dialog cancelled or closed.")

    def delete_item(self, db_key: DatabaseKey, item_id: str):
        """指定されたアイテムを削除します（確認含む）。"""
        item_to_delete = self.db_data.get(db_key, {}).get(item_id)
        # Work の場合は title_jp を表示名に使う
        item_name = getattr(item_to_delete, "title_jp", None) or getattr(
            item_to_delete, "name", item_id
        )
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"'{item_name}' ({item_id}) を削除しますか？\nこの操作はメモリ上のデータのみに影響し、元に戻せません。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            deleted = self.data_handler.handle_delete_part(
                db_key, item_id, self.db_data
            )
            if deleted:
                print(f"[DEBUG] Item {item_id} deleted successfully.")
                # MainWindow 側の関連データ更新
                if db_key == "actors":
                    self.actor_assignments = {
                        k: v for k, v in self.actor_assignments.items() if v != item_id
                    }
                if db_key == "scenes" and item_id == self.current_scene_id:
                    self.current_scene_id = next(
                        iter(self.db_data.get("scenes", {})), None
                    )
                    # self.prompt_panel.set_current_scene(self.current_scene_id) # update_ui_after_data_change で呼ばれる

                self.update_ui_after_data_change()  # UI全体更新
            else:
                QMessageBox.warning(
                    self, "Delete Error", f"Failed to delete item '{item_id}'."
                )
        else:
            print(f"[DEBUG] Deletion cancelled by user for {item_id}.")


# --- Style Definitions (変更なし) ---
# ... (省略) ...
