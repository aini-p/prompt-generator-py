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
from PySide6.QtGui import QCloseEvent
from .widgets.base_editor_dialog import BaseEditorDialog
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
    Character,
    Style,
    Cut,  # ★ Cut をインポート
)
from typing import Dict, Optional, Any, List, Tuple, Literal, Union, TypeAlias, get_args

# --- パネルとハンドラをインポート ---
from .handlers.data_handler import DataHandler
from .panels.library_panel import LibraryPanel
from .panels.prompt_panel import PromptPanel
from .panels.data_management_panel import DataManagementPanel

# --- 編集ダイアログのインポート ---
from .widgets.actor_editor_dialog import ActorEditorDialog
from .widgets.scene_editor_dialog import SceneEditorDialog
from .widgets.direction_editor_dialog import DirectionEditorDialog
from .widgets.simple_part_editor_dialog import SimplePartEditorDialog
from .widgets.work_editor_dialog import WorkEditorDialog
from .widgets.character_editor_dialog import CharacterEditorDialog
from .widgets.costume_editor_dialog import CostumeEditorDialog
from .widgets.sd_params_editor_dialog import (
    SDParamsEditorDialog,
)  # ★ SDParamsEditorDialog をインポート
from .widgets.cut_editor_dialog import CutEditorDialog  # ★ CutEditorDialog をインポート

# ------------------------------------
from .prompt_generator import generate_batch_prompts, create_image_generation_tasks
from .batch_runner import run_stable_diffusion


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Object-Oriented Prompt Builder")
        self.setGeometry(100, 100, 1200, 800)

        # --- editor_dialog_mapping を修正 ---
        self.editor_dialog_mapping = {
            "WORK": (WorkEditorDialog, "works"),
            "CHARACTER": (CharacterEditorDialog, "characters"),
            "ACTOR": (ActorEditorDialog, "actors"),
            "SCENE": (SceneEditorDialog, "scenes"),
            "CUT": (CutEditorDialog, "cuts"),
            "DIRECTION": (DirectionEditorDialog, "directions"),
            "COSTUME": (CostumeEditorDialog, "costumes"),
            "POSE": (SimplePartEditorDialog, "poses"),
            "EXPRESSION": (SimplePartEditorDialog, "expressions"),
            "BACKGROUND": (SimplePartEditorDialog, "backgrounds"),
            "LIGHTING": (SimplePartEditorDialog, "lighting"),
            "COMPOSITION": (SimplePartEditorDialog, "compositions"),
            "STYLE": (SimplePartEditorDialog, "styles"),
            "SDPARAMS": (SDParamsEditorDialog, "sdParams"),  # ★ 追加 (大文字に変更)
        }
        # --- ▲▲▲ 修正ここまで ▲▲▲ ---

        # --- データ関連 ---
        self.db_data: Dict[str, Dict[str, Any]] = {}
        # self.sd_params: StableDiffusionParams = StableDiffusionParams() # ← 削除
        self.data_handler = DataHandler(self)

        # --- ▼▼▼ データと設定の読み込みを修正 ▼▼▼ ---
        # 1. DBから基本データをロード (sd_params は db_data['sdParams'] に辞書として入る)
        self.db_data, initial_scene_id = self.data_handler.load_all_data()
        # 2. 設定ファイルから最後の状態をロード
        last_scene_id, last_style_id, last_assignments, last_sd_param_id = (
            self.data_handler.load_config()
        )
        # 3. 状態を初期化
        self.current_scene_id = (
            last_scene_id
            if last_scene_id in self.db_data.get("scenes", {})
            else initial_scene_id
        )
        self.current_style_id = (
            last_style_id if last_style_id in self.db_data.get("styles", {}) else None
        )
        # ★ current_sd_param_id を初期化
        self.current_sd_param_id = (
            last_sd_param_id
            if last_sd_param_id in self.db_data.get("sdParams", {})
            else next(
                iter(self.db_data.get("sdParams", {})), None
            )  # 最後の選択、なければ最初のプリセット、それもなければ None
        )
        self.actor_assignments = {
            role_id: actor_id
            for role_id, actor_id in last_assignments.items()
            if actor_id in self.db_data.get("actors", {})
        }
        self.generated_prompts: List[GeneratedPrompt] = []
        # --- ▲▲▲ 修正ここまで ▲▲▲ ---

        # --- UI要素 ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(400)
        left_panel.setMaximumWidth(600)
        self.data_management_panel = DataManagementPanel()
        left_layout.addWidget(self.data_management_panel)
        self.prompt_panel = PromptPanel()
        self.prompt_panel.set_data_reference(self.db_data)
        left_layout.addWidget(self.prompt_panel)
        self.library_panel = LibraryPanel()
        self.library_panel.set_data_reference(self.db_data)
        left_layout.addWidget(self.library_panel)
        left_layout.addStretch()
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setMinimumWidth(500)
        prompt_display_group = QGroupBox("Generated Prompts (Batch)")
        prompt_display_layout = QVBoxLayout(prompt_display_group)
        self.prompt_display_area = QTextEdit()
        self.prompt_display_area.setReadOnly(True)
        prompt_display_layout.addWidget(self.prompt_display_area)
        right_layout.addWidget(prompt_display_group)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([450, 750])
        main_layout.addWidget(splitter)

        self._connect_signals()

        self.prompt_panel.set_current_scene(self.current_scene_id)
        self.prompt_panel.set_current_style(self.current_style_id)
        self.prompt_panel.set_current_sd_params(self.current_sd_param_id)  # ★ 追加
        self.prompt_panel.set_assignments(self.actor_assignments)
        self.update_prompt_display()

    def _connect_signals(self):
        # Data Management Panel
        self.data_management_panel.saveClicked.connect(
            lambda: self.data_handler.save_all_data(
                self.db_data
            )  # ★ sd_params 引数削除
        )
        self.data_management_panel.exportClicked.connect(
            lambda: self.data_handler.export_data(self.db_data)  # ★ sd_params 引数削除
        )
        self.data_management_panel.importClicked.connect(self._handle_import)

        # Prompt Panel
        self.prompt_panel.generatePromptsClicked.connect(self.generate_prompts)
        self.prompt_panel.executeGenerationClicked.connect(self.execute_generation)
        self.prompt_panel.sceneChanged.connect(
            self._handle_scene_change_and_save_config
        )
        self.prompt_panel.assignmentChanged.connect(
            self._handle_assignment_change_and_save_config
        )
        self.prompt_panel.styleChanged.connect(
            self._handle_style_change_and_save_config
        )
        # self.prompt_panel.editSdParamsClicked.connect(self._handle_edit_sd_params) # ← 削除
        self.prompt_panel.sdParamsChanged.connect(
            self._handle_sd_params_change_and_save_config
        )  # ★ 追加

        # Library Panel
        self.library_panel.library_list_widget.itemDoubleClicked.connect(
            self._handle_item_double_clicked
        )
        self.library_panel.addNewItemClicked.connect(self._handle_add_new_item)
        self.library_panel.deleteItemClicked.connect(self._handle_delete_item)

    # --- ▼▼▼ _handle_edit_sd_params を削除 ▼▼▼ ---
    # @Slot()
    # def _handle_edit_sd_params(self): ...
    # --- ▲▲▲ 削除ここまで ▲▲▲ ---

    @Slot(str, str)
    def _handle_add_new_item(self, db_key_str: str, modal_title: str):
        """LibraryPanel の Add New ボタンに対応するスロット。"""
        modal_type = self._get_modal_type_from_db_key(db_key_str)
        if modal_type:
            print(
                f"[DEBUG] Add New button clicked for type: {db_key_str} -> {modal_type}"
            )
            self.open_edit_dialog(modal_type, None)  # item_data=None でダイアログを開く
        else:
            print(
                f"[DEBUG] Error: Cannot determine modal_type for db_key '{db_key_str}'"
            )

    # --- ▼▼▼ _handle_..._and_save_config を修正 (sd_param_id 追加) ▼▼▼ ---
    @Slot(str)
    def _handle_scene_change_and_save_config(self, new_scene_id: str):
        print(f"[DEBUG] MainWindow received sceneChanged signal: {new_scene_id}")
        current_scene_id_before = self.current_scene_id
        self.current_scene_id = new_scene_id if new_scene_id else None
        if current_scene_id_before != self.current_scene_id:
            self.generated_prompts = []
            self.update_prompt_display()
            self.data_handler.save_config(
                self.current_scene_id,
                self.current_style_id,
                self.actor_assignments,
                self.current_sd_param_id,  # ★ 追加
            )

    @Slot(dict)
    def _handle_assignment_change_and_save_config(self, new_assignments: dict):
        print(f"[DEBUG] MainWindow received assignmentChanged: {new_assignments}")
        self.actor_assignments = new_assignments.copy()
        self.generated_prompts = []
        self.update_prompt_display()
        self.data_handler.save_config(
            self.current_scene_id,
            self.current_style_id,
            self.actor_assignments,
            self.current_sd_param_id,  # ★ 追加
        )

    @Slot(str)
    def _handle_style_change_and_save_config(self, new_style_id: str):
        print(f"[DEBUG] MainWindow received styleChanged signal: {new_style_id}")
        new_id_or_none = new_style_id if new_style_id else None
        if self.current_style_id != new_id_or_none:
            self.current_style_id = new_id_or_none
            self.generated_prompts = []
            self.update_prompt_display()
            self.data_handler.save_config(
                self.current_scene_id,
                self.current_style_id,
                self.actor_assignments,
                self.current_sd_param_id,  # ★ 追加
            )

    # --- ▲▲▲ 修正ここまで ▲▲▲ ---

    # --- ▼▼▼ _handle_sd_params_change_and_save_config を追加 ▼▼▼ ---
    @Slot(str)
    def _handle_sd_params_change_and_save_config(self, new_sd_param_id: str):
        """PromptPanel から SD Params 変更の通知を受け取り、設定を保存するスロット。"""
        print(f"[DEBUG] MainWindow received sdParamsChanged signal: {new_sd_param_id}")
        new_id_or_none = new_sd_param_id if new_sd_param_id else None
        if self.current_sd_param_id != new_id_or_none:
            self.current_sd_param_id = new_id_or_none
            self.generated_prompts = []  # 設定が変わったらプレビューはリセット
            self.update_prompt_display()
            self.data_handler.save_config(
                self.current_scene_id,
                self.current_style_id,
                self.actor_assignments,
                self.current_sd_param_id,
            )

    # --- ▲▲▲ 追加ここまで ▲▲▲ ---

    def closeEvent(self, event: QCloseEvent):
        """アプリケーション終了時に設定を保存します。"""
        print("[DEBUG] MainWindow closing. Saving config...")
        self.data_handler.save_config(
            self.current_scene_id,
            self.current_style_id,
            self.actor_assignments,
            self.current_sd_param_id,  # ★ 追加
        )
        event.accept()

    @Slot()
    def _handle_import(self):
        """インポートボタンが押されたときの処理。"""
        imported_db_data = self.data_handler.import_data()  # ★ 戻り値を変更
        if imported_db_data:
            self.db_data = imported_db_data  # ★ db_data を丸ごと入れ替え
            # self.sd_params = ... # ← 削除
            self.library_panel.set_data_reference(self.db_data)
            self.prompt_panel.set_data_reference(self.db_data)

            # --- ▼▼▼ インポート後のデフォルト選択を修正 ▼▼▼ ---
            scenes_dict = self.db_data.get("scenes", {})
            new_scene_id = next(iter(scenes_dict), None)
            # if self.current_scene_id not in scenes_dict: # current_scene_id は上書きするのでチェック不要
            self.current_scene_id = new_scene_id

            self.current_style_id = None  # Style はリセット

            # SD Params もリセット (最初のプリセットを選択)
            self.current_sd_param_id = next(
                iter(self.db_data.get("sdParams", {})), None
            )

            self.update_ui_after_data_change()  # UI全体更新
            self.prompt_panel.set_current_scene(self.current_scene_id)
            self.prompt_panel.set_current_style(self.current_style_id)
            self.prompt_panel.set_current_sd_params(self.current_sd_param_id)  # ★ 追加
            # --- ▲▲▲ 修正ここまで ▲▲▲ ---

    @Slot(QListWidgetItem)
    def _handle_item_double_clicked(self, item: QListWidgetItem):
        """LibraryPanel のリスト項目がダブルクリックされたときの処理。"""
        if not item:
            return
        db_key = self.library_panel._current_db_key
        item_id = item.data(Qt.ItemDataRole.UserRole)

        if db_key and item_id:
            item_data = self.db_data.get(db_key, {}).get(item_id)
            if item_data:
                modal_type = self._get_modal_type_from_db_key(db_key)
                if modal_type:
                    self.open_edit_dialog(modal_type, item_data)
                else:
                    QMessageBox.warning(
                        self, "Error", f"Cannot determine editor type for '{db_key}'"
                    )
            else:
                QMessageBox.warning(
                    self, "Error", f"Could not find data for {db_key} - {item_id}"
                )

    @Slot(str, str)
    def _handle_delete_item(self, db_key_str: str, item_id: str):
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in get_args(DatabaseKey) else None
        )
        if not db_key:
            QMessageBox.critical(
                self, "Error", f"Invalid db_key '{db_key_str}' for deletion."
            )
            return
        self.delete_item(db_key, item_id)

    @Slot(str, object, QWidget)  # QComboBox -> QWidget
    def _handle_open_nested_editor(
        self, modal_type: str, initial_data: Optional[Any], target_widget: QWidget
    ):
        print(
            f"[DEBUG] MainWindow received request to open nested editor: {modal_type}"
        )
        self.open_edit_dialog(
            modal_type, initial_data, target_widget_to_update=target_widget
        )

    # --- コアロジックメソッド ---
    @Slot()
    def generate_prompts(self):
        """プロンプト生成を実行します。"""
        current_scene = self.db_data.get("scenes", {}).get(self.current_scene_id)
        if not current_scene:  # ... エラー処理 ...
            QMessageBox.warning(self, "Generate", "Please select a scene first.")
            return
        current_cut_id = getattr(current_scene, "cut_id", None)
        if not current_cut_id:  # ... エラー処理 ...
            QMessageBox.warning(
                self, "Generate", "選択されたシーンにカットが割り当てられていません。"
            )
            return
        current_cut = self.db_data.get("cuts", {}).get(current_cut_id)
        if not current_cut or not isinstance(current_cut, Cut):  # ... エラー処理 ...
            QMessageBox.warning(
                self,
                "Generate",
                f"割り当てられたカットが見つかりません (ID: {current_cut_id})。",
            )
            return
        roles_in_cut = current_cut.roles

        missing_roles = [
            r.name_in_scene
            for r in roles_in_cut
            if r.id not in self.actor_assignments or not self.actor_assignments[r.id]
        ]
        if missing_roles:  # ... エラー処理 ...
            QMessageBox.warning(
                self,
                "Generate",
                f"すべての配役にアクターを割り当ててください: {', '.join(missing_roles)}",
            )
            return

        try:
            # FullDatabase には辞書を渡す
            full_db = FullDatabase(**self.db_data)  # sdParams は db_data 内に含まれる
            self.generated_prompts = generate_batch_prompts(
                scene_id=self.current_scene_id,
                actor_assignments=self.actor_assignments,
                db=full_db,
                style_id=self.current_style_id,
            )
            self.update_prompt_display()
        except Exception as e:
            QMessageBox.critical(
                self, "Generation Error", f"プロンプト生成中にエラーが発生しました: {e}"
            )
            print(f"[DEBUG] Prompt generation error: {e}")
            traceback.print_exc()

    @Slot()
    def execute_generation(self):
        """画像生成を実行します。"""
        if not self.generated_prompts:  # ... エラー処理 ...
            QMessageBox.warning(
                self, "Execute", "先に 'Generate Prompt Preview' を実行してください。"
            )
            return
        current_scene = self.db_data.get("scenes", {}).get(self.current_scene_id)
        if not current_scene:  # ... エラー処理 ...
            QMessageBox.warning(self, "Execute", "シーンが選択されていません。")
            return

        try:
            # --- ▼▼▼ current_sd_params を取得 ▼▼▼ ---
            current_sd_params = self.db_data.get("sdParams", {}).get(
                self.current_sd_param_id
            )
            if not current_sd_params:
                # フォールバック (最初のプリセット、なければデフォルト値)
                current_sd_params = next(
                    iter(self.db_data.get("sdParams", {}).values()),
                    StableDiffusionParams(
                        id="default_fallback", name="Default Fallback"
                    ),  # ★ デフォルトに ID, Name 追加
                )
                print(
                    f"[WARN] No SD Params selected or found, using fallback: {current_sd_params.name}"
                )
            # --- ▲▲▲ 取得ここまで ▲▲▲ ---

            tasks = create_image_generation_tasks(
                self.generated_prompts,
                current_sd_params,
                current_scene,  # ★ current_sd_params を渡す
            )
            if not tasks:
                QMessageBox.warning(self, "Execute", "生成タスクがありません。")
                return
            success, message = run_stable_diffusion(tasks)
            if success:
                QMessageBox.information(self, "Execute", message)
            else:
                QMessageBox.critical(self, "Execution Error", message)
        except Exception as e:
            QMessageBox.critical(
                self, "Execution Error", f"予期せぬエラーが発生しました: {e}"
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
        current_list_selection_id = None
        current_item = self.library_panel.library_list_widget.currentItem()
        if current_item:
            current_list_selection_id = current_item.data(Qt.ItemDataRole.UserRole)
        current_type_index = self.library_panel.library_type_combo.currentIndex()

        # データ参照を更新
        self.prompt_panel.set_data_reference(self.db_data)
        self.library_panel.set_data_reference(self.db_data)

        # リストタイプと選択状態を復元
        if current_type_index >= 0:
            self.library_panel.library_type_combo.blockSignals(True)
            self.library_panel.library_type_combo.setCurrentIndex(current_type_index)
            self.library_panel.library_type_combo.blockSignals(False)
            self.library_panel.update_list()

        if current_list_selection_id:
            self.library_panel.select_item_by_id(current_list_selection_id)

        print("[DEBUG] update_ui_after_data_change complete.")

    def open_edit_dialog(
        self,
        modal_type: str,
        item_data: Optional[Any],
        target_widget_to_update: Optional[QWidget] = None,
    ):
        """編集ダイアログを開きます (新規作成・編集兼用)。"""
        dialog_info = self.editor_dialog_mapping.get(modal_type)
        if not dialog_info:
            QMessageBox.warning(self, "Error", f"Invalid editor type: {modal_type}")
            return

        DialogClass, db_key_str = dialog_info
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in get_args(DatabaseKey) else None
        )
        if not db_key:
            QMessageBox.critical(
                self,
                "Error",
                f"Internal error: Invalid db_key '{db_key_str}' for type '{modal_type}'",
            )
            return

        print(
            f"[DEBUG] Opening editor dialog for type: {modal_type}, data: {'Exists' if item_data else 'None'}"
        )
        dialog: Optional[BaseEditorDialog] = None
        try:
            # --- ▼▼▼ SDParamsEditorDialog の呼び出しを追加 ▼▼▼ ---
            if DialogClass == SimplePartEditorDialog:
                dialog = DialogClass(item_data, modal_type, self.db_data, self)
            elif DialogClass == CutEditorDialog:
                dialog = DialogClass(item_data, self.db_data, self)
            elif DialogClass == SDParamsEditorDialog:  # ★ 追加
                dialog = DialogClass(item_data, self.db_data, self)
            else:
                dialog = DialogClass(item_data, self.db_data, self)
            # --- ▲▲▲ 追加ここまで ▲▲▲ ---
            if dialog:
                dialog.request_open_editor.connect(self._handle_open_nested_editor)

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
                saved_data = dialog.saved_data
                if saved_data:
                    item_id_to_select = getattr(saved_data, "id", None)
                    print(
                        f"[DEBUG] Dialog returned data: {item_id_to_select} of type {type(saved_data).__name__}."
                    )

                    if DialogClass == SimplePartEditorDialog and isinstance(
                        saved_data, PromptPartBase
                    ):
                        target_class: Optional[Type[PromptPartBase]] = None
                        if db_key == "poses":
                            target_class = Pose
                        elif db_key == "expressions":
                            target_class = Expression
                        elif db_key == "backgrounds":
                            target_class = Background
                        elif db_key == "lighting":
                            target_class = Lighting
                        elif db_key == "compositions":
                            target_class = Composition
                        elif db_key == "styles":
                            target_class = Style
                        if target_class:
                            try:
                                saved_data = target_class(**saved_data.__dict__)
                            except TypeError as e:
                                print(f"[ERROR] Failed to convert...: {e}")
                                saved_data = None
                        else:
                            print(f"[ERROR] Unknown db_key '{db_key}'...")
                            saved_data = None

                    if saved_data and item_id_to_select:
                        # 1. メモリに追加/更新
                        is_new_scene_with_new_cut = False  # (不要になった)
                        if db_key == "cuts":
                            if "cuts" not in self.db_data:
                                self.db_data["cuts"] = {}
                            self.db_data["cuts"][item_id_to_select] = saved_data
                            print(
                                f"[DEBUG] Cut {item_id_to_select} saved/updated in memory."
                            )
                            # newly_created_cut_id のロジックは削除

                        elif db_key == "sdParams":  # ★ sdParams をメモリに追加
                            if "sdParams" not in self.db_data:
                                self.db_data["sdParams"] = {}
                            self.db_data["sdParams"][item_id_to_select] = saved_data
                            print(
                                f"[DEBUG] SD Param {item_id_to_select} saved/updated in memory."
                            )
                        elif db_key in self.db_data:
                            self.db_data[db_key][item_id_to_select] = saved_data
                        else:
                            print(f"[ERROR] Invalid db_key '{db_key}'...")
                            return

                        # 2. DBに即時保存
                        try:
                            # is_new_scene_with_new_cut のロジックは削除
                            if db_key == "cuts":
                                db.save_cut(saved_data)
                            elif db_key == "sdParams":
                                db.save_sd_param(saved_data)  # ★ sdParams をDBに保存
                            else:
                                self.data_handler.save_single_item(db_key, saved_data)
                        except Exception as db_save_e:
                            print(
                                f"[ERROR] Failed to save item {item_id_to_select} to DB: {db_save_e}"
                            )

                        # 3. UI更新
                        if target_widget_to_update:
                            parent_dialog = target_widget_to_update.parent()
                            while parent_dialog and not isinstance(
                                parent_dialog, QDialog
                            ):
                                parent_dialog = parent_dialog.parent()
                            if isinstance(parent_dialog, BaseEditorDialog):
                                parent_dialog.update_combo_box_after_edit(
                                    target_widget_to_update, db_key, item_id_to_select
                                )
                            else:
                                print(
                                    "[ERROR] Could not find parent BaseEditorDialog..."
                                )
                        else:
                            self.update_ui_after_data_change()
                            if item_id_to_select:
                                self.library_panel.select_item_by_id(item_id_to_select)
                    elif not saved_data:
                        QMessageBox.warning(
                            self,
                            "Save Error",
                            "データの保存に失敗しました (型変換エラーまたは不明なタイプ)。",
                        )
                else:
                    print("[DEBUG] Dialog accepted but returned no valid data.")
            else:
                print("[DEBUG] Dialog cancelled or closed.")

    def _get_modal_type_from_db_key(
        self, db_key: Optional[DatabaseKey]
    ) -> Optional[str]:
        if not db_key:
            return None
        for modal_type, (dialog_class, key_str) in self.editor_dialog_mapping.items():
            if key_str == db_key:
                return modal_type
        # ★ sdParams 用のフォールバック (大文字に変更したため) -> 不要、マッピングキーを大文字にした
        # if db_key == "sdParams": return "SDPARAMS"
        return None

    def delete_item(self, db_key: DatabaseKey, item_id: str):
        item_to_delete = self.db_data.get(db_key, {}).get(item_id)
        if not item_to_delete:  # ... エラー処理 ...
            return
        item_name = getattr(item_to_delete, "title_jp", None) or getattr(
            item_to_delete, "name", item_id
        )
        confirm = QMessageBox.question(...)
        if confirm == QMessageBox.StandardButton.Yes:
            deleted_from_memory = self.data_handler.handle_delete_part(
                db_key, item_id, self.db_data
            )
            if deleted_from_memory:
                try:
                    # --- ▼▼▼ sdParam の削除処理を追加 ▼▼▼ ---
                    if db_key == "sdParams":
                        db.delete_sd_param(item_id)
                    else:
                        db._delete_item(db_key, item_id)
                    # --- ▲▲▲ 変更ここまで ▲▲▲ ---
                    print(
                        f"[DEBUG] Item {item_id} deleted from database table '{db_key}'."
                    )
                except Exception as db_del_e:  # ... エラー処理 ...
                    pass

                # --- ▼▼▼ 関連データの更新 ▼▼▼ ---
                if db_key == "actors":  # ... actor_assignments ...
                    pass
                if db_key == "scenes" and item_id == self.current_scene_id:
                    self.current_scene_id = next(
                        iter(self.db_data.get("scenes", {})), None
                    )
                if db_key == "cuts":
                    for scene in self.db_data.get("scenes", {}).values():
                        if scene.cut_id == item_id:
                            scene.cut_id = None
                            db.save_scene(scene)  # DB も更新
                    # UI 更新は update_ui_after_data_change でカバーされるはず
                if db_key == "sdParams" and item_id == self.current_sd_param_id:
                    # ★ 削除された SD Param が選択されていたらリセット
                    self.current_sd_param_id = next(
                        iter(self.db_data.get("sdParams", {})), None
                    )
                    self.prompt_panel.set_current_sd_params(
                        self.current_sd_param_id
                    )  # ★ UI も更新
                # --- ▲▲▲ 変更ここまで ▲▲▲ ---

                self.update_ui_after_data_change()
            # ... (else 節) ...
        else:
            print(f"[DEBUG] Deletion cancelled by user for {item_id}.")


# --- (main 関数実行部分は変更なし) ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    try:
        db.initialize_db()
    except Exception as e:
        print(f"FATAL: Could not initialize database: {e}")
        sys.exit(1)
    try:
        window = MainWindow()
        window.show()
    except Exception as e:
        print(f"FATAL: Could not create main window: {e}")
        traceback.print_exc()  # ★ 詳細なトレースバックを表示
        sys.exit(1)
    sys.exit(app.exec())
