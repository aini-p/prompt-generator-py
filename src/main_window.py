# src/main_window.py
import sys, os, json, time, traceback
import copy
import math
import csv
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
    QTabWidget,
    QProgressBar,
    QFormLayout,
)
from PySide6.QtCore import Qt, Slot, QModelIndex, QMimeData, QThread, Signal, QTimer
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent, QDragMoveEvent
from .widgets.base_editor_dialog import BaseEditorDialog
from . import database as db
from .models import (
    Scene,
    Actor,
    StateCategory,
    PromptPartBase,
    StableDiffusionParams,
    Costume,
    Pose,
    Expression,
    Background,
    Lighting,
    Composition,
    SceneRole,
    GeneratedPrompt,
    ImageGenerationTask,
    STORAGE_KEYS,
    DatabaseKey,
    FullDatabase,
    Work,
    Character,
    Style,
    Cut,
    Sequence,
    SequenceSceneEntry,
    QueueItem,
    ColorPaletteItem,
    State,
    AdditionalPrompt,
    RoleAppearanceAssignment,
    BatchMetadata,
)
from typing import (
    Dict,
    Optional,
    Any,
    List,
    Tuple,
    Literal,
    Union,
    TypeAlias,
    get_args,
    Type,
)

# --- パネルとハンドラをインポート ---
from .handlers.data_handler import DataHandler
from .panels.library_panel import LibraryPanel
from .panels.prompt_panel import PromptPanel
from .panels.data_management_panel import DataManagementPanel
from .panels.batch_panel import BatchPanel

# --- 編集ダイアログのインポート ---
from .widgets.actor_editor_dialog import ActorEditorDialog
from .widgets.scene_editor_dialog import SceneEditorDialog
from .widgets.simple_part_editor_dialog import SimplePartEditorDialog
from .widgets.work_editor_dialog import WorkEditorDialog
from .widgets.character_editor_dialog import CharacterEditorDialog
from .widgets.costume_editor_dialog import CostumeEditorDialog
from .widgets.sd_params_editor_dialog import SDParamsEditorDialog
from .widgets.cut_editor_dialog import CutEditorDialog
from .widgets.sequence_editor_dialog import SequenceEditorDialog
from .widgets.actor_assignment_dialog import ActorAssignmentDialog
from .widgets.state_editor_dialog import StateEditorDialog
from .widgets.state_category_editor_dialog import StateCategoryEditorDialog
from .widgets.generic_selection_dialog import GenericSelectionDialog
from .widgets.generation_options_dialog import GenerationOptionsDialog

# ------------------------------------
from .prompt_generator import generate_batch_prompts, create_image_generation_tasks
from .generation_worker import BackendManager, TaskSubmitter


class MainWindow(QMainWindow):
    start_backend_signal = Signal(str)
    submit_tasks_signal = Signal(list)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Object-Oriented Prompt Builder")
        self.setGeometry(100, 100, 1200, 800)

        self.editor_dialog_mapping: Dict[str, Tuple[Type[QDialog], DatabaseKey]] = {
            "WORK": (WorkEditorDialog, "works"),
            "CHARACTER": (CharacterEditorDialog, "characters"),
            "ACTOR": (ActorEditorDialog, "actors"),
            "SCENE": (SceneEditorDialog, "scenes"),
            "CUT": (CutEditorDialog, "cuts"),
            "COSTUME": (CostumeEditorDialog, "costumes"),
            "POSE": (SimplePartEditorDialog, "poses"),
            "EXPRESSION": (SimplePartEditorDialog, "expressions"),
            "BACKGROUND": (SimplePartEditorDialog, "backgrounds"),
            "LIGHTING": (SimplePartEditorDialog, "lighting"),
            "COMPOSITION": (SimplePartEditorDialog, "compositions"),
            "STYLE": (SimplePartEditorDialog, "styles"),
            "STATE_CATEGORY": (StateCategoryEditorDialog, "state_categories"),
            "STATE": (StateEditorDialog, "states"),
            "ADDITIONAL_PROMPT": (SimplePartEditorDialog, "additional_prompts"),
            "SDPARAMS": (SDParamsEditorDialog, "sdParams"),
            "SEQUENCE": (SequenceEditorDialog, "sequences"),
        }

        # --- 1. データハンドラと変数を準備 ---
        self.db_data: Dict[str, Dict[str, Any]] = {}
        self.batch_queue: List[QueueItem] = []
        self.current_scene_id: Optional[str] = None
        self.actor_assignments: Dict[str, str] = {}
        self.appearance_overrides: Dict[str, Dict[str, Optional[str]]] = {}
        self.generated_prompts: List[GeneratedPrompt] = []
        self.image_output_base_dir: str = "data/output_images"
        self.data_handler = DataHandler(self)
        self.open_editors: Dict[str, QDialog] = {} # 開いているエディタを追跡

        # --- 2. DBとConfigからすべてのデータを読み込む ---
        _db_data, _batch_queue, initial_scene_id = self.data_handler.load_all_data()
        self.db_data = _db_data
        self.batch_queue = _batch_queue
        
        (
            last_scene_id,
            last_assignments,
            last_overrides,
            self.image_output_base_dir,
        ) = self.data_handler.load_config()
        print(f"[DEBUG-INIT] Loaded last_assignments from config: {last_assignments}")

        # --- 3. 読み込んだデータで状態を初期化 ---
        self.current_scene_id = (
            last_scene_id
            if last_scene_id in self.db_data.get("scenes", {})
            else initial_scene_id
        )
        self.actor_assignments = {
            role_id: actor_id
            for role_id, actor_id in last_assignments.items()
            if actor_id in self.db_data.get("actors", {})
        }
        print(f"[DEBUG-INIT] self.actor_assignments after filtering: {self.actor_assignments}")
        self.appearance_overrides = last_overrides

        # --- 4. UI要素を構築 ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        left_tab_widget = QTabWidget()
        left_tab_widget.setMinimumWidth(400)
        left_tab_widget.setMaximumWidth(600)

        prompt_tab = QWidget()
        prompt_tab_layout = QVBoxLayout(prompt_tab)
        self.data_management_panel = DataManagementPanel()
        prompt_tab_layout.addWidget(self.data_management_panel)
        
        self.prompt_panel = PromptPanel()
        prompt_tab_layout.addWidget(self.prompt_panel)
        prompt_tab_layout.addStretch()
        left_tab_widget.addTab(prompt_tab, "Prompt Generation")

        self.batch_panel = BatchPanel()
        left_tab_widget.addTab(self.batch_panel, "Batch (Sequence)")

        self.library_panel = LibraryPanel()
        left_tab_widget.addTab(self.library_panel, "Library")

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setMinimumWidth(500)
        prompt_display_group = QGroupBox("Generated Prompts (Batch or Single)")
        prompt_display_layout = QVBoxLayout(prompt_display_group)
        self.prompt_display_area = QTextEdit()
        self.prompt_display_area.setReadOnly(True)
        prompt_display_layout.addWidget(self.prompt_display_area)
        right_layout.addWidget(prompt_display_group)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_tab_widget)
        splitter.addWidget(right_panel)
        splitter.setSizes([450, 750])
        main_layout.addWidget(splitter)

        # --- 5. シグナルを接続 ---
        self._connect_signals()

        # --- 6. ワーカーをセットアップ ---
        self._setup_workers()

        # --- 7. UIパネルに初期データを設定し、UIを更新 ---
        self.prompt_panel.set_data_reference(self.db_data)
        print(f"[DEBUG-INIT] Passing assignments to panel: {self.actor_assignments}")
        self.prompt_panel.set_assignments(self.actor_assignments)
        self.prompt_panel._current_overrides = self.appearance_overrides
        self.prompt_panel.update_scene_combo() # これでUIが構築される
        self.prompt_panel.set_current_scene(self.current_scene_id) # これで選択状態が合う
        self.update_pending_task_count() 

        self.batch_panel.set_data_reference(
            self.db_data.get("sequences", {}), self.batch_queue
        )
        self.library_panel.set_data_reference(self.db_data)

        self.update_prompt_display()

        # --- 8. バックエンドを自動起動 ---
        self._handle_start_backend()

    def _setup_workers(self):
        # Backend Manager Worker
        self.backend_thread = QThread(self)
        self.backend_manager = BackendManager()
        self.backend_manager.moveToThread(self.backend_thread)
        self.backend_manager.log_message.connect(self.on_worker_log)
        self.start_backend_signal.connect(self.backend_manager.start_backend)
        self.backend_thread.start()

        # Task Submitter Worker
        self.submitter_thread = QThread(self)
        self.task_submitter = TaskSubmitter()
        self.task_submitter.moveToThread(self.submitter_thread)
        self.task_submitter.log_message.connect(self.on_worker_log)
        self.task_submitter.finished.connect(self.on_submission_finished)
        self.submit_tasks_signal.connect(self.task_submitter.submit_tasks)
        self.submitter_thread.start()

        # Task Count Timer
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.task_queue_dir = os.path.join(
            project_root, "StableDiffusionClient", "data", "tasks_queue"
        )
        self.task_count_timer = QTimer(self)
        self.task_count_timer.timeout.connect(self.update_pending_task_count)
        self.task_count_timer.start(5000)  # Update every 5 seconds

    @Slot()
    def update_pending_task_count(self):
        count = 0
        try:
            # Ensure the directory exists before trying to list its contents
            if os.path.isdir(self.task_queue_dir):
                count = len(
                    [
                        f
                        for f in os.listdir(self.task_queue_dir)
                        if f.endswith(".json")
                    ]
                )
        except Exception as e:
            # In case of any error (e.g., permission denied), log it and default to 0
            print(f"Error counting tasks in queue: {e}")
            count = 0
        self.prompt_panel.update_task_count(count)

    def _connect_signals(self):
        # Data Management Panel
        self.data_management_panel.saveClicked.connect(
            lambda: self.data_handler.save_all_data(self.db_data, self.batch_queue)
        )
        self.data_management_panel.exportClicked.connect(
            lambda: self.data_handler.export_data(self.db_data, self.batch_queue)
        )
        self.data_management_panel.importClicked.connect(self._handle_import)
        self.data_management_panel.syncCsvClicked.connect(self._handle_sync_csv)
        # Prompt Panel
        self.prompt_panel.generatePromptsClicked.connect(self.generate_prompts)
        self.prompt_panel.executeGenerationClicked.connect(self.execute_generation)
        self.prompt_panel.sceneChanged.connect(
            self._handle_scene_change_and_save_config
        )
        self.prompt_panel.assignmentChanged.connect(
            self._handle_assignment_change_and_save_config
        )

        # Library Panel
        self.library_panel.library_list_widget.itemDoubleClicked.connect(
            self._handle_item_double_clicked
        )
        self.library_panel.addNewItemClicked.connect(self._handle_add_new_item)
        self.library_panel.copyItemClicked.connect(self._handle_copy_item)
        self.library_panel.deleteItemClicked.connect(self._handle_delete_item)

        # Batch Panel
        self.batch_panel.addSequenceClicked.connect(
            lambda: self.open_edit_dialog("SEQUENCE", None)
        )
        self.batch_panel.editSequenceClicked.connect(self._handle_edit_sequence)
        self.batch_panel.deleteSequenceClicked.connect(
            lambda seq_id: self.delete_item("sequences", seq_id)
        )
        self.batch_panel.addSequenceToQueueClicked.connect(self._handle_add_to_queue)
        self.batch_panel.editQueueItemAssignmentsClicked.connect(
            self._handle_edit_queue_assignments
        )
        self.batch_panel.removeQueueItemClicked.connect(self._handle_remove_from_queue)
        self.batch_panel.clearQueueClicked.connect(self._handle_clear_queue)
        self.batch_panel.runBatchClicked.connect(self.execute_batch_generation)
        self.batch_panel.sequencesReordered.connect(self._handle_sequences_reordered)
        self.batch_panel.queueItemsReordered.connect(self._handle_queue_reordered)

    @Slot(str, object)
    def _handle_copy_item(self, db_key_str: str, original_item_data: Any):
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in get_args(DatabaseKey) else None
        )
        if not db_key:
            return

        modal_type = self._get_modal_type_from_db_key(db_key)
        if not modal_type:
            return

        try:
            item_dict = original_item_data.__dict__.copy()

            if db_key == "costumes":
                if "color_palette" in item_dict:
                    item_dict["color_palette"] = [
                        ColorPaletteItem(**cp.__dict__)
                        for cp in item_dict.get("color_palette", [])
                    ]
                if "state_ids" in item_dict:
                    item_dict["state_ids"] = list(item_dict.get("state_ids", []))
            elif db_key == "cuts" and "roles" in item_dict:
                item_dict["roles"] = [
                    SceneRole(**r.__dict__) for r in item_dict.get("roles", [])
                ]
            elif db_key == "scenes":
                if "role_assignments" in item_dict:
                    item_dict["role_assignments"] = [
                        RoleAppearanceAssignment(
                            role_id=ra.role_id,
                            costume_ids=list(ra.costume_ids),
                            pose_ids=list(ra.pose_ids),
                            expression_ids=list(ra.expression_ids),
                        )
                        for ra in item_dict.get("role_assignments", [])
                    ]
                item_dict["state_categories"] = list(item_dict.get("state_categories", []))
                item_dict["additional_prompt_ids"] = list(item_dict.get("additional_prompt_ids", []))
                item_dict["composition_ids"] = list(item_dict.get("composition_ids", []))
                item_dict["sd_param_ids"] = list(item_dict.get("sd_param_ids", []))
            elif db_key == "sequences" and "scene_entries" in item_dict:
                item_dict["scene_entries"] = [
                    SequenceSceneEntry(**se.__dict__)
                    for se in item_dict.get("scene_entries", [])
                ]

            new_id_base = db_key[:-1] if db_key.endswith("s") else db_key
            item_dict["id"] = f"{new_id_base}_copy_{int(time.time() * 1000)}"
            # Copy generated objects must be treated as newly created for recent-first UI ordering.
            if "created_at" in item_dict:
                item_dict["created_at"] = time.time()

            if db_key == "works":
                item_dict["title_jp"] = f"{item_dict.get('title_jp', '')} (Copy)"
            else:
                item_dict["name"] = f"{item_dict.get('name', '')} (Copy)"

            copied_data = type(original_item_data)(**item_dict)
            self.open_edit_dialog(modal_type, copied_data)

        except Exception as e:
            QMessageBox.critical(self, "Copy Error", f"Failed to create copy: {e}")
            traceback.print_exc()

    @Slot(str, str)
    def _handle_add_new_item(self, db_key_str: str, modal_title: str):
        modal_type = self._get_modal_type_from_db_key(db_key_str)
        if modal_type:
            self.open_edit_dialog(modal_type, None)

    @Slot(str)
    def _handle_scene_change_and_save_config(self, new_scene_id: str):
        if self.current_scene_id == new_scene_id:
            return
            
        self.current_scene_id = new_scene_id
        self.generated_prompts = []
        self.update_prompt_display()
        self.appearance_overrides.clear()
        
        self.prompt_panel.set_assignments(self.actor_assignments)
        self.prompt_panel.set_current_scene(self.current_scene_id)
        self.prompt_panel._current_overrides = self.appearance_overrides

        self.data_handler.save_config(
            self.current_scene_id,
            self.actor_assignments,
            self.appearance_overrides,
            self.image_output_base_dir,
        )

    @Slot(dict)
    def _handle_assignment_change_and_save_config(self, new_assignments: dict):
        self.actor_assignments = new_assignments.copy()
        self.appearance_overrides = self.prompt_panel.get_current_overrides()
        self.generated_prompts = []
        self.update_prompt_display()
        self.data_handler.save_config(
            self.current_scene_id,
            self.actor_assignments,
            self.appearance_overrides,
            self.image_output_base_dir,
        )

    def closeEvent(self, event: QCloseEvent):
        self.data_handler.save_config(
            self.current_scene_id,
            self.actor_assignments,
            self.appearance_overrides,
            self.image_output_base_dir,
        )
        self.backend_manager.stop_backend()
        self.backend_thread.quit()
        self.submitter_thread.quit()
        self.backend_thread.wait(3000)
        self.submitter_thread.wait(3000)
        event.accept()

    @Slot()
    def _handle_import(self):
        import_result = self.data_handler.import_data()
        if not import_result:
            return

        self.db_data, self.batch_queue = import_result
        
        scenes_dict = self.db_data.get("scenes", {})
        self.current_scene_id = next(iter(scenes_dict), None)
        self.actor_assignments = {}
        self.appearance_overrides = {}
        self.generated_prompts = []

        self.update_ui_after_data_change()
        self.prompt_panel.set_current_scene(self.current_scene_id)
        self.prompt_panel.set_assignments(self.actor_assignments)
        self.prompt_panel._current_overrides = self.appearance_overrides
        self.update_prompt_display()


    @Slot(QListWidgetItem)
    def _handle_item_double_clicked(self, item: QListWidgetItem):
        if not item:
            return
        db_key = self.library_panel._current_db_key
        item_id = item.data(Qt.ItemDataRole.UserRole)

        if db_key and item_id and (item_data := self.db_data.get(db_key, {}).get(item_id)):
            if modal_type := self._get_modal_type_from_db_key(db_key):
                self.open_edit_dialog(modal_type, item_data)

    @Slot(str, str)
    def _handle_delete_item(self, db_key_str: str, item_id: str):
        self.delete_item(db_key_str, item_id)

    @Slot(str, object)
    def _handle_open_nested_editor(
        self,
        modal_type: str,
        initial_data: Optional[Any],
    ):
        self.open_edit_dialog(modal_type, initial_data)

    @Slot()
    def generate_prompts(self):
        if not self.current_scene_id:
            QMessageBox.warning(self, "Generate", "Please select a scene first.")
            return

        try:
            full_db = FullDatabase(**self.db_data)
            self.generated_prompts = generate_batch_prompts(
                scene_id=self.current_scene_id,
                actor_assignments=self.actor_assignments,
                appearance_overrides=self.appearance_overrides,
                db=full_db,
            )
            self.update_prompt_display()
        except Exception as e:
            QMessageBox.critical(self, "Generation Error", f"プロンプト生成中にエラーが発生しました: {e}")
            traceback.print_exc()

    @Slot()
    def _handle_start_backend(self):
        self.on_worker_log("Requesting to start backend...")
        self.start_backend_signal.emit(self.image_output_base_dir)

    def _submit_tasks(self, tasks: List[ImageGenerationTask]):
        if not tasks:
            QMessageBox.warning(self, "Submit Tasks", "No tasks were generated to submit.")
            return
        
        self.batch_panel.set_buttons_enabled(False)
        self.prompt_panel.execute_btn.setEnabled(False)
        self.batch_panel.set_status(f"Submitting {len(tasks)} tasks to the queue...", 0)
        self.submit_tasks_signal.emit(tasks)

    def _build_generation_metadata(
        self,
        cut: Cut,
        scene_name: str,
        sequence_name: str,
        actor_assignments: Dict[str, str],
    ) -> BatchMetadata:
        char_names: List[str] = []
        work_titles: List[str] = []
        seen_character_ids = set()
        seen_work_ids = set()

        for role in cut.roles:
            actor_id = actor_assignments.get(role.id)
            actor = self.db_data.get("actors", {}).get(actor_id) if actor_id else None
            char = (
                self.db_data.get("characters", {}).get(actor.character_id)
                if actor and actor.character_id
                else None
            )
            if not char:
                continue

            if char.id not in seen_character_ids:
                char_name = getattr(char, "name", "")
                if char_name:
                    char_names.append(char_name)
                seen_character_ids.add(char.id)

            work = self.db_data.get("works", {}).get(char.work_id) if char.work_id else None
            if work and work.id not in seen_work_ids:
                work_title = (
                    getattr(work, "title_file_safe_jp", "")
                    or getattr(work, "title_jp", "")
                    or getattr(work, "title_en", "")
                )
                if work_title:
                    work_titles.append(work_title)
                seen_work_ids.add(work.id)

        return BatchMetadata(
            sequence_name=sequence_name,
            scene_name=scene_name,
            main_character=char_names[0] if char_names else "",
            sub_characters=char_names[1:] if len(char_names) > 1 else [],
            work_titles=work_titles,
        )

    @Slot()
    def execute_generation(self):
        if not self.generated_prompts:
            QMessageBox.warning(self, "Execute", "先に 'Generate Prompt Preview' を実行してください。")
            return
        
        current_scene = self.db_data.get("scenes", {}).get(self.current_scene_id)
        if not current_scene or not current_scene.cut_id:
            return

        current_cut = self.db_data.get("cuts", {}).get(current_scene.cut_id)
        if not current_cut:
            return

        options_dialog = GenerationOptionsDialog(self)
        if options_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        batch_size, n_iter, seed = options_dialog.get_values()

        try:
            full_db = FullDatabase(**self.db_data)
            tasks = create_image_generation_tasks(
                generated_prompts=self.generated_prompts,
                cut=current_cut,
                scene=current_scene,
                db=full_db,
            )
            if not tasks: return
            metadata = self._build_generation_metadata(
                current_cut,
                getattr(current_scene, "name", "N/A"),
                "Test",
                self.actor_assignments,
            )
            
            is_debug = self.prompt_panel.is_debug_mode_enabled()
            for task in tasks:
                if is_debug:
                    task.steps = max(1, math.floor(task.steps * 0.7))
                    task.width = max(64, math.floor(task.width * 0.7))
                    task.height = max(64, math.floor(task.height * 0.7))
                task.batch_size, task.n_iter = batch_size, n_iter
                if seed != -1: task.seed = seed
                task.metadata = metadata

            self._submit_tasks(tasks)

        except Exception as e:
            QMessageBox.critical(self, "Execution Error", f"予期せぬエラーが発生しました: {e}")
            traceback.print_exc()

    def update_prompt_display(self):
        if not self.generated_prompts:
            self.prompt_display_area.setPlainText("Press 'Generate Prompt Preview' or run batch.")
            return
        
        display_text = ""
        for p in self.generated_prompts:
            actor_info = ""
            if p.firstActorInfo and (char := p.firstActorInfo.get("character")) and (work := p.firstActorInfo.get("work")):
                actor_info = f" ({getattr(work, 'title_jp', '')} - {getattr(char, 'name', '')})"
            display_text += f"--- {p.name} (Cut {p.cut}){actor_info} ---\nPositive:\n{p.positive}\n\nNegative:\n{p.negative}\n------------------------------------\n\n"
        self.prompt_display_area.setPlainText(display_text)

    def update_ui_after_data_change(self, updated_db_key: Optional[DatabaseKey] = None):
        # Library Panel
        current_item = self.library_panel.library_list_widget.currentItem()
        current_list_selection_id = current_item.data(Qt.ItemDataRole.UserRole) if current_item else None
        current_type_index = self.library_panel.library_type_combo.currentIndex()
        self.library_panel.set_data_reference(self.db_data)
        if current_type_index >= 0:
            self.library_panel.library_type_combo.blockSignals(True)
            self.library_panel.library_type_combo.setCurrentIndex(current_type_index)
            self.library_panel.library_type_combo.blockSignals(False)
            self.library_panel.update_list()
        if current_list_selection_id:
            self.library_panel.select_item_by_id(current_list_selection_id)

        # Prompt Panel
        self.prompt_panel.set_data_reference(self.db_data)
        if not updated_db_key or updated_db_key == "scenes":
            self.prompt_panel.set_assignments(self.actor_assignments)
            self.prompt_panel.update_scene_combo()
        elif updated_db_key in [
            "actors",
            "cuts",
            "characters",
            "works",
            "costumes",
            "poses",
            "expressions",
        ]:
            self.prompt_panel.set_assignments(self.actor_assignments)
            self.prompt_panel.build_role_assignment_ui()
            
        # Batch Panel
        self.batch_panel.set_data_reference(self.db_data.get("sequences", {}), self.batch_queue)

    def _on_editor_finished(self, editor_id: str):
        if editor_id in self.open_editors:
            # print(f"[DEBUG] Editor for {editor_id} finished. Removing from tracking.")
            del self.open_editors[editor_id]

    def open_edit_dialog(self, modal_type: str, item_data: Optional[Any]):
        dialog_info = self.editor_dialog_mapping.get(modal_type)
        if not dialog_info: return

        DialogClass, db_key = dialog_info

        if DialogClass == SequenceEditorDialog:
            dialog = SequenceEditorDialog(item_data, self.db_data, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                saved_data = dialog.get_data()
                if saved_data and (item_id_to_select := getattr(saved_data, "id", None)):
                    self.db_data[db_key][item_id_to_select] = saved_data
                    self.data_handler.save_single_item(db_key, saved_data)
                    self.update_ui_after_data_change(db_key)
                    if items := self.batch_panel.sequence_list.findItems(f"({item_id_to_select})", Qt.MatchFlag.MatchContains):
                        self.batch_panel.sequence_list.setCurrentItem(items[0])
            return

        editor_id = getattr(item_data, "id", None)
        if editor_id and editor_id in self.open_editors:
            self.open_editors[editor_id].activateWindow()
            self.open_editors[editor_id].raise_()
            return
        
        # 新規作成の場合は、毎回ユニークなIDを生成
        if not editor_id:
            editor_id = f"new_{modal_type}_{time.time()}"
            
        try:
            if DialogClass == SimplePartEditorDialog:
                dialog = DialogClass(item_data, modal_type, self.db_data, db_key, self)
            else:
                dialog = DialogClass(item_data, self.db_data, db_key, self)
            
            dialog.setProperty("editor_id", editor_id)

            if isinstance(dialog, BaseEditorDialog):
                dialog.request_open_editor.connect(self._handle_open_nested_editor)
                dialog.dataSaved.connect(self._handle_data_saved_from_dialog)
                dialog.finished.connect(lambda result, id=editor_id: self._on_editor_finished(id))

        except Exception as e:
            QMessageBox.critical(self, "Dialog Error", f"Failed to create dialog for {modal_type}: {e}")
            traceback.print_exc()
            return

        self.open_editors[editor_id] = dialog
        dialog.show()

    @Slot(str, object, object)
    def _handle_data_saved_from_dialog(self, db_key: str, saved_data: Any, original_data: Optional[Any]):
        """ダイアログからデータが保存されたときに呼び出されるスロット"""
        if saved_data and (item_id_to_select := getattr(saved_data, "id", None)):
            if db_key not in self.db_data: self.db_data[db_key] = {}
            is_new_item = original_data is None
            self.db_data[db_key][item_id_to_select] = saved_data
            self.data_handler.save_single_item(db_key, saved_data)
            
            # --- 他のエディタとメインウィンドウに更新を通知 ---
            self.update_ui_after_data_change(db_key)
            self.broadcast_data_update(db_key, saved_data, is_new_item)

            if db_key == "sequences":
                if items := self.batch_panel.sequence_list.findItems(f"({item_id_to_select})", Qt.MatchFlag.MatchContains):
                    self.batch_panel.sequence_list.setCurrentItem(items[0])
            else:
                self.library_panel.select_item_by_id(item_id_to_select)

    def broadcast_data_update(self, db_key: str, updated_item: Any, is_new: bool):
        """開いているすべてのエディタにデータ更新を通知する"""
        print(f"[DEBUG] Broadcasting update for {db_key} - {getattr(updated_item, 'id', 'N/A')}")
        for editor in self.open_editors.values():
            if isinstance(editor, BaseEditorDialog):
                editor.handle_external_data_update(db_key, updated_item, is_new)


    def _get_modal_type_from_db_key(self, db_key: str) -> Optional[str]:
        for modal_type, (_, key_str) in self.editor_dialog_mapping.items():
            if key_str == db_key:
                return modal_type
        return None

    def delete_item(self, db_key: DatabaseKey, item_id: str):
        if not (item_to_delete := self.db_data.get(db_key, {}).get(item_id)): return

        item_name = getattr(item_to_delete, "title_jp", getattr(item_to_delete, "name", item_id))
        if QMessageBox.question(self, "Confirm Deletion", f"本当に '{item_name}' ({item_id}) を削除しますか？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return

        deleted, queue_modified = self.data_handler.handle_delete_part(db_key, item_id, self.db_data, self.batch_queue)
        if deleted:
            try:
                db_delete_map = { "sequences": db.delete_sequence, "cuts": db.delete_cut, "sdParams": db.delete_sd_param, "works": db.delete_work, "characters": db.delete_character, "actors": db.delete_actor, "scenes": db.delete_scene, "costumes": db.delete_costume, "poses": db.delete_pose, "expressions": db.delete_expression, "backgrounds": db.delete_background, "lighting": db.delete_lighting, "compositions": db.delete_composition, "styles": db.delete_style, "state_categories": db.delete_state_category, "states": db.delete_state, "additional_prompts": db.delete_additional_prompt }
                if delete_func := db_delete_map.get(db_key):
                    delete_func(item_id)
            except Exception as e:
                QMessageBox.warning(self, "DB Error", f"DBからの削除中にエラー: {e}")

            if db_key == "actors":
                self.actor_assignments = {k: v for k, v in self.actor_assignments.items() if v != item_id}
                for q_item in self.batch_queue:
                    q_item.actor_assignments = {k: v for k, v in q_item.actor_assignments.items() if v != item_id}
                queue_modified = True
            
            if db_key == "scenes" and item_id == self.current_scene_id:
                self.current_scene_id = next(iter(self.db_data.get("scenes", {})), None)
                self.prompt_panel.set_current_scene(self.current_scene_id)
            
            if db_key == "cuts":
                for scene in self.db_data.get("scenes", {}).values():
                    if scene.cut_id == item_id:
                        scene.cut_id = None
                        db.save_scene(scene)

            self.update_ui_after_data_change()
            if queue_modified:
                self.data_handler.save_batch_queue(self.batch_queue)

    @Slot(str)
    def _handle_edit_sequence(self, sequence_id: str):
        if sequence_data := self.db_data.get("sequences", {}).get(sequence_id):
            self.open_edit_dialog("SEQUENCE", sequence_data)

    @Slot(str)
    def _handle_add_to_queue(self, sequence_id: str):
        if not (sequence := self.db_data.get("sequences", {}).get(sequence_id)): return

        initial_assignments = self.batch_queue[-1].actor_assignments.copy() if self.batch_queue else {}
        dialog = ActorAssignmentDialog(sequence, initial_assignments, {}, self.db_data, self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.data_handler.add_item_to_queue(
                sequence_id, dialog.get_assignments(), dialog.get_appearance_overrides(), self.batch_queue
            )
            self.batch_panel.update_queue_list()

    @Slot(str)
    def _handle_edit_queue_assignments(self, queue_item_id: str):
        item_to_edit = next((item for item in self.batch_queue if item.id == queue_item_id), None)
        if not item_to_edit or not (sequence := self.db_data.get("sequences", {}).get(item_to_edit.sequence_id)):
            return

        dialog = ActorAssignmentDialog(sequence, item_to_edit.actor_assignments, item_to_edit.appearance_overrides, self.db_data, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.data_handler.update_queue_item_assignments(queue_item_id, dialog.get_assignments(), dialog.get_appearance_overrides(), self.batch_queue)
            self.batch_panel.update_queue_list()

    @Slot(str)
    def _handle_remove_from_queue(self, queue_item_id: str):
        if self.data_handler.remove_item_from_queue(queue_item_id, self.batch_queue):
            self.batch_panel.update_queue_list()

    @Slot()
    def _handle_clear_queue(self):
        if QMessageBox.question(self, "Clear Queue", "Clear all items from the batch queue?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.batch_queue.clear()
            self.data_handler.save_batch_queue(self.batch_queue)
            self.batch_panel.update_queue_list()

    @Slot(list)
    def _handle_sequences_reordered(self, new_ordered_ids: list):
        pass

    @Slot(list)
    def _handle_queue_reordered(self, new_ordered_ids: list):
        self.data_handler.reorder_queue(new_ordered_ids, self.batch_queue)
        self.batch_panel.update_queue_list()

    @Slot()
    def execute_batch_generation(self):
        if not self.batch_queue:
            QMessageBox.information(self, "Batch Run", "No items in the batch queue.")
            return

        options_dialog = GenerationOptionsDialog(self)
        if options_dialog.exec() != QDialog.DialogCode.Accepted: return
        batch_size, n_iter, seed = options_dialog.get_values()
        
        try:
            full_db = FullDatabase(**self.db_data)
            all_tasks = []
            is_debug = self.prompt_panel.is_debug_mode_enabled()
            
            for item in self.batch_queue:
                sequence = self.db_data.get("sequences", {}).get(item.sequence_id)
                if not sequence: continue

                for scene_entry in sequence.scene_entries:
                    if not scene_entry.is_enabled: continue
                    scene = self.db_data.get("scenes", {}).get(scene_entry.scene_id)
                    cut = self.db_data.get("cuts", {}).get(scene.cut_id) if scene and scene.cut_id else None
                    if not scene or not cut: continue
                    
                    prompts = generate_batch_prompts(scene.id, item.actor_assignments, item.appearance_overrides, full_db)
                    tasks = create_image_generation_tasks(prompts, cut, scene, full_db)

                    metadata = self._build_generation_metadata(
                        cut,
                        getattr(scene, "name", "N/A"),
                        getattr(sequence, "name", "N/A"),
                        item.actor_assignments,
                    )
                    
                    for task in tasks:
                        if is_debug:
                            task.steps = max(1, math.floor(task.steps * 0.7))
                            task.width = max(64, math.floor(task.width * 0.7))
                            task.height = max(64, math.floor(task.height * 0.7))
                        task.batch_size, task.n_iter = batch_size, n_iter
                        if seed != -1: task.seed = seed
                        task.metadata = metadata # ★ タスクにメタデータを設定

                    all_tasks.extend(tasks)

            if all_tasks:
                self._submit_tasks(all_tasks)
            else:
                QMessageBox.information(self, "Batch Run", "No tasks to run.")

        except Exception as e:
            QMessageBox.critical(self, "Batch Run Error", f"An unexpected error occurred: {e}")
            traceback.print_exc()

    @Slot(bool, str)
    def on_submission_finished(self, success: bool, message: str):
        self.batch_panel.set_buttons_enabled(True)
        self.prompt_panel.execute_btn.setEnabled(True)
        
        final_message = f"Task Submission: {message}"
        msg_box = QMessageBox.information if success else QMessageBox.warning
        msg_box(self, "Task Submission", final_message)
        
        self.batch_panel.set_status("Idle. Waiting for new tasks.", 0)

    @Slot(str)
    def on_worker_log(self, message: str):
        print(f"[Worker] {message}")
        self.batch_panel.set_status(message)

    @Slot()
    def _handle_sync_csv(self):
        QMessageBox.information(self, "CSV同期 (1/2)", "まず、[作品 (Work)] のCSVファイルを選択してください。")
        work_file, _ = QFileDialog.getOpenFileName(self, "作品 (Work) のCSVファイルを選択", "", "CSV Files (*.csv)")
        if not work_file: return

        QMessageBox.information(self, "CSV同期 (2/2)", "次に、[キャラクター (Character)] のCSVファイルを選択してください。")
        char_file, _ = QFileDialog.getOpenFileName(self, "キャラクター (Character) のCSVファイルを選択", "", "CSV Files (*.csv)")
        if not char_file: return

        try:
            wc, wu, ws = self._sync_works_from_csv(work_file)
            cc, cu, cs, ac = self._sync_characters_from_csv(char_file)
            self.update_ui_after_data_change()
            QMessageBox.information(
                self,
                "同期完了",
                (
                    "CSV同期が完了しました。\n\n"
                    f"作品: 新規{wc}, スキップ(既存){ws}\n"
                    f"キャラクター: 新規{cc}, スキップ(既存){cu}, スキップ(作品不明){cs}\n"
                    f"Actor自動作成: 新規{ac}"
                ),
            )
        except Exception as e:
            QMessageBox.critical(self, "同期エラー", f"CSVの処理中にエラーが発生しました:\n{e}")
            traceback.print_exc()

    def _sync_works_from_csv(self, file_path: str) -> Tuple[int, int, int]:
        created_count, updated_count, skipped_count = 0, 0, 0
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = {h: i for i, h in enumerate(next(reader))}
            
            for row in reader:
                if not (work_id := row[header["ファイルセーフ英語"]]): continue
                
                is_new = work_id not in self.db_data.get("works", {})
                if not is_new:
                    skipped_count += 1
                    continue

                created_count += 1
                work_obj = Work(id=work_id)
                work_obj.title_jp = row[header["フルタイトル日本語"]]
                work_obj.title_en = row[header["フルタイトル英語"]]
                work_obj.sns_tags = row[header["ハッシュタグ英語"]]
                work_obj.tags = [row[header[h]] for h in ["ファイルセーフ日本語", "ファイルセーフ英語", "ショートタイトル日本語", "ショートタイトル英語", "ハッシュタグ日本語"] if row[header[h]]]
                
                db.save_work(work_obj)
                if "works" not in self.db_data: self.db_data["works"] = {}
                self.db_data["works"][work_id] = work_obj
        return created_count, updated_count, skipped_count

    def _sync_characters_from_csv(self, file_path: str) -> Tuple[int, int, int, int]:
        created, updated, skipped, actor_created = 0, 0, 0, 0
        work_map = {w.tags[0].strip(): w.id for w in self.db_data.get("works", {}).values() if w.tags}
        
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = {h: i for i, h in enumerate(next(reader))}
            
            for row in reader:
                if not (char_id := row[header["ファイルセーフ英語"]]): continue
                if not (work_id := work_map.get(row[header["登場作品"]].strip())):
                    skipped += 1
                    continue
                
                is_new = char_id not in self.db_data.get("characters", {})
                if not is_new:
                    updated += 1
                    continue

                created += 1
                char_obj = Character(id=char_id)
                char_obj.name = row[header["ファイルセーフ日本語"]]
                char_obj.work_id = work_id
                char_obj.tags = [row[header[h]] for h in ["フルネーム日本語", "フルネーム英語", "ショートネーム日本語", "ハッシュタグ日本語"] if row[header[h]]]
                
                db.save_character(char_obj)
                if "characters" not in self.db_data: self.db_data["characters"] = {}
                self.db_data["characters"][char_id] = char_obj

                # Characterに紐づくActorが未作成なら自動作成する
                if "actors" not in self.db_data:
                    self.db_data["actors"] = {}

                actors_dict = self.db_data.get("actors", {})
                has_linked_actor = any(
                    getattr(actor, "character_id", "") == char_id
                    for actor in actors_dict.values()
                )

                if not has_linked_actor:
                    base_actor_id = f"actor_{char_id}"
                    actor_id = base_actor_id
                    suffix = 1
                    while actor_id in actors_dict:
                        actor_id = f"{base_actor_id}_{suffix}"
                        suffix += 1

                    actor_obj = Actor(
                        id=actor_id,
                        name=char_obj.name or char_id,
                        character_id=char_id,
                    )
                    db.save_actor(actor_obj)
                    self.db_data["actors"][actor_id] = actor_obj
                    actor_created += 1

        return created, updated, skipped, actor_created

if __name__ == "__main__":
    app = QApplication(sys.argv)
    try:
        db.initialize_db()
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"FATAL: Could not start application: {e}")
        traceback.print_exc()
        sys.exit(1)