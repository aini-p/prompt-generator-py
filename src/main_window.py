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
    QTabWidget,
    QProgressBar,
    QFormLayout,
)
from PySide6.QtCore import Qt, Slot, QModelIndex, QMimeData
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent, QDragMoveEvent
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
    StableDiffusionParams,
    Cut,
    Sequence,
    SequenceSceneEntry,
    QueueItem,  # ★ 追加
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
from .panels.batch_panel import BatchPanel  # ★ 追加

# --- 編集ダイアログのインポート ---
from .widgets.actor_editor_dialog import ActorEditorDialog
from .widgets.scene_editor_dialog import SceneEditorDialog
from .widgets.direction_editor_dialog import DirectionEditorDialog
from .widgets.simple_part_editor_dialog import SimplePartEditorDialog
from .widgets.work_editor_dialog import WorkEditorDialog
from .widgets.character_editor_dialog import CharacterEditorDialog
from .widgets.costume_editor_dialog import CostumeEditorDialog
from .widgets.sd_params_editor_dialog import SDParamsEditorDialog
from .widgets.cut_editor_dialog import CutEditorDialog
from .widgets.sequence_editor_dialog import SequenceEditorDialog  # ★ 追加
from .widgets.actor_assignment_dialog import ActorAssignmentDialog  # ★ 追加

# ------------------------------------
from .prompt_generator import generate_batch_prompts, create_image_generation_tasks
from .batch_runner import run_stable_diffusion


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Object-Oriented Prompt Builder")
        self.setGeometry(100, 100, 1200, 800)

        # --- editor_dialog_mapping を修正 ---
        self.editor_dialog_mapping: Dict[str, Tuple[Type[QDialog], DatabaseKey]] = {
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
            "SDPARAMS": (SDParamsEditorDialog, "sdParams"),
            "SEQUENCE": (SequenceEditorDialog, "sequences"),  # ★ 追加
        }
        # --- ▲▲▲ 修正ここまで ▲▲▲ ---

        # --- データ関連 ---
        # ★ DataHandler 初期化の前に属性を定義しておく
        self.db_data: Dict[str, Dict[str, Any]] = {}
        self.batch_queue: List[QueueItem] = []
        self.current_scene_id: Optional[str] = None
        self.actor_assignments: Dict[str, str] = {}
        self.generated_prompts: List[GeneratedPrompt] = []

        self.data_handler = DataHandler(self)

        # --- データと設定の読み込みを修正 ---
        # ★ load_all_data の戻り値に合わせて修正
        _db_data, _batch_queue, initial_scene_id = self.data_handler.load_all_data()
        self.db_data = _db_data
        self.batch_queue = _batch_queue  # ロードしたキューを保持

        last_scene_id, last_assignments = self.data_handler.load_config()

        # --- 状態を初期化 ---
        # ★ ここで MainWindow の状態変数を確定させる
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
        # self.generated_prompts は上で初期化済み

        # --- UI要素 ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)  # 全体を左右に分割

        # --- 左パネル (タブ形式に変更) ---
        left_tab_widget = QTabWidget()
        left_tab_widget.setMinimumWidth(400)
        left_tab_widget.setMaximumWidth(600)

        # --- プロンプト生成タブ ---
        prompt_tab = QWidget()
        prompt_tab_layout = QVBoxLayout(prompt_tab)
        self.data_management_panel = DataManagementPanel()  # データ管理はここに入れる
        prompt_tab_layout.addWidget(self.data_management_panel)
        self.prompt_panel = PromptPanel()  # ★ パネル初期化
        self.prompt_panel.set_data_reference(self.db_data)  # ★ データ参照設定
        prompt_tab_layout.addWidget(self.prompt_panel)
        prompt_tab_layout.addStretch()
        left_tab_widget.addTab(prompt_tab, "Prompt Generation")

        # --- バッチ処理タブ ---
        self.batch_panel = BatchPanel()  # ★ 新しいパネル
        # ★ データ参照設定 (Sequence と Queue)
        self.batch_panel.set_data_reference(
            self.db_data.get("sequences", {}), self.batch_queue
        )
        left_tab_widget.addTab(self.batch_panel, "Batch (Sequence)")

        # --- ライブラリタブ ---
        self.library_panel = LibraryPanel()  # ★ パネル初期化
        self.library_panel.set_data_reference(self.db_data)  # ★ データ参照設定
        left_tab_widget.addTab(self.library_panel, "Library")

        # --- 右パネル (プロンプト表示エリア - 変更なし) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setMinimumWidth(500)
        prompt_display_group = QGroupBox(
            "Generated Prompts (Batch or Single)"
        )  # 名前変更
        prompt_display_layout = QVBoxLayout(prompt_display_group)
        self.prompt_display_area = QTextEdit()
        self.prompt_display_area.setReadOnly(True)
        prompt_display_layout.addWidget(self.prompt_display_area)
        right_layout.addWidget(prompt_display_group)

        # --- 全体のレイアウト (Splitter) ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_tab_widget)  # 左側はタブウィジェット
        splitter.addWidget(right_panel)
        splitter.setSizes([450, 750])
        main_layout.addWidget(splitter)

        # --- シグナル接続 (パネル初期化後に行う) ---
        self._connect_signals()

        # --- ★ UIパネルの初期状態設定 (MainWindow の状態確定後に行う) ---
        self.prompt_panel.set_current_scene(self.current_scene_id)
        self.prompt_panel.set_assignments(self.actor_assignments)
        self.update_prompt_display()  # ★ 最後に表示エリアを更新

    def _connect_signals(self):
        # Data Management Panel
        self.data_management_panel.saveClicked.connect(
            lambda: self.data_handler.save_all_data(
                self.db_data, self.batch_queue
            )  # ★ キューも渡す
        )
        self.data_management_panel.exportClicked.connect(
            lambda: self.data_handler.export_data(
                self.db_data, self.batch_queue
            )  # ★ キューも渡す
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

        # Library Panel
        self.library_panel.library_list_widget.itemDoubleClicked.connect(
            self._handle_item_double_clicked
        )
        self.library_panel.addNewItemClicked.connect(self._handle_add_new_item)
        self.library_panel.deleteItemClicked.connect(self._handle_delete_item)

        # --- ★ Batch Panel シグナル接続 ---
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
        self.batch_panel.runBatchClicked.connect(
            self.execute_batch_generation
        )  # ★ 新しいメソッド
        self.batch_panel.sequencesReordered.connect(
            self._handle_sequences_reordered
        )  # ★ D&D
        self.batch_panel.queueItemsReordered.connect(
            self._handle_queue_reordered
        )  # ★ D&D

    @Slot(str, str)
    def _handle_add_new_item(self, db_key_str: str, modal_title: str):
        """LibraryPanel の Add New ボタンに対応するスロット。"""
        # ★ DatabaseKey 型への変換を追加
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in get_args(DatabaseKey) else None
        )
        if not db_key:
            QMessageBox.critical(self, "Error", f"Invalid db_key '{db_key_str}'")
            return

        modal_type = self._get_modal_type_from_db_key(db_key)
        if modal_type:
            print(
                f"[DEBUG] Add New button clicked for type: {db_key_str} -> {modal_type}"
            )
            self.open_edit_dialog(modal_type, None)
        else:
            print(
                f"[DEBUG] Error: Cannot determine modal_type for db_key '{db_key_str}'"
            )

    @Slot(str)
    def _handle_scene_change_and_save_config(self, new_scene_id: str):
        print(f"[DEBUG] MainWindow received sceneChanged signal: {new_scene_id}")
        current_scene_id_before = self.current_scene_id
        self.current_scene_id = new_scene_id if new_scene_id else None
        if current_scene_id_before != self.current_scene_id:
            self.generated_prompts = []  # プロンプトプレビューをクリア
            self.update_prompt_display()
            self.data_handler.save_config(
                self.current_scene_id,
                self.current_style_id,
                self.actor_assignments,
                self.current_sd_param_id,
            )

    @Slot(dict)
    def _handle_assignment_change_and_save_config(self, new_assignments: dict):
        print(f"[DEBUG] MainWindow received assignmentChanged: {new_assignments}")
        self.actor_assignments = new_assignments.copy()
        self.generated_prompts = []  # プロンプトプレビューをクリア
        self.update_prompt_display()
        self.data_handler.save_config(
            self.current_scene_id,
            self.current_style_id,
            self.actor_assignments,
            self.current_sd_param_id,
        )

    def closeEvent(self, event: QCloseEvent):
        """アプリケーション終了時に設定を保存します。"""
        print("[DEBUG] MainWindow closing. Saving config...")
        self.data_handler.save_config(
            self.current_scene_id,
            self.current_style_id,
            self.actor_assignments,
            self.current_sd_param_id,
        )
        event.accept()

    # --- ▼▼▼ _handle_import を修正 ▼▼▼ ---
    @Slot()
    def _handle_import(self):
        """インポートボタンが押されたときの処理。"""
        # ★ 戻り値が変わった
        import_result = self.data_handler.import_data()
        if import_result:
            imported_db_data, imported_batch_queue = import_result
            self.db_data = imported_db_data
            self.batch_queue = imported_batch_queue  # ★ キューも更新

            # --- UI と状態の更新 ---
            self.library_panel.set_data_reference(self.db_data)
            self.prompt_panel.set_data_reference(self.db_data)
            # ★ Batch Panel も更新
            self.batch_panel.set_data_reference(
                self.db_data.get("sequences", {}), self.batch_queue
            )

            scenes_dict = self.db_data.get("scenes", {})
            new_scene_id = next(iter(scenes_dict), None)
            self.current_scene_id = new_scene_id
            self.actor_assignments = {}  # アサインメントはリセット
            self.generated_prompts = []  # プレビューもリセット

            # ★ UI更新メソッドを呼ぶ前にプロンプトパネルの状態を設定
            self.prompt_panel.set_current_scene(self.current_scene_id)
            self.prompt_panel.set_current_style(self.current_style_id)
            self.prompt_panel.set_current_sd_params(self.current_sd_param_id)
            self.prompt_panel.set_assignments(
                self.actor_assignments
            )  # リセットされたものを渡す

            self.update_ui_after_data_change()  # UI全体更新 (リストなど)
            self.update_prompt_display()  # プロンプト表示エリア更新

    # --- ▲▲▲ 修正ここまで ▲▲▲ ---

    @Slot(QListWidgetItem)
    def _handle_item_double_clicked(self, item: QListWidgetItem):
        """LibraryPanel のリスト項目がダブルクリックされたときの処理。"""
        if not item:
            return
        # ★ _current_db_key が None の可能性を考慮
        db_key_str = self.library_panel._current_db_key
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in get_args(DatabaseKey) else None
        )
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
        self.delete_item(db_key, item_id)  # ★ delete_item メソッドを呼び出す

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
        """プロンプト生成を実行します (単一シーン用)。"""
        # (このメソッドの実装は変更なし)
        current_scene = self.db_data.get("scenes", {}).get(self.current_scene_id)
        if not current_scene:
            QMessageBox.warning(self, "Generate", "Please select a scene first.")
            return
        # ... (以降の Cut 取得、Role チェック、generate_batch_prompts 呼び出しは同じ) ...
        # ... (エラーハンドリングも同じ) ...
        try:
            full_db = FullDatabase(**self.db_data)
            # generate_batch_prompts はシーンIDを受け取るのでそのまま使える
            self.generated_prompts = generate_batch_prompts(
                scene_id=self.current_scene_id,
                actor_assignments=self.actor_assignments,
                db=full_db,
            )
            self.update_prompt_display()  # 結果を表示
        except Exception as e:
            QMessageBox.critical(
                self, "Generation Error", f"プロンプト生成中にエラーが発生しました: {e}"
            )
            print(f"[DEBUG] Prompt generation error: {e}")
            traceback.print_exc()

    @Slot()
    def execute_generation(self):
        """画像生成を実行します (単一シーン用)。"""
        # (このメソッドの実装は変更なし)
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
            # ▼▼▼ SD Params を Scene から取得 ▼▼▼
            sd_param_id = getattr(current_scene, "sd_param_id", None)
            current_sd_params = (
                self.db_data.get("sdParams", {}).get(sd_param_id)
                if sd_param_id
                else None
            )

            if not current_sd_params:
                # フォールバック処理 (IDが見つからないか、シーンに設定されていない場合)
                current_sd_params = next(
                    iter(self.db_data.get("sdParams", {}).values()),
                    StableDiffusionParams(
                        id="default_fallback", name="Default Fallback"
                    ),
                )
                print(
                    f"[WARN] SD Params not found for scene or globally, using fallback: {current_sd_params.name}"
                )
            # ▲▲▲ 修正ここまで ▲▲▲

            # ▼▼▼ create_image_generation_tasks に FullDatabase を渡す ▼▼▼
            full_db = FullDatabase(**self.db_data)
            tasks = create_image_generation_tasks(
                generated_prompts=self.generated_prompts,
                scene=current_scene,
                db=full_db,  # ★ FullDatabase を渡す
                # sd_params=current_sd_params, # ← 削除
            )
            # ▲▲▲ 修正ここまで ▲▲▲
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
        # (このメソッドの実装は変更なし)
        print("[DEBUG] update_prompt_display called.")
        if not self.generated_prompts:
            self.prompt_display_area.setPlainText(
                "Press 'Generate Prompt Preview' or run batch."
            )
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
            # ★ cut 属性はグローバルインデックスになったので注意
            display_text += f"--- {p.name} (Cut {p.cut}){actor_info_str} ---\nPositive:\n{p.positive}\n\nNegative:\n{p.negative}\n------------------------------------\n\n"
        self.prompt_display_area.setPlainText(display_text)
        print("[DEBUG] Prompt display area updated.")

    # --- ▼▼▼ UI更新メソッド修正 ▼▼▼ ---
    def update_ui_after_data_change(self):
        """データ変更（インポート、新規追加、削除など）後にUI全体を更新します。キューも更新します。"""
        print("[DEBUG] update_ui_after_data_change called.")
        # --- LibraryPanel 更新 ---
        current_list_selection_id = None
        current_item = self.library_panel.library_list_widget.currentItem()
        if current_item:
            current_list_selection_id = current_item.data(Qt.ItemDataRole.UserRole)
        current_type_index = self.library_panel.library_type_combo.currentIndex()

        self.library_panel.set_data_reference(self.db_data)  # データ参照更新

        if current_type_index >= 0:
            self.library_panel.library_type_combo.blockSignals(True)
            self.library_panel.library_type_combo.setCurrentIndex(current_type_index)
            self.library_panel.library_type_combo.blockSignals(False)
            self.library_panel.update_list()  # リスト内容更新

        if current_list_selection_id:
            self.library_panel.select_item_by_id(current_list_selection_id)  # 選択復元

        # --- PromptPanel 更新 ---
        self.prompt_panel.set_data_reference(
            self.db_data
        )  # データ参照更新 (コンボボックス更新のため)
        # prompt_panel の現在の選択状態は MainWindow が持っているので、ここでは set_current_* は呼ばない

        # --- ★ Batch Panel のデータ参照も更新 ---
        self.batch_panel.set_data_reference(
            self.db_data.get("sequences", {}), self.batch_queue
        )

        print("[DEBUG] update_ui_after_data_change complete.")

    # --- ▲▲▲ 修正ここまで ▲▲▲ ---

    # --- ▼▼▼ open_edit_dialog を修正 ▼▼▼ ---
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
        # ★ db_key_str から DatabaseKey 型へ変換
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in get_args(DatabaseKey) else None
        )
        if not db_key:
            QMessageBox.critical(
                self, "Error", f"Internal error: Invalid db_key '{db_key_str}'..."
            )
            return

        print(
            f"[DEBUG] Opening editor dialog for type: {modal_type}, DB key: {db_key}, Data: {'Exists' if item_data else 'None'}"
        )
        dialog: Optional[QDialog] = None
        try:
            # --- ダイアログクラスに応じて初期化 ---
            if DialogClass == SequenceEditorDialog:  # ★ Sequence 用
                dialog = DialogClass(item_data, self.db_data, self)
            elif DialogClass == SimplePartEditorDialog:
                dialog = DialogClass(item_data, modal_type, self.db_data, self)
            elif DialogClass in [
                CutEditorDialog,
                SDParamsEditorDialog,
            ]:  # db_dict のみ必要なクラス
                dialog = DialogClass(item_data, self.db_data, self)
            elif issubclass(
                DialogClass, BaseEditorDialog
            ):  # BaseEditorDialog を継承する標準的なクラス
                dialog = DialogClass(item_data, self.db_data, self)
            else:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Dialog class {DialogClass.__name__} is not properly configured.",
                )
                return

            # --- BaseEditorDialog を継承している場合のみシグナル接続 ---
            if isinstance(dialog, BaseEditorDialog):
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
                saved_data = None
                # --- ダイアログの種類に応じてデータ取得方法を切り替え ---
                if isinstance(dialog, BaseEditorDialog):
                    saved_data = dialog.saved_data
                elif isinstance(dialog, SequenceEditorDialog):
                    saved_data = dialog.get_data()  # get_data() を呼ぶ

                if saved_data:
                    item_id_to_select = getattr(saved_data, "id", None)
                    print(
                        f"[DEBUG] Dialog returned data: {item_id_to_select} of type {type(saved_data).__name__}."
                    )

                    # --- SimplePartEditorDialog の型変換処理 ---
                    if isinstance(dialog, SimplePartEditorDialog) and isinstance(
                        saved_data, PromptPartBase
                    ):
                        target_class: Optional[Type[PromptPartBase]] = None
                        if db_key == "poses":
                            target_class = Pose
                        elif db_key == "expressions":
                            target_class = Expression
                        # ... (他の SimplePart の elif) ...
                        elif db_key == "styles":
                            target_class = Style

                        if target_class:
                            try:
                                saved_data = target_class(**saved_data.__dict__)
                            except TypeError as e:
                                print(f"[ERROR] Failed to convert SimplePart data: {e}")
                                saved_data = None
                        else:
                            print(
                                f"[ERROR] Unknown db_key '{db_key}' for SimplePart conversion."
                            )
                            saved_data = None

                    if saved_data and item_id_to_select:
                        # 1. メモリに追加/更新
                        if db_key == "sequences":  # ★ Sequence をメモリに追加/更新
                            if "sequences" not in self.db_data:
                                self.db_data["sequences"] = {}
                            self.db_data["sequences"][item_id_to_select] = saved_data
                            print(
                                f"[DEBUG] Sequence {item_id_to_select} saved/updated in memory."
                            )
                        # ... (既存の elif db_key == "cuts", "sdParams" など) ...
                        elif db_key in get_args(DatabaseKey):  # 有効なキーか確認
                            if db_key not in self.db_data:
                                self.db_data[
                                    db_key
                                ] = {}  # 初めてのキーなら辞書を初期化
                            self.db_data[db_key][item_id_to_select] = saved_data
                        else:
                            print(f"[ERROR] Invalid db_key '{db_key}'...")
                            return

                        # 2. DBに即時保存
                        try:
                            # ★ db_key に応じた保存関数を呼び出す
                            if db_key == "sequences":
                                db.save_sequence(saved_data)
                            elif db_key == "cuts":
                                db.save_cut(saved_data)
                            elif db_key == "sdParams":
                                db.save_sd_param(saved_data)
                            # ... (他の elif) ...
                            else:  # SimplePart や Actor など、汎用ハンドラを使うもの
                                self.data_handler.save_single_item(db_key, saved_data)
                        except Exception as db_save_e:
                            print(
                                f"[ERROR] Failed to save item {item_id_to_select} to DB: {db_save_e}"
                            )

                        # 3. UI更新
                        if (
                            target_widget_to_update
                        ):  # ネストされたダイアログからのコールバック
                            # --- 親ダイアログのコンボボックス更新処理 ---
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
                        else:  # メインウィンドウからの直接呼び出し
                            self.update_ui_after_data_change()  # UI全体更新
                            if item_id_to_select:
                                # ★ 更新されたリストでアイテムを選択
                                if db_key == "sequences":
                                    self.batch_panel.sequence_list.blockSignals(True)
                                    items = self.batch_panel.sequence_list.findItems(
                                        f"({item_id_to_select})",
                                        Qt.MatchFlag.MatchContains,
                                    )
                                    if items:
                                        self.batch_panel.sequence_list.setCurrentItem(
                                            items[0]
                                        )
                                    self.batch_panel.sequence_list.blockSignals(False)
                                else:  # LibraryPanel のリストを選択
                                    self.library_panel.select_item_by_id(
                                        item_id_to_select
                                    )
                    elif not saved_data:
                        QMessageBox.warning(
                            self, "Save Error", "データの保存に失敗しました。"
                        )
                else:
                    print("[DEBUG] Dialog accepted but returned no valid data.")
            else:
                print("[DEBUG] Dialog cancelled or closed.")

    # --- ▲▲▲ 修正ここまで ▲▲▲ ---

    def _get_modal_type_from_db_key(
        self, db_key: Optional[DatabaseKey]
    ) -> Optional[str]:
        # (このメソッドの実装は変更なし)
        if not db_key:
            return None
        for modal_type, (dialog_class, key_str) in self.editor_dialog_mapping.items():
            if key_str == db_key:
                return modal_type
        return None

    # --- ▼▼▼ delete_item を修正 ▼▼▼ ---
    def delete_item(self, db_key: DatabaseKey, item_id: str):
        item_to_delete = self.db_data.get(db_key, {}).get(item_id)
        if not item_to_delete:
            QMessageBox.warning(self, "Error", f"Item {item_id} not found in {db_key}.")
            return

        item_name = getattr(item_to_delete, "title_jp", None) or getattr(
            item_to_delete, "name", item_id
        )

        confirm = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"本当に '{item_name}' ({item_id}) を削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            # ★ handle_delete_part の呼び出しと戻り値を変更
            deleted_from_memory, queue_modified = self.data_handler.handle_delete_part(
                db_key, item_id, self.db_data, self.batch_queue
            )

            if deleted_from_memory:
                try:
                    # --- DB削除処理 ---
                    if db_key == "sequences":
                        db.delete_sequence(item_id)
                    elif db_key == "cuts":
                        db.delete_cut(item_id)
                    elif db_key == "sdParams":
                        db.delete_sd_param(item_id)
                    elif db_key == "works":
                        db.delete_work(item_id)
                    elif db_key == "characters":
                        db.delete_character(item_id)
                    elif db_key == "actors":
                        db.delete_actor(item_id)
                    elif db_key == "scenes":
                        db.delete_scene(item_id)
                    elif db_key == "directions":
                        db.delete_direction(item_id)
                    elif db_key == "costumes":
                        db.delete_costume(item_id)
                    elif db_key == "poses":
                        db.delete_pose(item_id)
                    elif db_key == "expressions":
                        db.delete_expression(item_id)
                    elif db_key == "backgrounds":
                        db.delete_background(item_id)
                    elif db_key == "lighting":
                        db.delete_lighting(item_id)
                    elif db_key == "compositions":
                        db.delete_composition(item_id)
                    elif db_key == "styles":
                        db.delete_style(item_id)
                    else:  # 念のため
                        db._delete_item(db_key, item_id)
                    print(
                        f"[DEBUG] Item {item_id} deleted from database table '{db_key}'."
                    )
                except Exception as db_del_e:
                    QMessageBox.warning(
                        self, "DB Error", f"DBからの削除中にエラー: {db_del_e}"
                    )
                    print(
                        f"[ERROR] Failed to delete item {item_id} from DB: {db_del_e}"
                    )
                    # メモリ上は削除されているのでUI更新は行う

                # --- 関連データの更新 (メモリ上) ---
                if db_key == "actors":
                    # アサインメントから削除
                    self.actor_assignments = {
                        k: v for k, v in self.actor_assignments.items() if v != item_id
                    }
                    # キュー内のアサインメントからも削除
                    for q_item in self.batch_queue:
                        q_item.actor_assignments = {
                            k: v
                            for k, v in q_item.actor_assignments.items()
                            if v != item_id
                        }
                    queue_modified = True  # キューが変更された可能性がある

                if db_key == "scenes" and item_id == self.current_scene_id:
                    # 現在選択中のシーンが削除されたらリセット
                    self.current_scene_id = next(
                        iter(self.db_data.get("scenes", {})), None
                    )
                    self.prompt_panel.set_current_scene(
                        self.current_scene_id
                    )  # UIも更新
                if db_key == "cuts":
                    # このカットを使っているシーンの cut_id を None に
                    for scene in self.db_data.get("scenes", {}).values():
                        if scene.cut_id == item_id:
                            scene.cut_id = None
                            # DBも更新 (即時反映)
                            try:
                                db.save_scene(scene)
                            except Exception as e_scene:
                                print(
                                    f"Error updating scene after cut deletion: {e_scene}"
                                )
                if db_key == "sdParams" and item_id == self.current_sd_param_id:
                    # 現在選択中のSD Paramが削除されたらリセット
                    self.current_sd_param_id = next(
                        iter(self.db_data.get("sdParams", {})), None
                    )
                    self.prompt_panel.set_current_sd_params(
                        self.current_sd_param_id
                    )  # UIも更新
                # ToDo: 他の関連データ (例: Work削除時のCharacterなど) も必要に応じて更新

                self.update_ui_after_data_change()  # UI全体更新
                # ★ キューが変更された場合、DBに保存 (handle_delete_part 内で行われるように変更しても良い)
                if queue_modified:
                    self.data_handler.save_batch_queue(self.batch_queue)

            else:
                QMessageBox.warning(
                    self, "Error", f"Failed to delete {item_name} from memory."
                )
        else:
            print(f"[DEBUG] Deletion cancelled by user for {item_id}.")

    # --- ▲▲▲ 修正ここまで ▲▲▲ ---

    # --- ▼▼▼ Sequence / Queue 関連のスロット ▼▼▼ ---
    @Slot(str)
    def _handle_edit_sequence(self, sequence_id: str):
        sequence_data = self.db_data.get("sequences", {}).get(sequence_id)
        if sequence_data:
            self.open_edit_dialog("SEQUENCE", sequence_data)
        else:
            QMessageBox.warning(self, "Error", f"Sequence {sequence_id} not found.")

    @Slot(str)
    def _handle_add_to_queue(self, sequence_id: str):
        sequence = self.db_data.get("sequences", {}).get(sequence_id)
        if not sequence:
            QMessageBox.warning(self, "Error", f"Sequence {sequence_id} not found.")
            return

        initial_assignments = {}
        if self.batch_queue:
            last_item_same_seq = next(
                (
                    item
                    for item in reversed(self.batch_queue)
                    if item.sequence_id == sequence_id
                ),
                None,
            )
            if last_item_same_seq:
                initial_assignments = last_item_same_seq.actor_assignments.copy()
            else:
                initial_assignments = self.batch_queue[-1].actor_assignments.copy()

        dialog = ActorAssignmentDialog(
            sequence, initial_assignments, self.db_data, self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            final_assignments = dialog.get_assignments()
            self.data_handler.add_item_to_queue(
                sequence_id, final_assignments, self.batch_queue
            )
            self.batch_panel.update_queue_list()

    @Slot(str)
    def _handle_edit_queue_assignments(self, queue_item_id: str):
        item_to_edit = next(
            (item for item in self.batch_queue if item.id == queue_item_id), None
        )
        if not item_to_edit:
            QMessageBox.warning(self, "Error", f"Queue item {queue_item_id} not found.")
            return
        sequence = self.db_data.get("sequences", {}).get(item_to_edit.sequence_id)
        if not sequence:
            QMessageBox.warning(
                self,
                "Error",
                f"Sequence {item_to_edit.sequence_id} not found for queue item.",
            )
            return

        dialog = ActorAssignmentDialog(
            sequence, item_to_edit.actor_assignments, self.db_data, self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_assignments = dialog.get_assignments()
            self.data_handler.update_queue_item_assignments(
                queue_item_id, new_assignments, self.batch_queue
            )
            self.batch_panel.update_queue_list()  # 表示内容が変わるかもしれないので更新

    @Slot(str)
    def _handle_remove_from_queue(self, queue_item_id: str):
        if self.data_handler.remove_item_from_queue(queue_item_id, self.batch_queue):
            self.batch_panel.update_queue_list()

    @Slot()
    def _handle_clear_queue(self):
        confirm = QMessageBox.question(
            self,
            "Clear Queue",
            "Clear all items from the batch queue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.batch_queue.clear()
            self.data_handler.save_batch_queue(self.batch_queue)  # DBもクリア
            self.batch_panel.update_queue_list()

    @Slot(list)
    def _handle_sequences_reordered(self, new_ordered_ids: list):
        # シーケンス自体の永続的な順序は保存しない方針
        print(f"[DEBUG] Sequences reordered in UI (not saved): {new_ordered_ids}")
        pass

    @Slot(list)
    def _handle_queue_reordered(self, new_ordered_ids: list):
        print(f"[DEBUG] Queue reordered: {new_ordered_ids}")
        self.data_handler.reorder_queue(new_ordered_ids, self.batch_queue)
        self.batch_panel.update_queue_list()  # UI更新して新しい順序を反映

    @Slot()
    def execute_batch_generation(self):
        """バッチキューを実行します。"""
        if not self.batch_queue:
            QMessageBox.information(self, "Batch Run", "Batch queue is empty.")
            return

        total_scenes_to_process = 0
        sequences_data = self.db_data.get("sequences", {})
        scenes_data = self.db_data.get("scenes", {})
        for item in self.batch_queue:
            sequence = sequences_data.get(item.sequence_id)
            if sequence:
                total_scenes_to_process += sum(
                    1 for entry in sequence.scene_entries if entry.is_enabled
                )

        if total_scenes_to_process == 0:
            QMessageBox.warning(
                self, "Batch Run", "No enabled scenes found in the queue."
            )
            return

        self.batch_panel.set_buttons_enabled(False)  # 実行中はボタン無効化
        self.batch_panel.set_status("Starting batch generation...", 0)
        QApplication.processEvents()  # UI更新を強制

        all_tasks: List[ImageGenerationTask] = []
        full_db = FullDatabase(**self.db_data)  # プロンプト生成用にDB全体を渡す
        processed_scenes_count = 0
        global_prompt_index = 1  # 全プロンプトの通し番号

        try:
            for queue_item in self.batch_queue:
                sequence = sequences_data.get(queue_item.sequence_id)
                if not sequence:
                    print(
                        f"[WARN] Sequence {queue_item.sequence_id} not found, skipping."
                    )
                    continue

                self.batch_panel.set_status(f"Processing Sequence: {sequence.name}...")
                QApplication.processEvents()

                # シーケンス内の有効なシーンを順番に処理
                for scene_entry in sequence.scene_entries:
                    if not scene_entry.is_enabled:
                        continue

                    scene_id = scene_entry.scene_id
                    scene = scenes_data.get(scene_id)
                    if not scene:
                        print(f"[WARN] Scene {scene_id} not found, skipping.")
                        continue

                    # 1. プロンプト生成
                    prompts_for_scene = generate_batch_prompts(
                        scene_id=scene_id,
                        actor_assignments=queue_item.actor_assignments,
                        db=full_db,
                    )

                    # 2. タスク生成
                    # cut インデックスをグローバルに
                    for i, prompt_data in enumerate(prompts_for_scene):
                        prompt_data.cut = global_prompt_index + i

                    tasks_for_scene = create_image_generation_tasks(
                        generated_prompts=prompts_for_scene,
                        scene=scene,  # Scene オブジェクトを渡す
                        db=full_db,  # FullDatabase を渡す
                    )
                    all_tasks.extend(tasks_for_scene)
                    global_prompt_index += len(prompts_for_scene)

                    processed_scenes_count += 1
                    progress = int(
                        (processed_scenes_count / total_scenes_to_process) * 95
                    )  # 95% まで進める
                    self.batch_panel.set_status(
                        f"Generated tasks for Scene: {scene.name}", progress
                    )
                    QApplication.processEvents()

            # 3. バッチ実行
            if not all_tasks:
                QMessageBox.warning(self, "Batch Run", "No tasks generated.")
                self.batch_panel.set_buttons_enabled(True)
                self.batch_panel.set_status("Idle", 0)
                return

            self.batch_panel.set_status(
                f"Running Stable Diffusion for {len(all_tasks)} tasks...", 95
            )
            QApplication.processEvents()

            success, message = run_stable_diffusion(all_tasks)

            if success:
                QMessageBox.information(self, "Batch Run Complete", message)
                self.batch_panel.set_status("Batch completed.", 100)
                # オプション: 成功したらキューをクリア
                # self.batch_queue.clear()
                # self.data_handler.save_batch_queue(self.batch_queue)
                # self.batch_panel.update_queue_list()
            else:
                QMessageBox.critical(self, "Batch Run Error", message)
                self.batch_panel.set_status(f"Error: {message}", 0)

        except Exception as e:
            QMessageBox.critical(
                self, "Batch Run Error", f"An unexpected error occurred: {e}"
            )
            print(f"[ERROR] Batch execution failed: {e}")
            traceback.print_exc()
            self.batch_panel.set_status(f"Error: {e}", 0)
        finally:
            self.batch_panel.set_buttons_enabled(True)  # ボタンを再度有効化
            # 完了後、少し待ってからアイドル状態に戻すなどの処理も可
            # self.batch_panel.set_status("Idle", 0)


# --- (main 関数実行部分は変更なし) ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    try:
        db.initialize_db()
    except Exception as e:
        print(f"FATAL: Could not initialize database: {e}")
        traceback.print_exc()  # ★ 詳細表示
        sys.exit(1)
    try:
        window = MainWindow()
        window.show()
    except Exception as e:
        print(f"FATAL: Could not create main window: {e}")
        traceback.print_exc()
        sys.exit(1)
    sys.exit(app.exec())
