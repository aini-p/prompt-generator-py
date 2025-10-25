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
from .widgets.actor_editor_dialog import (
    ActorEditorDialog,
)
from .widgets.scene_editor_dialog import (
    SceneEditorDialog,
)
from .widgets.direction_editor_dialog import (
    DirectionEditorDialog,
)
from .widgets.simple_part_editor_dialog import (
    SimplePartEditorDialog,
)
from .widgets.work_editor_dialog import (
    WorkEditorDialog,
)
from .widgets.character_editor_dialog import (
    CharacterEditorDialog,
)
from .widgets.costume_editor_dialog import CostumeEditorDialog
from .widgets.sd_params_editor_dialog import SDParamsEditorDialog
from .widgets.cut_editor_dialog import CutEditorDialog

# ------------------------------------
from .prompt_generator import generate_batch_prompts, create_image_generation_tasks
from .batch_runner import run_stable_diffusion


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Object-Oriented Prompt Builder")
        self.setGeometry(100, 100, 1200, 800)

        # --- editor_dialog_mapping (変更なし) ---
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
        }

        # --- データ関連 (変更なし) ---
        self.db_data: Dict[str, Dict[str, Any]] = {}
        self.sd_params: StableDiffusionParams = StableDiffusionParams()
        self.data_handler = DataHandler(self)
        self.db_data, self.sd_params, initial_scene_id = (
            self.data_handler.load_all_data()
        )
        last_scene_id, last_style_id, last_assignments = self.data_handler.load_config()
        self.current_scene_id = (
            last_scene_id
            if last_scene_id in self.db_data.get("scenes", {})
            else initial_scene_id
        )
        self.current_style_id = (
            last_style_id if last_style_id in self.db_data.get("styles", {}) else None
        )
        self.actor_assignments = {
            role_id: actor_id
            for role_id, actor_id in last_assignments.items()
            if actor_id in self.db_data.get("actors", {})
        }
        self.generated_prompts: List[GeneratedPrompt] = []

        # --- UI要素 (変更なし) ---
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

        # --- シグナル接続 (変更なし) ---
        self._connect_signals()

        # --- 初期UI状態設定 (変更なし) ---
        self.prompt_panel.set_current_scene(self.current_scene_id)
        self.prompt_panel.set_current_style(self.current_style_id)
        self.prompt_panel.set_assignments(self.actor_assignments)
        self.update_prompt_display()

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
        self.prompt_panel.sceneChanged.connect(
            self._handle_scene_change_and_save_config
        )
        self.prompt_panel.assignmentChanged.connect(
            self._handle_assignment_change_and_save_config
        )
        self.prompt_panel.styleChanged.connect(
            self._handle_style_change_and_save_config
        )
        self.prompt_panel.editSdParamsClicked.connect(self._handle_edit_sd_params)

        # Library Panel
        self.library_panel.library_list_widget.itemDoubleClicked.connect(
            self._handle_item_double_clicked
        )
        self.library_panel.addNewItemClicked.connect(self._handle_add_new_item)
        self.library_panel.deleteItemClicked.connect(self._handle_delete_item)

    @Slot()
    def _handle_edit_sd_params(self):
        """PromptPanel の Edit SD Params ボタンに対応するスロット。"""
        print("[DEBUG] Edit SD Params button clicked.")
        dialog = SDParamsEditorDialog(self.sd_params, self.db_data, self)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            updated_params = dialog.saved_data
            if updated_params and isinstance(updated_params, StableDiffusionParams):
                self.sd_params = updated_params
                print("[DEBUG] SD Params updated in MainWindow.")
                try:
                    db.save_sd_params(self.sd_params)
                    print("[DEBUG] Updated SD Params saved to database.")
                except Exception as e:
                    QMessageBox.warning(
                        self,
                        "DB Save Error",
                        f"SD Params のデータベース保存に失敗しました: {e}",
                    )
                    print(f"[ERROR] Failed to save updated SD Params to DB: {e}")
            else:
                print("[DEBUG] SD Params dialog returned invalid data.")
        else:
            print("[DEBUG] SD Params dialog cancelled.")

    @Slot(str)
    def _handle_scene_change_and_save_config(self, new_scene_id: str):
        """PromptPanel からシーン変更の通知を受け取り、設定を保存するスロット。"""
        print(f"[DEBUG] MainWindow received sceneChanged signal: {new_scene_id}")
        current_scene_id_before = self.current_scene_id
        self.current_scene_id = new_scene_id if new_scene_id else None
        if current_scene_id_before != self.current_scene_id:
            self.generated_prompts = []
            self.update_prompt_display()
            self.data_handler.save_config(
                self.current_scene_id, self.current_style_id, self.actor_assignments
            )

    @Slot(dict)
    def _handle_assignment_change_and_save_config(self, new_assignments: dict):
        """PromptPanel から割り当て変更の通知を受け取り、設定を保存するスロット。"""
        print(f"[DEBUG] MainWindow received assignmentChanged: {new_assignments}")
        self.actor_assignments = new_assignments.copy()
        self.generated_prompts = []
        self.update_prompt_display()
        self.data_handler.save_config(
            self.current_scene_id, self.current_style_id, self.actor_assignments
        )

    @Slot(str)
    def _handle_style_change_and_save_config(self, new_style_id: str):
        """PromptPanel から Style 変更の通知を受け取り、設定を保存するスロット。"""
        print(f"[DEBUG] MainWindow received styleChanged signal: {new_style_id}")
        new_id_or_none = new_style_id if new_style_id else None
        if self.current_style_id != new_id_or_none:
            self.current_style_id = new_id_or_none
            self.generated_prompts = []
            self.update_prompt_display()
            self.data_handler.save_config(
                self.current_scene_id, self.current_style_id, self.actor_assignments
            )

    def closeEvent(self, event: QCloseEvent):
        """アプリケーション終了時に設定を保存します。"""
        print("[DEBUG] MainWindow closing. Saving config...")
        self.data_handler.save_config(
            self.current_scene_id, self.current_style_id, self.actor_assignments
        )
        event.accept()

    @Slot()
    def _handle_import(self):
        """インポートボタンが押されたときの処理。"""
        imported = self.data_handler.import_data()
        if imported:
            self.db_data, imported_sd_params = imported
            self.sd_params = imported_sd_params
            self.library_panel.set_data_reference(self.db_data)
            self.prompt_panel.set_data_reference(self.db_data)
            scenes_dict = self.db_data.get("scenes", {})
            new_scene_id = next(iter(scenes_dict), None)
            if self.current_scene_id not in scenes_dict:
                self.current_scene_id = new_scene_id
            self.update_ui_after_data_change()
            self.prompt_panel.set_current_scene(self.current_scene_id)
            self.prompt_panel.set_current_style(None)

    @Slot(str, str)
    def _handle_add_new_item(self, db_key_str: str, modal_title: str):
        """LibraryPanel の Add New ボタンに対応するスロット。"""
        modal_type = self._get_modal_type_from_db_key(db_key_str)
        if modal_type:
            print(
                f"[DEBUG] Add New button clicked for type: {db_key_str} -> {modal_type}"
            )
            self.open_edit_dialog(modal_type, None)
        else:
            print(
                f"[DEBUG] Error: Cannot determine modal_type for db_key '{db_key_str}'"
            )

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
        """LibraryPanel の Delete ボタンに対応するスロット。"""
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in get_args(DatabaseKey) else None
        )
        if not db_key:
            QMessageBox.critical(
                self, "Error", f"Invalid db_key '{db_key_str}' for deletion."
            )
            return
        self.delete_item(db_key, item_id)

    @Slot(str, object, QWidget)
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
        if not self.current_scene_id:
            QMessageBox.warning(self, "Generate", "Please select a scene first.")
            return
        current_scene = self.db_data.get("scenes", {}).get(self.current_scene_id)
        if not current_scene:
            QMessageBox.warning(self, "Generate", "Selected scene data not found.")
            return

        # --- ▼▼▼ 修正 ▼▼▼ ---
        # 1. Scene から cut_id を取得
        current_cut_id = getattr(current_scene, "cut_id", None)
        if not current_cut_id:
            QMessageBox.warning(
                self, "Generate", "選択されたシーンにカットが割り当てられていません。"
            )
            return

        # 2. cut_id から Cut オブジェクトを取得
        current_cut = self.db_data.get("cuts", {}).get(current_cut_id)
        if not current_cut or not isinstance(current_cut, Cut):
            QMessageBox.warning(
                self,
                "Generate",
                f"割り当てられたカットが見つかりません (ID: {current_cut_id})。",
            )
            return

        # 3. Cut の roles を使用
        roles_in_cut = current_cut.roles
        # --- ▲▲▲ 修正ここまで ▲▲▲ ---

        print(f"[DEBUG] generate_prompts: Checking scene ID: {self.current_scene_id}")
        # --- ▼▼▼ 修正 ▼▼▼ ---
        # L484: current_scene.roles -> roles_in_cut
        print(
            f"[DEBUG] generate_prompts: Expected Role IDs: {[r.id for r in roles_in_cut]}"
        )
        # --- ▲▲▲ 修正ここまで ▲▲▲ ---
        print(
            f"[DEBUG] generate_prompts: Current assignments: {self.actor_assignments}"
        )

        # --- ▼▼▼ 修正 ▼▼▼ ---
        # L490: current_scene.roles -> roles_in_cut
        missing_roles = [
            r.name_in_scene
            for r in roles_in_cut
            if r.id not in self.actor_assignments or not self.actor_assignments[r.id]
        ]
        # --- ▲▲▲ 修正ここまで ▲▲▲ ---

        if missing_roles:
            QMessageBox.warning(
                self,
                "Generate",
                f"すべての配役にアクターを割り当ててください: {', '.join(missing_roles)}",
            )
            return

        try:
            full_db = FullDatabase(**self.db_data, sdParams=self.sd_params)
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
        if not self.generated_prompts:
            QMessageBox.warning(
                self, "Execute", "先に 'Generate Prompt Preview' を実行してください。"
            )
            return
        current_scene = self.db_data.get("scenes", {}).get(self.current_scene_id)
        if not current_scene:
            QMessageBox.warning(self, "Execute", "シーンが選択されていません。")
            return
        try:
            tasks = create_image_generation_tasks(
                self.generated_prompts, self.sd_params, current_scene
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

        self.prompt_panel.set_data_reference(self.db_data)
        self.library_panel.set_data_reference(self.db_data)

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
        newly_created_cut_id: Optional[str] = None  # ★ 新規 Cut ID 退避用

        try:
            if DialogClass == SimplePartEditorDialog:
                dialog = DialogClass(item_data, modal_type, self.db_data, self)
            elif DialogClass == CutEditorDialog:
                dialog = DialogClass(item_data, self.db_data, self)
            else:
                dialog = DialogClass(item_data, self.db_data, self)
            print(f"[DEBUG] Dialog instance created: {dialog}")

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
                            print(
                                f"[DEBUG] Converting PromptPartBase to {target_class.__name__} object."
                            )
                            try:
                                saved_data = target_class(**saved_data.__dict__)
                                print(
                                    f"[DEBUG] Conversion successful: {type(saved_data).__name__}"
                                )
                            except TypeError as e:
                                print(
                                    f"[ERROR] Failed to convert PromptPartBase to {target_class.__name__}: {e}. Cannot save."
                                )
                                saved_data = None
                        else:
                            print(
                                f"[ERROR] Unknown db_key '{db_key}' for SimplePartEditorDialog result. Cannot save."
                            )
                            saved_data = None

                    if saved_data and item_id_to_select:
                        # 1. メモリに追加/更新
                        is_new_scene_with_new_cut = False
                        if db_key == "cuts":
                            if "cuts" not in self.db_data:
                                self.db_data["cuts"] = {}
                            self.db_data["cuts"][item_id_to_select] = saved_data
                            print(
                                f"[DEBUG] Cut {item_id_to_select} saved/updated in memory."
                            )
                            if (
                                target_widget_to_update
                                and isinstance(
                                    target_widget_to_update.parent(), SceneEditorDialog
                                )
                                and not target_widget_to_update.parent().initial_data
                            ):
                                newly_created_cut_id = item_id_to_select
                                print(
                                    f"[DEBUG] New Cut {newly_created_cut_id} created during new Scene creation."
                                )

                        elif db_key == "scenes" and not item_data:  # 新規 Scene
                            scene_cut_id = getattr(saved_data, "cut_id", None)
                            # この時点では newly_created_cut_id はまだ設定されていない可能性
                            # -> このロジックは SceneEditorDialog.get_data に任せるべき
                            # ここでは Scene をメモリに保存するだけ
                            if db_key in self.db_data:
                                self.db_data[db_key][item_id_to_select] = saved_data
                            else:
                                print(f"[ERROR] Invalid db_key '{db_key}'...")
                                return

                        elif db_key in self.db_data:
                            self.db_data[db_key][item_id_to_select] = saved_data
                        else:
                            print(
                                f"[ERROR] Invalid db_key '{db_key}' when trying to save data."
                            )
                            return

                        # 2. DBに即時保存
                        try:
                            # ★ 新規 Scene が新規 Cut を参照する場合、Cut を先に保存
                            if db_key == "scenes" and not item_data:  # 新規 Scene
                                scene_cut_id = getattr(saved_data, "cut_id", None)
                                # new_cut = self.db_data.get("cuts", {}).get(scene_cut_id)
                                # if new_cut and scene_cut_id == newly_created_cut_id: # この判定が難しい
                                #     print(f"[DEBUG] Saving newly created Cut {scene_cut_id} first...")
                                #     db.save_cut(new_cut)
                                #
                                # 簡略化: Cut は Cut ダイアログが閉じた時点で即時保存されているはず
                                # (このロジックは Cut が List[Cut] だったときの名残)
                                pass

                            if db_key == "cuts":
                                db.save_cut(saved_data)
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
                                if isinstance(target_widget_to_update, QComboBox):
                                    parent_dialog.update_combo_box_after_edit(
                                        target_widget_to_update,
                                        db_key,
                                        item_id_to_select,
                                    )
                                elif isinstance(target_widget_to_update, QListWidget):
                                    parent_dialog.update_combo_box_after_edit(  # 基底メソッドを呼ぶ (SceneEditorDialog がオーバーライド)
                                        target_widget_to_update,
                                        db_key,
                                        item_id_to_select,
                                    )
                                else:
                                    print(
                                        f"[ERROR] Unsupported target widget type for update: {type(target_widget_to_update)}"
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
        """db_key 文字列から editor_dialog_mapping のキー (modal_type) を逆引きします。"""
        if not db_key:
            return None
        for modal_type, (dialog_class, key_str) in self.editor_dialog_mapping.items():
            if key_str == db_key:
                return modal_type
        return None

    def delete_item(self, db_key: DatabaseKey, item_id: str):
        """指定されたアイテムを削除します（確認含む）。"""
        item_to_delete = self.db_data.get(db_key, {}).get(item_id)
        if not item_to_delete:
            QMessageBox.warning(
                self, "Delete Error", f"Item '{item_id}' not found in '{db_key}'."
            )
            return

        item_name = getattr(item_to_delete, "title_jp", None) or getattr(
            item_to_delete, "name", item_id
        )

        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"'{item_name}' ({item_id}) をメモリとデータベースから削除しますか？\n"
            f"この操作は元に戻せません。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            deleted_from_memory = self.data_handler.handle_delete_part(
                db_key, item_id, self.db_data
            )
            if deleted_from_memory:
                try:
                    db._delete_item(db_key, item_id)
                    print(
                        f"[DEBUG] Item {item_id} deleted from database table '{db_key}'."
                    )
                except Exception as db_del_e:
                    print(
                        f"[ERROR] Failed to delete item {item_id} from database: {db_del_e}"
                    )
                    QMessageBox.warning(
                        self,
                        "DB Delete Error",
                        f"メモリからは削除しましたが、データベースからの削除中にエラーが発生しました。\nError: {db_del_e}",
                    )

                if db_key == "actors":
                    self.actor_assignments = {
                        k: v for k, v in self.actor_assignments.items() if v != item_id
                    }
                if db_key == "scenes" and item_id == self.current_scene_id:
                    self.current_scene_id = next(
                        iter(self.db_data.get("scenes", {})), None
                    )
                # ★ Cut 削除時に Scene の cut_id をクリアする処理を追加
                if db_key == "cuts":
                    for scene in self.db_data.get("scenes", {}).values():
                        if scene.cut_id == item_id:
                            scene.cut_id = None
                            db.save_scene(scene)  # DB も更新
                    # もし PromptPanel でその Cut を持つ Scene が選択されていたら UI 更新
                    if self.current_scene_id:
                        current_scene = self.db_data.get("scenes", {}).get(
                            self.current_scene_id
                        )
                        if current_scene and current_scene.cut_id == item_id:
                            self.prompt_panel.build_role_assignment_ui()

                self.update_ui_after_data_change()
            else:
                pass
        else:
            print(f"[DEBUG] Deletion cancelled by user for {item_id}.")
