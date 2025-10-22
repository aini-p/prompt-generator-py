# src/main_window.py
import sys
import os
import json
import time
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
    QLayout,  # ★ QLayout
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
    FullDatabase,
    json_str_to_list,
)
from .prompt_generator import generate_batch_prompts, create_image_generation_tasks
from .batch_runner import run_stable_diffusion
from typing import Dict, Optional, Any, List, Tuple, Literal, Union, TypeAlias

# --- 実際のフォームをインポート ---
try:
    from .widgets.add_actor_form import AddActorForm
    from .widgets.add_scene_form import AddSceneForm
    from .widgets.add_direction_form import AddDirectionForm
    from .widgets.add_simple_part_form import AddSimplePartForm

    FORMS_IMPORTED = True
    print("[DEBUG] 編集フォームウィジェットのインポートに成功しました。")
except ImportError as e:
    print(
        f"[DEBUG] 警告: 編集フォームウィジェットのインポートに失敗しました。プレースホルダーを使用します。エラー: {e}"
    )

    # フォールバック (プレースホルダー定義)
    class QDialogPlaceholder(QDialog):
        DialogCode = QDialog.DialogCode

        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent", None))
            print("[DEBUG] プレースホルダーダイアログを使用しています。")
            title = "Placeholder Dialog"
            if args:
                if isinstance(args[1], str):
                    title = f"Edit {args[1]}"
                elif args[0]:
                    title = f"Edit {args[0].__class__.__name__}"
                else:
                    title = f"New Item"
            self.setWindowTitle(title)

        def exec(self):
            QMessageBox.information(
                self, "プレースホルダー", "この編集機能はまだ実装されていません。"
            )
            return self.DialogCode.Rejected

        def get_data(self):
            return None

    AddActorForm = AddSceneForm = AddDirectionForm = AddSimplePartForm = (
        QDialogPlaceholder
    )
    FORMS_IMPORTED = False

# --- DatabaseKey の定義 ---
DatabaseKey = Literal[
    "actors",
    "costumes",
    "poses",
    "expressions",
    "directions",
    "backgrounds",
    "lighting",
    "compositions",
    "scenes",
    "sdParams",
]

# --- 汎用モーダルフォームの型 ---
ModalDataType = Union[Actor, Scene, Direction, PromptPartBase, None]
ModalState: TypeAlias = Dict[str, Any]  # {'type': str, 'data': ModalDataType}


class MainWindow(QMainWindow):
    # (__init__ から update_scene_combo までは変更なし)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Object-Oriented Prompt Builder")
        self.setGeometry(100, 100, 1200, 800)
        self.current_scene_id: Optional[str] = None
        self.db_data: Dict[str, Dict[str, Any]] = {}
        self.sd_params: StableDiffusionParams = StableDiffusionParams()
        self._load_all_data()
        self.actor_assignments: Dict[str, str] = {}
        self.generated_prompts: List[GeneratedPrompt] = []
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(400)
        left_panel.setMaximumWidth(600)
        splitter.addWidget(left_panel)
        self._setup_data_management_ui(left_layout)
        self._setup_prompt_generation_ui(left_layout)
        library_scroll = QScrollArea()
        library_scroll.setWidgetResizable(True)
        library_widget = QWidget()
        self.library_layout = QVBoxLayout(library_widget)
        library_widget.setLayout(self.library_layout)
        library_scroll.setWidget(library_widget)
        left_layout.addWidget(library_scroll)
        self._setup_library_ui()
        left_layout.addStretch()
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        splitter.addWidget(right_panel)
        right_layout.addWidget(QLabel("Generated Prompts (Batch)"))
        self.prompt_display_area = QTextEdit()
        self.prompt_display_area.setReadOnly(True)
        right_layout.addWidget(self.prompt_display_area)
        splitter.setSizes([450, 750])

    def _load_all_data(self):
        print("[DEBUG] _load_all_data called.")
        try:
            self.db_data["actors"] = db.load_actors()
            self.db_data["scenes"] = db.load_scenes()
            self.db_data["directions"] = db.load_directions()
            self.db_data["costumes"] = db.load_costumes()
            self.db_data["poses"] = db.load_poses()
            self.db_data["expressions"] = db.load_expressions()
            self.db_data["backgrounds"] = db.load_backgrounds()
            self.db_data["lighting"] = db.load_lighting()
            self.db_data["compositions"] = db.load_compositions()
            self.sd_params = db.load_sd_params()
            print("[DEBUG] Data loaded successfully from database.")
            scenes_dict = self.db_data.get("scenes", {})
            print(f"[DEBUG] Loaded {len(scenes_dict)} scenes.")
            if scenes_dict:
                if self.current_scene_id not in scenes_dict:
                    print(
                        f"[DEBUG] Current scene ID '{self.current_scene_id}' is invalid or None."
                    )
                    self.current_scene_id = next(iter(scenes_dict), None)
                    print(
                        f"[DEBUG] Setting current scene ID to: {self.current_scene_id}"
                    )
            else:
                self.current_scene_id = None
                print("[DEBUG] No scenes found.")
            print(f"[DEBUG] Initial scene ID set to: {self.current_scene_id}")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load data: {e}")
            print(f"[DEBUG] DB load error: {e}")
            self.db_data = {k: {} for k in STORAGE_KEYS if k != "sdParams"}
            self.sd_params = StableDiffusionParams()
            self.current_scene_id = None

    def _setup_data_management_ui(self, parent_layout):
        group = QGroupBox("Data Management")
        layout = QHBoxLayout()
        group.setLayout(layout)
        save_btn = QPushButton("💾 Save to DB")
        save_btn.clicked.connect(self.save_all_data)
        export_btn = QPushButton("📤 Export JSON")
        export_btn.clicked.connect(self.export_data)
        import_btn = QPushButton("📥 Import JSON")
        import_btn.clicked.connect(self.import_data)
        layout.addWidget(save_btn)
        layout.addWidget(export_btn)
        layout.addWidget(import_btn)
        parent_layout.addWidget(group)

    def _setup_prompt_generation_ui(self, parent_layout):
        print("[DEBUG] _setup_prompt_generation_ui called.")
        group = QGroupBox("Prompt Generation")
        self.prompt_gen_layout = QVBoxLayout()
        group.setLayout(self.prompt_gen_layout)
        scene_layout = QHBoxLayout()
        scene_layout.addWidget(QLabel("1. Select Scene:"))
        self.scene_combo = QComboBox()
        self.update_scene_combo()
        self.scene_combo.currentIndexChanged.connect(self.on_scene_changed)
        scene_layout.addWidget(self.scene_combo)
        self.prompt_gen_layout.addLayout(scene_layout)
        self.role_assignment_widget = QWidget()
        self.role_assignment_widget.setObjectName("RoleAssignmentWidgetContainer")
        print(
            "[DEBUG] _setup_prompt_generation_ui: Initial role_assignment_widget created."
        )
        self.prompt_gen_layout.addWidget(self.role_assignment_widget)
        self.build_role_assignment_ui()
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

    def update_scene_combo(self):
        print("[DEBUG] update_scene_combo called.")
        self.scene_combo.blockSignals(True)
        self.scene_combo.clear()
        scene_list = list(self.db_data.get("scenes", {}).values())
        print(f"[DEBUG] update_scene_combo: Found {len(scene_list)} scenes.")
        if not scene_list:
            self.scene_combo.addItem("No scenes available")
            self.scene_combo.setEnabled(False)
            print("[DEBUG] update_scene_combo: No scenes available.")
        else:
            self.scene_combo.addItems([s.name for s in scene_list])
            current_scene_index = 0
            current_id = self.current_scene_id
            scene_ids = [s.id for s in scene_list]
            if current_id and current_id in scene_ids:
                try:
                    current_scene_index = scene_ids.index(current_id)
                except ValueError:
                    print(
                        f"[DEBUG] update_scene_combo: current_id '{current_id}' not found."
                    )
                    current_id = scene_list[0].id
                    current_scene_index = 0
            elif scene_list:
                current_id = scene_list[0].id
                current_scene_index = 0
                print(f"[DEBUG] update_scene_combo: set to first: {current_id}")
            self.current_scene_id = current_id
            print(
                f"[DEBUG] update_scene_combo: Setting index to {current_scene_index} (ID: {self.current_scene_id})"
            )
            self.scene_combo.setCurrentIndex(current_scene_index)
            self.scene_combo.setEnabled(True)
        self.scene_combo.blockSignals(False)
        print("[DEBUG] update_scene_combo complete.")

    # --- ★★★ 関数全体表示 (build_role_assignment_ui - レイアウトクリア修正 v4) ★★★ ---
    def build_role_assignment_ui(self):
        """Dynamically builds the UI for assigning actors to roles
        INSIDE the current self.role_assignment_widget."""
        print(
            f"[DEBUG] build_role_assignment_ui called for scene ID: {self.current_scene_id}"
        )

        # --- 1. レイアウトを取得、なければ作成 ---
        layout = self.role_assignment_widget.layout()
        if layout is None:
            print(
                "[DEBUG] No layout found on role_assignment_widget, creating new QVBoxLayout."
            )
            layout = QVBoxLayout()
            self.role_assignment_widget.setLayout(layout)
        else:
            print("[DEBUG] Clearing existing role assignment layout...")
            # --- ★ 修正: レイアウトクリア処理 (より安全な方法) ---
            # layout() からアイテムを削除すると同時にウィジェットも削除予約
            # QLayout::takeAt() は QLayoutItem を返す
            item = layout.takeAt(0)
            while item is not None:
                widget = item.widget()
                if widget is not None:
                    # print(f"[DEBUG] Deleting old widget: {widget}")
                    widget.deleteLater()  # ウィジェットを削除予約
                else:
                    # item がレイアウトの場合 (QHBoxLayoutなど)
                    layout_item = item.layout()
                    if layout_item is not None:
                        # print(f"[DEBUG] Deleting old nested layout: {layout_item}")
                        # ネストされたレイアウトの中身もクリア (再帰的に行うのが理想だが、ここでは1段階のみ)
                        item_inner = layout_item.takeAt(0)
                        while item_inner is not None:
                            widget_inner = item_inner.widget()
                            if widget_inner is not None:
                                widget_inner.deleteLater()
                            # ネストされたレイアウト内のレイアウトも考慮 (さらに深くは省略)
                            layout_inner = item_inner.layout()
                            if layout_inner is not None:
                                layout_inner.deleteLater()  # Delete layout itself
                            item_inner = layout_item.takeAt(0)  # 次のアイテムへ
                        # ネストされたレイアウト自体も削除
                        layout_item.deleteLater()
                # 次のアイテムを取得
                item = layout.takeAt(0)
            print("[DEBUG] Existing role assignment layout cleared.")
            # --- ★ 修正ここまで ---

        # --- 2. 新しいレイアウトにウィジェットを追加 ---
        layout.addWidget(QLabel("2. Assign Actors to Roles:"))
        current_scene = (
            self.db_data.get("scenes", {}).get(self.current_scene_id)
            if self.current_scene_id
            else None
        )
        if not current_scene:
            layout.addWidget(QLabel("No scene selected."))
            layout.addStretch()
            print("[DEBUG] build_role_assignment_ui: No scene selected.")
            return

        actor_list = list(self.db_data.get("actors", {}).values())
        actor_names = ["-- Select Actor --"] + [a.name for a in actor_list]
        actor_ids = [""] + [a.id for a in actor_list]
        print(f"[DEBUG] build_role_assignment_ui: Found {len(actor_list)} actors.")

        if not current_scene.roles:
            layout.addWidget(QLabel("(このシーンには配役が定義されていません)"))
            print("[DEBUG] build_role_assignment_ui: Current scene has no roles.")

        print(
            f"[DEBUG] build_role_assignment_ui: Building UI for {len(current_scene.roles)} roles..."
        )
        for role in current_scene.roles:
            print(f"[DEBUG] Creating UI for role: {role.id} ({role.name_in_scene})")
            role_layout = QHBoxLayout()  # 新しい行レイアウト
            label_text = f"{role.name_in_scene} ([{role.id.upper()}])"
            role_layout.addWidget(QLabel(label_text))
            combo = QComboBox()  # 新しいコンボボックス
            combo.addItems(actor_names)
            assigned_actor_id = self.actor_assignments.get(role.id)
            current_index = 0
            if assigned_actor_id and assigned_actor_id in actor_ids:
                try:
                    current_index = actor_ids.index(assigned_actor_id)
                except ValueError:
                    print(
                        f"[DEBUG] Warn: Assigned actor ID '{assigned_actor_id}' not found."
                    )
            combo.setCurrentIndex(current_index)
            combo.currentIndexChanged.connect(
                lambda index, r_id=role.id, ids=list(actor_ids): self.on_actor_assigned(
                    r_id, ids[index] if 0 <= index < len(ids) else ""
                )
            )
            role_layout.addWidget(combo)
            layout.addLayout(role_layout)  # メインレイアウトに行を追加

        layout.addStretch()  # 要素を上に詰める
        # ★ Optional: ウィジェットのサイズポリシーを調整 (効果がある場合がある)
        self.role_assignment_widget.adjustSize()
        # ★ Optional: 親レイアウトに更新を促す
        if self.prompt_gen_layout:
            self.prompt_gen_layout.activate()

        print("[DEBUG] build_role_assignment_ui complete.")

    # --- ★★★ 関数全体表示ここまで ★★★ ---

    # (on_scene_changed は変更なし - build_role_assignment_ui を呼ぶだけ)
    @Slot(int)
    def on_scene_changed(self, index):
        print(f"[DEBUG] on_scene_changed called with index: {index}")
        scene_list = list(self.db_data.get("scenes", {}).values())
        if 0 <= index < len(scene_list):
            new_scene_id = scene_list[index].id
            print(f"[DEBUG] Selected scene ID from list: {new_scene_id}")
            if new_scene_id != self.current_scene_id:
                print(
                    f"[DEBUG] Scene ID changed! Old: {self.current_scene_id}, New: {new_scene_id}"
                )
                self.current_scene_id = new_scene_id
                self.actor_assignments = {}
                self.generated_prompts = []
                print("[DEBUG] Calling build_role_assignment_ui...")
                self.build_role_assignment_ui()  # レイアウト再構築を呼ぶ
                print("[DEBUG] Returned from build_role_assignment_ui.")
                self.update_prompt_display()
            else:
                print("[DEBUG] Scene index changed, but ID is the same.")
        else:
            print(f"[DEBUG] Invalid scene index selected: {index}")

    # --- ★★★ 関数全体表示 (_setup_library_ui - レイアウトクリア修正) ★★★ ---
    def _setup_library_ui(self):
        """Populates the library editing section."""
        print("[DEBUG] _setup_library_ui called.")  # Debug
        # --- 1. 古いレイアウトとウィジェットを確実に削除 (修正) ---
        # Check if library_layout exists and has items
        if hasattr(self, "library_layout") and self.library_layout is not None:
            # Iterate backwards to safely remove items from the layout
            print(
                f"[DEBUG] Clearing library layout. Item count: {self.library_layout.count()}"
            )  # Debug
            while self.library_layout.count() > 0:
                item = self.library_layout.takeAt(
                    self.library_layout.count() - 1
                )  # Take last item
                if item is None:
                    print(
                        "[DEBUG] takeAt returned None unexpectedly in library layout."
                    )  # Debug
                    continue

                widget = item.widget()
                if widget is not None:
                    print(f"[DEBUG] Deleting library widget: {widget}")  # Debug
                    widget.deleteLater()
                else:
                    # Check if it's a layout item
                    layout_item = item.layout()
                    if layout_item is not None:
                        # Clear nested layout items
                        print(
                            f"[DEBUG] Deleting nested library layout: {layout_item}"
                        )  # Debug
                        while layout_item.count() > 0:
                            nested_item = layout_item.takeAt(layout_item.count() - 1)
                            nested_widget = nested_item.widget()
                            if nested_widget:
                                nested_widget.deleteLater()
                            # Also delete nested layouts if present
                            nested_layout = nested_item.layout()
                            if nested_layout:
                                nested_layout.deleteLater()
                        layout_item.deleteLater()  # Delete the nested layout itself
            print("[DEBUG] Finished clearing library layout.")  # Debug
        else:
            print(
                "[DEBUG] self.library_layout is None or doesn't exist yet, cannot clear."
            )  # Debug

        # --- 2. 新しいグループボックスとレイアウトを作成 ---
        # Ensure self.library_layout exists (it should from __init__)
        if not hasattr(self, "library_layout") or self.library_layout is None:
            print("[DEBUG] ERROR: self.library_layout is missing in _setup_library_ui!")
            # Attempt to recover if layout was somehow lost (shouldn't happen)
            # Find the parent widget (library_widget) and reset its layout
            library_widget = self.findChild(
                QWidget, "library_widget_name"
            )  # Need object name
            if library_widget:
                self.library_layout = QVBoxLayout(library_widget)
            else:
                return  # Cannot proceed

        library_group = QGroupBox("Library Editing")
        library_group_layout = (
            QVBoxLayout()
        )  # This is the layout *inside* the new group box
        library_group.setLayout(library_group_layout)
        # Add the new group box to the main library layout (self.library_layout)
        self.library_layout.addWidget(library_group)
        print("[DEBUG] Added new 'Library Editing' QGroupBox.")  # Debug

        # --- 3. SD Params Editor ---
        sd_group = QGroupBox("Stable Diffusion Parameters")
        sd_group.setCheckable(True)
        sd_group.setChecked(False)
        sd_layout = QFormLayout()
        sd_group.setLayout(sd_layout)
        library_group_layout.addWidget(
            sd_group
        )  # Add SD group *inside* the library group
        # Create/update widgets
        self.sd_steps_spin = getattr(
            self, "sd_steps_spin", QSpinBox(minimum=1, maximum=200)
        )
        self.sd_sampler_edit = getattr(self, "sd_sampler_edit", QLineEdit())
        self.sd_cfg_spin = getattr(
            self,
            "sd_cfg_spin",
            QDoubleSpinBox(minimum=1.0, maximum=30.0, singleStep=0.5),
        )
        self.sd_seed_spin = getattr(
            self, "sd_seed_spin", QSpinBox(minimum=-1, maximum=2**31 - 1)
        )
        self.sd_width_spin = getattr(
            self, "sd_width_spin", QSpinBox(minimum=64, maximum=4096, singleStep=64)
        )
        self.sd_height_spin = getattr(
            self, "sd_height_spin", QSpinBox(minimum=64, maximum=4096, singleStep=64)
        )
        self.sd_denoising_spin = getattr(
            self,
            "sd_denoising_spin",
            QDoubleSpinBox(minimum=0.0, maximum=1.0, singleStep=0.05),
        )
        # Set values
        self.sd_steps_spin.setValue(self.sd_params.steps)
        self.sd_sampler_edit.setText(self.sd_params.sampler_name)
        self.sd_cfg_spin.setValue(self.sd_params.cfg_scale)
        self.sd_seed_spin.setValue(self.sd_params.seed)
        self.sd_width_spin.setValue(self.sd_params.width)
        self.sd_height_spin.setValue(self.sd_params.height)
        self.sd_denoising_spin.setValue(self.sd_params.denoising_strength)
        # Disconnect/Connect signals safely
        try:
            self.sd_steps_spin.valueChanged.disconnect()
        except RuntimeError:
            pass
        self.sd_steps_spin.valueChanged.connect(
            lambda v: setattr(self.sd_params, "steps", v)
        )
        try:
            self.sd_sampler_edit.textChanged.disconnect()
        except RuntimeError:
            pass
        self.sd_sampler_edit.textChanged.connect(
            lambda t: setattr(self.sd_params, "sampler_name", t)
        )
        try:
            self.sd_cfg_spin.valueChanged.disconnect()
        except RuntimeError:
            pass
        self.sd_cfg_spin.valueChanged.connect(
            lambda v: setattr(self.sd_params, "cfg_scale", v)
        )
        try:
            self.sd_seed_spin.valueChanged.disconnect()
        except RuntimeError:
            pass
        self.sd_seed_spin.valueChanged.connect(
            lambda v: setattr(self.sd_params, "seed", v)
        )
        try:
            self.sd_width_spin.valueChanged.disconnect()
        except RuntimeError:
            pass
        self.sd_width_spin.valueChanged.connect(
            lambda v: setattr(self.sd_params, "width", v)
        )
        try:
            self.sd_height_spin.valueChanged.disconnect()
        except RuntimeError:
            pass
        self.sd_height_spin.valueChanged.connect(
            lambda v: setattr(self.sd_params, "height", v)
        )
        try:
            self.sd_denoising_spin.valueChanged.disconnect()
        except RuntimeError:
            pass
        self.sd_denoising_spin.valueChanged.connect(
            lambda v: setattr(self.sd_params, "denoising_strength", v)
        )
        # Add rows if not already added
        if not sd_layout.rowCount() > 0:  # Check if rows already exist
            sd_layout.addRow("Steps:", self.sd_steps_spin)
            sd_layout.addRow("Sampler Name:", self.sd_sampler_edit)
            sd_layout.addRow("CFG Scale:", self.sd_cfg_spin)
            sd_layout.addRow("Seed (-1 Random):", self.sd_seed_spin)
            sd_layout.addRow("Width:", self.sd_width_spin)
            sd_layout.addRow("Height:", self.sd_height_spin)
            sd_layout.addRow("Denoising (img2img):", self.sd_denoising_spin)

        # --- 4. Collapsible Library Sections ---
        library_items: List[Tuple[str, str, str]] = [
            ("Scenes", "scenes", "SCENE"),
            ("Actors", "actors", "ACTOR"),
            ("Directions", "directions", "DIRECTION"),
            ("Costumes", "costumes", "COSTUME"),
            ("Poses", "poses", "POSE"),
            ("Expressions", "expressions", "EXPRESSION"),
            ("Backgrounds", "backgrounds", "BACKGROUND"),
            ("Lighting", "lighting", "LIGHTING"),
            ("Compositions", "compositions", "COMPOSITION"),
        ]
        print(f"[DEBUG] Setting up {len(library_items)} library sections...")
        for title, db_key_str, modal_type_str in library_items:
            db_key: DatabaseKey = db_key_str  # Explicit cast/hint
            modal_type = modal_type_str  # Explicit cast/hint
            if db_key not in self.db_data:
                print(f"[DEBUG] Key '{db_key}' not found in db_data.")
                continue  # Skip if key missing

            group = QGroupBox(title)
            group.setCheckable(True)
            group.setChecked(False)
            layout = QVBoxLayout()
            group.setLayout(layout)
            add_btn = QPushButton(f"＋ Add New {title[:-1]}")
            add_btn.clicked.connect(
                lambda checked=False, mt=modal_type: self.open_edit_dialog(mt, None)
            )
            layout.addWidget(add_btn)
            list_widget = QListWidget()
            list_widget.setMaximumHeight(150)
            items = self.db_data.get(db_key, {})  # Safely get items dictionary
            if isinstance(items, dict):  # Ensure 'items' is a dictionary
                for item_id, item_obj in items.items():
                    item_name = getattr(item_obj, "name", "Unnamed")
                    item_id_str = getattr(item_obj, "id", None)
                    if item_id_str:
                        list_item = QListWidgetItem(f"{item_name} ({item_id_str})")
                        list_item.setData(Qt.ItemDataRole.UserRole, item_id_str)
                        list_widget.addItem(list_item)
            else:
                print(
                    f"[DEBUG] Warning: Expected dict for db_key '{db_key}', but got {type(items)}."
                )
            layout.addWidget(list_widget)
            btn_layout = QHBoxLayout()
            edit_btn = QPushButton("✏️ Edit Selected")
            delete_btn = QPushButton("🗑️ Delete Selected")
            edit_btn.clicked.connect(
                lambda checked=False,
                lw=list_widget,
                mt=modal_type,
                dk=db_key: self.edit_selected_item(lw, mt, dk)
            )
            delete_btn.clicked.connect(
                lambda checked=False,
                lw=list_widget,
                dk=db_key: self.delete_selected_item(lw, dk)
            )
            btn_layout.addWidget(edit_btn)
            btn_layout.addWidget(delete_btn)
            layout.addLayout(btn_layout)
            library_group_layout.addWidget(
                group
            )  # Add group to the main library group layout
        print("[DEBUG] Library sections setup complete.")

    # --- ★★★ 関数全体表示ここまで ★★★ ---

    @Slot()
    def save_all_data(self):
        pass  # 簡略表示

    @Slot()
    def export_data(self):
        pass  # 簡略表示

    @Slot()
    def import_data(self):
        pass  # 簡略表示

    # --- ★★★ 関数全体表示 (handleSavePart - 修正) ★★★ ---
    def handleSavePart(
        self, db_key: DatabaseKey, part: Any
    ):  # Accept Any data type from dialog
        """Saves a single part (Actor, Scene, etc.) to the in-memory db_data."""
        if not hasattr(part, "id"):
            print(
                f"[DEBUG] Error in handleSavePart: Saved data has no 'id'. Data: {part}"
            )
            return
        print(
            f"[DEBUG] handleSavePart called for db_key='{db_key}', part_id='{part.id}'"
        )

        # Update the specific dictionary within self.db_data
        if db_key in self.db_data:
            if not isinstance(self.db_data[db_key], dict):
                print(
                    f"[DEBUG] Warning: self.db_data['{db_key}'] is not a dict. Reinitializing."
                )
                self.db_data[db_key] = {}
            self.db_data[db_key][part.id] = part
            print(f"[DEBUG] Part {part.id} saved/updated in self.db_data['{db_key}'].")
        else:
            print(f"[DEBUG] Error: Invalid db_key '{db_key}' passed to handleSavePart.")
            return  # Stop if db_key is invalid

        # --- ★ 修正箇所 ---
        # If a Scene was saved, update the selection
        if db_key == "scenes":
            print(f"[DEBUG] Scene saved, setting current_scene_id to {part.id}")
            # Direct assignment to the attribute
            self.current_scene_id = part.id
            # Manually trigger UI updates related to scene change
            print("[DEBUG] Triggering UI updates after scene save...")
            self.update_scene_combo()  # Ensure combo reflects the change and current index
            self.build_role_assignment_ui()  # Rebuild roles for the newly saved/selected scene
            self.update_prompt_display()  # Clear prompt display

    # --- ★★★ 関数全体表示 (handleDeletePart - 修正) ★★★ ---
    def handleDeletePart(self, db_key: DatabaseKey, partId: str):
        """Deletes a single part from the in-memory db_data."""
        partName = (
            self.db_data.get(db_key, {}).get(partId, {}).get("name", "Item")
        )  # Safer access
        print(
            f"[DEBUG] handleDeletePart called for db_key='{db_key}', partId='{partId}' ({partName})"
        )

        # Confirmation is handled in delete_selected_item, assume confirmed here
        if db_key in self.db_data and partId in self.db_data[db_key]:
            print(f"[DEBUG] Deleting {partId} from self.db_data['{db_key}']...")
            del self.db_data[db_key][partId]

            # Reset related states if necessary
            if db_key == "actors":
                print("[DEBUG] Actor deleted, clearing assignments...")
                new_assignments = {
                    k: v for k, v in self.actor_assignments.items() if v != partId
                }
                self.actor_assignments = new_assignments
                # Need to rebuild UI potentially if deleted actor was assigned
                self.build_role_assignment_ui()
            if db_key == "scenes" and partId == self.current_scene_id:
                print(
                    "[DEBUG] Current scene deleted, selecting first available scene..."
                )
                self.current_scene_id = next(iter(self.db_data.get("scenes", {})), None)
                # UI update will be triggered by update_ui_after_data_change or explicitly
                # self.update_scene_combo() # Or let update_ui handle it

            print(f"[DEBUG] Deletion from db_data complete for {partId}.")
        else:
            print(f"[DEBUG] Item {partId} not found in {db_key}, cannot delete.")

    # --- ★★★ 関数全体表示ここまで ★★★ ---

    # --- ★★★ 関数全体表示 (LibraryList - 修正) ★★★ ---
    # Convert back to a method that returns a QWidget
    def LibraryList(self, db_key: DatabaseKey, modal_type: str) -> QWidget:
        """Creates a widget containing a list and edit/delete buttons for a library type."""
        print(f"[DEBUG] Creating LibraryList widget for: {db_key}")  # Debug
        widget = QWidget()  # Outer container widget
        layout = QVBoxLayout(widget)  # Main layout for this section
        layout.setContentsMargins(0, 0, 0, 0)

        add_btn = QPushButton(f"＋ Add New {db_key[:-1].capitalize()}")
        # Use lambda capture correctly
        add_btn.clicked.connect(
            lambda checked=False, mt=modal_type: self.open_edit_dialog(mt, None)
        )
        layout.addWidget(add_btn)

        list_widget = QListWidget()
        list_widget.setObjectName(
            f"list_{db_key}"
        )  # Set object name for debugging/styling
        list_widget.setMaximumHeight(150)
        items = self.db_data.get(db_key, {})  # Safely get items dictionary
        print(f"[DEBUG] Populating list for {db_key} with {len(items)} items.")  # Debug
        if isinstance(items, dict):  # Ensure 'items' is a dictionary
            for item_id, item_obj in items.items():
                item_name = getattr(item_obj, "name", "Unnamed")
                item_id_str = getattr(item_obj, "id", None)
                if item_id_str:
                    list_item = QListWidgetItem(f"{item_name} ({item_id_str})")
                    list_item.setData(Qt.ItemDataRole.UserRole, item_id_str)  # Store ID
                    list_widget.addItem(list_item)
        else:
            print(
                f"[DEBUG] Warning: Expected dict for db_key '{db_key}', but got {type(items)}."
            )
        layout.addWidget(list_widget)

        btn_layout = QHBoxLayout()
        edit_btn = QPushButton("✏️ Edit Selected")
        delete_btn = QPushButton("🗑️ Delete Selected")
        # Ensure correct capture in lambdas, pass the list_widget instance
        edit_btn.clicked.connect(
            lambda checked=False,
            lw=list_widget,
            mt=modal_type,
            dk=db_key: self.edit_selected_item(lw, mt, dk)
        )
        delete_btn.clicked.connect(
            lambda checked=False, lw=list_widget, dk=db_key: self.delete_selected_item(
                lw, dk
            )
        )
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        layout.addLayout(btn_layout)

        return widget  # Return the container widget

    @Slot(str, str)  # role_id, actor_id
    def on_actor_assigned(self, role_id, actor_id):
        print(
            f"[DEBUG] on_actor_assigned called for Role ID: {role_id}, Actor ID: '{actor_id}'"
        )
        if actor_id:
            self.actor_assignments[role_id] = actor_id
            print(f"[DEBUG] Assigned actor {actor_id} to role {role_id}")
        else:
            if role_id in self.actor_assignments:
                del self.actor_assignments[role_id]
                print(f"[DEBUG] Unassigned actor from role {role_id}")
            else:
                print(f"[DEBUG] Role {role_id} was already unassigned.")
        print(f"[DEBUG] Current assignments: {self.actor_assignments}")
        self.generated_prompts = []
        self.update_prompt_display()

    @Slot()
    def generate_prompts(self):
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
            self.generated_prompts: List[GeneratedPrompt] = generate_batch_prompts(
                self.current_scene_id, self.actor_assignments, self.db_data
            )
            self.update_prompt_display()
        except Exception as e:
            QMessageBox.critical(
                self, "Generation Error", f"Error generating prompts: {e}"
            )
            print(f"[DEBUG] Prompt generation error: {e}")
            import traceback

            traceback.print_exc()

    @Slot()
    def execute_generation(self):
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

    # --- ★★★ 関数全体表示 (update_prompt_display - 型ヒント修正) ★★★ ---
    def update_prompt_display(self):
        """Updates the right panel's text area."""
        print("[DEBUG] update_prompt_display called.")
        if not self.generated_prompts:
            self.prompt_display_area.setPlainText("Press 'Generate Prompt Preview'.")
            print("[DEBUG] No prompts to display.")
            return

        display_text = ""
        print(f"[DEBUG] Displaying {len(self.generated_prompts)} generated prompts.")
        # ★ 修正: self.generated_prompts は GeneratedPrompt オブジェクトのリスト
        for p in self.generated_prompts:
            display_text += f"--- {p.name} ---\n"
            display_text += f"Positive:\n{p.positive}\n\n"
            display_text += f"Negative:\n{p.negative}\n"
            display_text += "------------------------------------\n\n"
        self.prompt_display_area.setPlainText(display_text)
        print("[DEBUG] Prompt display area updated.")

    # --- ★★★ 関数全体表示ここまで ★★★ ---

    def update_ui_after_data_change(self):
        print("[DEBUG] update_ui_after_data_change called.")
        self.update_scene_combo()
        self._setup_library_ui()
        self.build_role_assignment_ui()
        self.generated_prompts = []
        self.update_prompt_display()
        print("[DEBUG] update_ui_after_data_change complete.")

    # --- ★★★ 関数全体表示 (open_edit_dialog - 修正) ★★★ ---
    def open_edit_dialog(self, modal_type: str, item_data: Optional[Any]):
        """Opens the appropriate dialog based on modal_type."""
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
        # ★ 修正: db_key を DatabaseKey 型として取得
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
            # --- ★ 修正: 実際のフォームクラスをインスタンス化 ---
            if modal_type == "ACTOR":
                # ★ db_data 全体を渡す
                dialog = AddActorForm(item_data, self.db_data, self)
            elif modal_type == "SCENE":
                dialog = AddSceneForm(item_data, self.db_data, self)
            elif modal_type == "DIRECTION":
                dialog = AddDirectionForm(item_data, self.db_data, self)
            elif modal_type in [
                "COSTUME",
                "POSE",
                "EXPRESSION",
                "BACKGROUND",
                "LIGHTING",
                "COMPOSITION",
            ]:
                # ★ AddSimplePartForm には db_data は不要かもしれない (型定義による)
                dialog = AddSimplePartForm(
                    item_data, modal_type, self
                )  # Pass type name string
            else:
                QMessageBox.warning(
                    self,
                    "Not Implemented",
                    f"Dialog for '{modal_type}' not implemented.",
                )
                return
            print(f"[DEBUG] Dialog instance created: {dialog}")
        except Exception as e:
            QMessageBox.critical(
                self, "Dialog Error", f"Failed to create dialog for {modal_type}: {e}"
            )
            print(f"[DEBUG] Error creating dialog: {e}")
            return

        if dialog:
            print("[DEBUG] Executing dialog...")
            result = dialog.exec()
            print(f"[DEBUG] Dialog exec finished with result: {result}")

            if result == QDialog.DialogCode.Accepted:
                print("[DEBUG] Dialog accepted.")
                if hasattr(dialog, "get_data") and callable(dialog.get_data):
                    saved_data = dialog.get_data()
                    # ★ 修正: db_key を DatabaseKey 型として渡す
                    if (
                        saved_data and db_key in self.db_data
                    ):  # db_key の妥当性もチェック
                        print(
                            f"[DEBUG] Dialog returned data: {saved_data.id}. Calling handleSavePart."
                        )
                        self.handleSavePart(db_key, saved_data)  # ★ db_key を渡す
                        self.update_ui_after_data_change()
                    elif not db_key:
                        print("[DEBUG] Error: db_key is missing for save operation.")
                    elif db_key not in self.db_data:
                        print(
                            f"[DEBUG] Error: db_key '{db_key}' is not a valid key in self.db_data."
                        )
                    else:
                        print("[DEBUG] Dialog accepted but returned no data.")
                else:
                    print(
                        f"[DEBUG] Dialog {dialog.__class__.__name__} accepted but has no 'get_data' method."
                    )
            else:
                print("[DEBUG] Dialog cancelled or closed.")
        else:
            print(f"[DEBUG] Dialog instance was None for {modal_type}.")

    # --- ★★★ 関数全体表示ここまで ★★★ ---

    # --- ★★★ 関数全体表示 (edit_selected_item - 修正) ★★★ ---
    def edit_selected_item(
        self, list_widget: QListWidget, modal_type: str, db_key_str: str
    ):
        """Opens the edit dialog for the item selected in the list widget."""
        print(
            f"[DEBUG] edit_selected_item called for type: {modal_type}, key: {db_key_str}"
        )
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Edit", "Please select an item to edit.")
            return
        item_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
        print(f"[DEBUG] Selected item ID: {item_id}")
        # ★ 修正: db_key を DatabaseKey 型として取得
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in STORAGE_KEYS else None
        )
        if not db_key:
            QMessageBox.critical(
                self, "Error", f"Invalid database key provided: {db_key_str}"
            )
            return
        item_data = self.db_data.get(db_key, {}).get(item_id)
        if item_data:
            print(f"[DEBUG] Found item data, calling open_edit_dialog...")
            self.open_edit_dialog(modal_type, item_data)
        else:
            QMessageBox.warning(
                self, "Edit", f"Item data not found for ID '{item_id}' in '{db_key}'."
            )
            print(f"[DEBUG] Item data not found for ID '{item_id}' in '{db_key}'.")

    # --- ★★★ 関数全体表示ここまで ★★★ ---

    # --- ★★★ 関数全体表示 (delete_selected_item - 修正) ★★★ ---
    def delete_selected_item(self, list_widget: QListWidget, db_key_str: str):
        """Deletes the item selected in the list widget."""
        print(f"[DEBUG] delete_selected_item called for key: {db_key_str}")
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Delete", "Please select an item to delete.")
            return
        item_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
        print(f"[DEBUG] Selected item ID for deletion: {item_id}")
        # ★ 修正: db_key を DatabaseKey 型として取得
        db_key: Optional[DatabaseKey] = (
            db_key_str if db_key_str in STORAGE_KEYS else None
        )
        if not db_key:
            QMessageBox.critical(
                self, "Error", f"Invalid database key provided: {db_key_str}"
            )
            return

        # handleDeletePart内で確認メッセージ表示 & データ削除
        self.handleDeletePart(db_key, item_id)  # Updates self.db_data

        # Check if item still exists in db_data (means deletion was cancelled or failed)
        if item_id not in self.db_data.get(db_key, {}):
            print(
                f"[DEBUG] Item {item_id} confirmed deleted from db_data. Removing from list widget."
            )
            # Remove item from the list widget visually only if confirmed deleted from data
            list_widget.takeItem(list_widget.row(selected_items[0]))
            if db_key == "scenes":
                print("[DEBUG] Scene deleted, updating scene combo.")
                self.update_scene_combo()  # Refresh scene dropdown if needed
        else:
            print(
                f"[DEBUG] Item {item_id} deletion cancelled or failed, not removing from list widget."
            )

    # --- ★★★ 関数全体表示ここまで ★★★ ---


# --- Style Definitions (変更なし) ---
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

# (Main execution block should be in main.py)
