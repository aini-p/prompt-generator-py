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
    Character,
    Style,  # Style もインポート
)
from typing import Dict, Optional, Any, List, Tuple, Literal, Union, TypeAlias, get_args

# --- パネルとハンドラをインポート ---
from .handlers.data_handler import DataHandler
from .panels.library_panel import LibraryPanel

# --- ▼▼▼ InspectorPanel のインポートを削除 ▼▼▼ ---
# from .panels.inspector_panel import InspectorPanel
# --- ▲▲▲ 削除ここまで ▲▲▲ ---
from .panels.prompt_panel import PromptPanel
from .panels.data_management_panel import DataManagementPanel

# --- ▼▼▼ 編集ダイアログのインポートに変更 ▼▼▼ ---
from .widgets.actor_editor_dialog import (
    ActorEditorDialog,
)  # (add_actor_form.py をリネーム・修正したもの)
from .widgets.scene_editor_dialog import (
    SceneEditorDialog,
)  # (add_scene_form.py をリネーム・修正したもの)
from .widgets.direction_editor_dialog import (
    DirectionEditorDialog,
)  # (add_direction_form.py をリネーム・修正したもの)
from .widgets.simple_part_editor_dialog import (
    SimplePartEditorDialog,
)  # (add_simple_part_form.py をリネーム・修正したもの)
from .widgets.work_editor_dialog import (
    WorkEditorDialog,
)  # (add_work_form.py をリネーム・修正したもの)
from .widgets.character_editor_dialog import (
    CharacterEditorDialog,
)  # (add_character_form.py をリネーム・修正したもの)
from .widgets.costume_editor_dialog import CostumeEditorDialog  # (新規作成したもの)
# --- ▲▲▲ 変更ここまで ▲▲▲ ---

# ------------------------------------
from .prompt_generator import generate_batch_prompts, create_image_generation_tasks
from .batch_runner import run_stable_diffusion


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Object-Oriented Prompt Builder")
        self.setGeometry(100, 100, 1200, 800)  # 少し幅を狭める

        # --- ▼▼▼ form_mapping を editor_dialog_mapping に変更 ▼▼▼ ---
        self.editor_dialog_mapping = {
            "WORK": (WorkEditorDialog, "works"),
            "CHARACTER": (CharacterEditorDialog, "characters"),
            "ACTOR": (ActorEditorDialog, "actors"),
            "SCENE": (SceneEditorDialog, "scenes"),
            "DIRECTION": (DirectionEditorDialog, "directions"),
            "COSTUME": (CostumeEditorDialog, "costumes"),
            "POSE": (SimplePartEditorDialog, "poses"),
            "EXPRESSION": (SimplePartEditorDialog, "expressions"),
            "BACKGROUND": (SimplePartEditorDialog, "backgrounds"),
            "LIGHTING": (SimplePartEditorDialog, "lighting"),
            "COMPOSITION": (SimplePartEditorDialog, "compositions"),
            "STYLE": (SimplePartEditorDialog, "styles"),
        }
        # --- ▲▲▲ 変更ここまで ▲▲▲ ---

        # --- データ関連 (変更なし) ---
        self.db_data: Dict[str, Dict[str, Any]] = {}
        self.sd_params: StableDiffusionParams = StableDiffusionParams()
        self.data_handler = DataHandler(self)
        self.db_data, self.sd_params, initial_scene_id = (
            self.data_handler.load_all_data()
        )
        self.current_scene_id: Optional[str] = initial_scene_id
        self.current_style_id: Optional[str] = None  # Style も初期化
        self.actor_assignments: Dict[str, str] = {}
        self.generated_prompts: List[GeneratedPrompt] = []

        # --- UI要素 ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # --- ▼▼▼ 左パネルと右パネルの構成を変更 ▼▼▼ ---
        # 左パネル (Library, Prompt, Data Management)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(400)
        left_panel.setMaximumWidth(600)

        self.data_management_panel = DataManagementPanel()
        left_layout.addWidget(self.data_management_panel)

        self.prompt_panel = PromptPanel()
        self.prompt_panel.set_data_reference(self.db_data)  # actor_assignments は不要に
        left_layout.addWidget(self.prompt_panel)

        self.library_panel = LibraryPanel()
        # SD Params は直接編集しないので library_panel には渡さない
        self.library_panel.set_data_reference(self.db_data)
        left_layout.addWidget(self.library_panel)

        left_layout.addStretch()

        # 右パネル (プロンプト表示エリアのみ)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setMinimumWidth(500)  # 幅調整

        prompt_display_group = QGroupBox("Generated Prompts (Batch)")
        prompt_display_layout = QVBoxLayout(prompt_display_group)
        self.prompt_display_area = QTextEdit()
        self.prompt_display_area.setReadOnly(True)
        prompt_display_layout.addWidget(self.prompt_display_area)
        right_layout.addWidget(prompt_display_group)

        # スプリッターで左右を分割
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([450, 750])  # サイズ調整
        main_layout.addWidget(splitter)
        # --- ▲▲▲ 変更ここまで ▲▲▲ ---

        # --- シグナル接続 ---
        self._connect_signals()

        # --- 初期UI状態設定 ---
        self.prompt_panel.set_current_scene(self.current_scene_id)
        # Style も初期設定 (None の場合、コンボボックスで "(None)" が選択される)
        self.prompt_panel.set_current_style(self.current_style_id)
        self.update_prompt_display()  # 初期プロンプト表示

    def _connect_signals(self):
        """パネル間のシグナルを接続します。"""
        # Data Management Panel (変更なし)
        self.data_management_panel.saveClicked.connect(
            lambda: self.data_handler.save_all_data(self.db_data, self.sd_params)
        )
        self.data_management_panel.exportClicked.connect(
            lambda: self.data_handler.export_data(self.db_data, self.sd_params)
        )
        self.data_management_panel.importClicked.connect(self._handle_import)

        # Prompt Panel (変更なし)
        self.prompt_panel.generatePromptsClicked.connect(self.generate_prompts)
        self.prompt_panel.executeGenerationClicked.connect(self.execute_generation)
        self.prompt_panel.sceneChanged.connect(self._handle_scene_change)
        self.prompt_panel.assignmentChanged.connect(self._handle_assignment_change)
        self.prompt_panel.styleChanged.connect(self._handle_style_change)

        # Library Panel
        # --- ▼▼▼ itemSelected を削除し、itemDoubleClicked を追加 ▼▼▼ ---
        # self.library_panel.itemSelected.connect(self.inspector_panel.update_inspector)
        self.library_panel.library_list_widget.itemDoubleClicked.connect(
            self._handle_item_double_clicked
        )
        # self.library_panel.itemSelectionCleared.connect(self.inspector_panel.clear_inspector) # 不要
        # --- ▲▲▲ 変更ここまで ▲▲▲ ---
        self.library_panel.addNewItemClicked.connect(self._handle_add_new_item)
        self.library_panel.deleteItemClicked.connect(self._handle_delete_item)

        # --- ▼▼▼ Inspector Panel 関連の接続を削除 ▼▼▼ ---
        # self.inspector_panel.changesSaved.connect(self._handle_inspector_save)
        # --- ▲▲▲ 削除ここまで ▲▲▲ ---

    # --- スロット (シグナルハンドラ) ---
    @Slot()
    def _handle_import(self):
        """インポートボタンが押されたときの処理。"""
        imported = self.data_handler.import_data()
        if imported:
            self.db_data, imported_sd_params = imported
            # SD Params は直接編集しないので、インポートされたものを使うか確認が必要
            # ここではインポートされたものを使う例
            self.sd_params = imported_sd_params
            # 新しいデータ参照を各パネルに設定
            self.library_panel.set_data_reference(self.db_data)
            # --- ▼▼▼ InspectorPanel への参照設定を削除 ▼▼▼ ---
            # self.inspector_panel.set_data_reference(self.db_data, self.sd_params)
            # --- ▲▲▲ 削除ここまで ▲▲▲ ---
            self.prompt_panel.set_data_reference(self.db_data)  # PromptPanel も更新
            # current_scene_id を再設定
            scenes_dict = self.db_data.get("scenes", {})
            new_scene_id = next(iter(scenes_dict), None)
            if self.current_scene_id not in scenes_dict:
                self.current_scene_id = new_scene_id

            # UI全体更新
            self.update_ui_after_data_change()
            self.prompt_panel.set_current_scene(self.current_scene_id)  # シーン再選択
            self.prompt_panel.set_current_style(None)  # Style はリセット

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

    # --- ▼▼▼ リストのダブルクリックで編集ダイアログを開くスロットを追加 ▼▼▼ ---
    @Slot(QListWidgetItem)
    def _handle_item_double_clicked(self, item: QListWidgetItem):
        """LibraryPanel のリスト項目がダブルクリックされたときの処理。"""
        if not item:
            return

        db_key = self.library_panel._current_db_key  # 現在選択中のタイプ
        item_id = item.data(Qt.ItemDataRole.UserRole)

        if db_key == "sdParams":
            QMessageBox.information(
                self,
                "SD Params",
                "SD Params は Data Management パネルから Export/Import してください。",
            )
            return
        elif db_key and item_id:
            item_data = self.db_data.get(db_key, {}).get(item_id)
            if item_data:
                modal_type = self._get_modal_type_from_db_key(db_key)
                if modal_type:
                    self.open_edit_dialog(
                        modal_type, item_data
                    )  # item_data を渡して編集モードで開く
                else:
                    QMessageBox.warning(
                        self, "Error", f"Cannot determine editor type for '{db_key}'"
                    )
            else:
                QMessageBox.warning(
                    self, "Error", f"Could not find data for {db_key} - {item_id}"
                )

    # --- ▲▲▲ 追加ここまで ▲▲▲ ---

    @Slot(str, str)
    def _handle_delete_item(self, db_key_str: str, item_id: str):
        """LibraryPanel の Delete ボタンに対応するスロット。"""
        # --- ▼▼▼ db_key_str を DatabaseKey に変換 ▼▼▼ ---
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in get_args(DatabaseKey) else None
        )
        if not db_key:
            QMessageBox.critical(
                self, "Error", f"Invalid db_key '{db_key_str}' for deletion."
            )
            return
        # --- ▲▲▲ 変更ここまで ▲▲▲ ---
        self.delete_item(db_key, item_id)

    # --- ▼▼▼ _handle_inspector_save を削除 ▼▼▼ ---
    # @Slot(str, str, object)
    # def _handle_inspector_save(...):
    #     ...
    # --- ▲▲▲ 削除ここまで ▲▲▲ ---

    @Slot(str)
    def _handle_scene_change(self, new_scene_id: str):
        """PromptPanel からシーン変更の通知を受け取るスロット。(変更なし)"""
        print(f"[DEBUG] MainWindow received sceneChanged signal: {new_scene_id}")
        current_scene_id_before = self.current_scene_id
        self.current_scene_id = new_scene_id if new_scene_id else None
        if current_scene_id_before != self.current_scene_id:
            self.generated_prompts = []
            self.update_prompt_display()

    @Slot(dict)
    def _handle_assignment_change(self, new_assignments: dict):
        """PromptPanel から割り当て変更の通知を受け取るスロット。(変更なし)"""
        print(f"[DEBUG] MainWindow received assignmentChanged: {new_assignments}")
        self.actor_assignments = new_assignments.copy()
        self.generated_prompts = []
        self.update_prompt_display()

    @Slot(str)
    def _handle_style_change(self, new_style_id: str):
        """PromptPanel から Style 変更の通知を受け取るスロット。(変更なし)"""
        print(f"[DEBUG] MainWindow received styleChanged signal: {new_style_id}")
        new_id_or_none = new_style_id if new_style_id else None
        if self.current_style_id != new_id_or_none:
            self.current_style_id = new_id_or_none
            self.generated_prompts = []
            self.update_prompt_display()

    # --- コアロジックメソッド (generate_prompts, execute_generation, update_prompt_display は変更なし) ---
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
            or not self.actor_assignments[r.id]  # IDがない場合もチェック
        ]
        if missing_roles:
            QMessageBox.warning(
                self,
                "Generate",
                f"Assign actors to all roles: {', '.join(missing_roles)}",
            )
            return

        try:
            full_db = FullDatabase(
                **self.db_data, sdParams=self.sd_params
            )  # kwargsで渡す方が安全
            self.generated_prompts = generate_batch_prompts(
                scene_id=self.current_scene_id,
                actor_assignments=self.actor_assignments,
                db=full_db,
                style_id=self.current_style_id,
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
        """画像生成を実行します。"""
        if not self.generated_prompts:
            QMessageBox.warning(
                self, "Execute", "Please generate prompt previews first."
            )
            return
        current_scene = self.db_data.get("scenes", {}).get(self.current_scene_id)
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
        self.library_panel.set_data_reference(self.db_data)  # SD Params は渡さない

        # リストタイプと選択状態を復元
        if current_type_index >= 0:
            self.library_panel.library_type_combo.blockSignals(True)
            self.library_panel.library_type_combo.setCurrentIndex(current_type_index)
            self.library_panel.library_type_combo.blockSignals(False)
            # update_list は setCurrentIndex の後、手動で呼ぶ方が確実かも
            self.library_panel.update_list()  # 手動でリスト更新

        if current_list_selection_id:
            self.library_panel.select_item_by_id(current_list_selection_id)
        # --- ▼▼▼ InspectorPanel 関連の処理を削除 ▼▼▼ ---
        # else:
        #     self.inspector_panel.clear_inspector()
        # --- ▲▲▲ 削除ここまで ▲▲▲ ---

        # プロンプト表示は必要に応じてクリア (シーン変更ハンドラ等で行う)
        # self.update_prompt_display()

        print("[DEBUG] update_ui_after_data_change complete.")

    # --- ▼▼▼ open_edit_dialog を修正 ▼▼▼ ---
    def open_edit_dialog(self, modal_type: str, item_data: Optional[Any]):
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
            # SimplePartEditorDialog は modal_type (文字列) も必要
            if DialogClass == SimplePartEditorDialog:
                dialog = DialogClass(item_data, modal_type, self.db_data, self)
            else:
                dialog = DialogClass(item_data, self.db_data, self)
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
                saved_data = (
                    dialog.saved_data
                )  # 基底クラスの _save_and_accept でセットされる

                if saved_data:
                    item_id_to_select = getattr(saved_data, "id", None)
                    print(
                        f"[DEBUG] Dialog returned data: {item_id_to_select} of type {type(saved_data).__name__}."
                    )

                    # 1. メモリに追加/更新
                    if db_key in self.db_data:
                        self.db_data[db_key][item_id_to_select] = saved_data
                    else:
                        print(
                            f"[ERROR] Invalid db_key '{db_key}' when trying to save data."
                        )
                        return  # エラー処理

                    # 2. DBに即時保存
                    try:
                        self.data_handler.save_single_item(db_key, saved_data)
                    except Exception as db_save_e:
                        # エラー処理は data_handler 側で行われるはずだが、念のため
                        print(
                            f"[ERROR] Failed to save item {item_id_to_select} to DB: {db_save_e}"
                        )
                        # QMessageBox は data_handler 側で表示される想定

                    # 3. UI更新
                    self.update_ui_after_data_change()
                    if item_id_to_select:
                        self.library_panel.select_item_by_id(
                            item_id_to_select
                        )  # 保存したアイテムを選択
                else:
                    print("[DEBUG] Dialog accepted but returned no valid data.")
            else:
                print("[DEBUG] Dialog cancelled or closed.")

    # --- ▲▲▲ 変更ここまで ▲▲▲ ---

    # --- ▼▼▼ ヘルパー関数を追加 ▼▼▼ ---
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

    # --- ▲▲▲ 追加ここまで ▲▲▲ ---

    def delete_item(self, db_key: DatabaseKey, item_id: str):
        """指定されたアイテムを削除します（確認含む）。"""
        item_to_delete = self.db_data.get(db_key, {}).get(item_id)
        if not item_to_delete:
            QMessageBox.warning(
                self, "Delete Error", f"Item '{item_id}' not found in '{db_key}'."
            )
            return

        # Work は title_jp、他は name を優先
        item_name = getattr(item_to_delete, "title_jp", None) or getattr(
            item_to_delete, "name", item_id
        )

        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            # --- ▼▼▼ メッセージを修正 ▼▼▼ ---
            f"'{item_name}' ({item_id}) をメモリとデータベースから削除しますか？\n"
            f"この操作は元に戻せません。",
            # --- ▲▲▲ 変更ここまで ▲▲▲ ---
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            # --- ▼▼▼ DataHandler 側の削除処理を呼び出す形に変更 ▼▼▼ ---
            deleted_from_memory = self.data_handler.handle_delete_part(
                db_key, item_id, self.db_data
            )
            if deleted_from_memory:
                # DBからも削除
                try:
                    db._delete_item(
                        db_key, item_id
                    )  # database モジュールの汎用削除関数を直接呼ぶ
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

                # MainWindow 側の関連データ更新 (変更なし)
                if db_key == "actors":
                    self.actor_assignments = {
                        k: v for k, v in self.actor_assignments.items() if v != item_id
                    }
                if db_key == "scenes" and item_id == self.current_scene_id:
                    self.current_scene_id = next(
                        iter(self.db_data.get("scenes", {})), None
                    )

                self.update_ui_after_data_change()  # UI全体更新
            # --- ▲▲▲ 変更ここまで ▲▲▲ ---
            else:
                # handle_delete_part でエラーがあればメッセージが表示されるはず
                pass
        else:
            print(f"[DEBUG] Deletion cancelled by user for {item_id}.")


# --- スタイル定義 (省略) ---
