# src/panels/prompt_panel.py
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QGroupBox,
    QMessageBox,
    QFormLayout,
    QGroupBox,
    QCheckBox,
    QLayout,
)
from PySide6.QtCore import Qt, Signal, Slot
from typing import Dict, List, Optional, Any, Tuple, Set
from ..models import (
    Scene,
    Actor,
    Style,
    Cut,
    SceneRole,
    StableDiffusionParams,
    Costume,
    Pose,
    Expression,
)


class PromptPanel(QWidget):
    generatePromptsClicked = Signal()
    executeGenerationClicked = Signal()
    sceneChanged = Signal(str)
    assignmentChanged = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._db_data_ref: Dict[str, Dict[str, Any]] = {}
        self._current_assignments: Dict[str, str] = {}
        self._current_overrides: Dict[str, Dict[str, Optional[str]]] = {}
        self._role_override_combos: Dict[str, Dict[str, QComboBox]] = {}
        self._current_scene_id: Optional[str] = None
        self._init_ui()

    def set_data_reference(self, db_data: Dict[str, Dict[str, Any]]):
        self._db_data_ref = db_data

    def set_current_scene(self, scene_id: Optional[str]):
        """MainWindow から現在のシーンIDが変更されたときに呼ばれます。"""
        if self._current_scene_id != scene_id:
            self._current_scene_id = scene_id
            scene_list = sorted(
                self._db_data_ref.get("scenes", {}).values(),
                key=lambda s: getattr(s, "name", "").lower(),
            )
            scene_ids = [getattr(s, "id", None) for s in scene_list]
            try:
                valid_scene_ids = [sid for sid in scene_ids if sid]
                index = (
                    valid_scene_ids.index(scene_id)
                    if scene_id in valid_scene_ids
                    else -1
                )
                self.scene_combo.blockSignals(True)
                self.scene_combo.setCurrentIndex(index if index >= 0 else -1)
                self.scene_combo.blockSignals(False)
            except ValueError:
                self.scene_combo.setCurrentIndex(-1)
            self.build_role_assignment_ui()

    def set_assignments(self, assignments: Dict[str, str]):
        """MainWindow から初期の配役を設定します。"""
        self._current_assignments = assignments.copy()

    def _init_ui(self):
        """UI要素を初期化します。"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        group = QGroupBox("Prompt Generation")
        self.prompt_gen_layout = QVBoxLayout(group)

        scene_layout = QHBoxLayout()
        scene_layout.addWidget(QLabel("1. Select Scene:"))
        self.scene_combo = QComboBox()
        self.scene_combo.currentIndexChanged.connect(self._on_scene_changed)
        scene_layout.addWidget(self.scene_combo)
        self.prompt_gen_layout.addLayout(scene_layout)

        # プレースホルダーとして初期ウィジェットを追加
        self.role_assignment_widget = QWidget()
        self.prompt_gen_layout.addWidget(self.role_assignment_widget)

        self.debug_mode_checkbox = QCheckBox("Debug Mode (Reduce Steps/Size)")
        self.debug_mode_checkbox.setToolTip(
            "If checked, reduces steps, width, and height by 30% (x0.7) when executing generation."
        )
        self.prompt_gen_layout.addWidget(self.debug_mode_checkbox)

        self.task_count_label = QLabel("Pending Tasks: 0")
        self.task_count_label.setAlignment(Qt.AlignCenter)
        self.task_count_label.setStyleSheet("font-weight: bold; color: #17a2b8;")
        self.prompt_gen_layout.addWidget(self.task_count_label)

        generate_preview_btn = QPushButton("🔄 Generate Prompt Preview")
        generate_preview_btn.setStyleSheet("background-color: #ffc107;")
        generate_preview_btn.clicked.connect(self.generatePromptsClicked)

        self.execute_btn = QPushButton("🚀 Execute Image Generation (Run Batch)")
        self.execute_btn.setStyleSheet("background-color: #28a745; color: white;")
        self.execute_btn.clicked.connect(self.executeGenerationClicked)

        self.prompt_gen_layout.addWidget(generate_preview_btn)
        self.prompt_gen_layout.addWidget(self.execute_btn)
        main_layout.addWidget(group)

    def update_task_count(self, count: int):
        """Updates the task count label."""
        self.task_count_label.setText(f"Pending Tasks: {count}")

    def is_debug_mode_enabled(self) -> bool:
        return self.debug_mode_checkbox.isChecked()

    def update_scene_combo(self):
        self.scene_combo.blockSignals(True)
        self.scene_combo.clear()
        scene_list = sorted(
            self._db_data_ref.get("scenes", {}).values(),
            key=lambda s: getattr(s, "name", "").lower(),
        )

        if not scene_list:
            self.scene_combo.addItem("No scenes available")
            self.scene_combo.setEnabled(False)
            self._current_scene_id = None
        else:
            self.scene_combo.addItems([getattr(s, "name", "Unnamed") for s in scene_list])
            valid_scene_ids = [getattr(s, "id", None) for s in scene_list if getattr(s, "id", None)]

            current_scene_index = -1
            if self._current_scene_id and self._current_scene_id in valid_scene_ids:
                try:
                    current_scene_index = valid_scene_ids.index(self._current_scene_id)
                except ValueError:
                    if valid_scene_ids:
                        self._current_scene_id = valid_scene_ids[0]
                        current_scene_index = 0
            elif valid_scene_ids:
                self._current_scene_id = valid_scene_ids[0]
                current_scene_index = 0
            else:
                self._current_scene_id = None
            
            if current_scene_index != -1:
                self.scene_combo.setCurrentIndex(current_scene_index)
            self.scene_combo.setEnabled(True)

        self.scene_combo.blockSignals(False)
        self.build_role_assignment_ui()

    def build_role_assignment_ui(self):
        """役割割り当てUIを動的に構築します。ウィジェットごと交換する方式でUIの残存を防ぎます。"""
        # 1. 古いウィジェットをレイアウトから削除し、メモリからの削除をスケジュール
        if hasattr(self, "role_assignment_widget") and self.role_assignment_widget:
            self.prompt_gen_layout.removeWidget(self.role_assignment_widget)
            self.role_assignment_widget.deleteLater()

        # 2. 新しいウィジェットを作成し、その中にUIを構築する
        self.role_assignment_widget = QWidget()
        self.role_assignment_widget.setObjectName("RoleAssignmentWidgetContainer")
        layout = QVBoxLayout(self.role_assignment_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self._role_override_combos.clear()
        
        layout.addWidget(QLabel("2. Assign Actors to Roles:"))
        current_scene = self._db_data_ref.get("scenes", {}).get(self._current_scene_id)

        roles_to_display: List[SceneRole] = []
        if current_scene and getattr(current_scene, "cut_id", None):
            cut_id = current_scene.cut_id
            selected_cut = self._db_data_ref.get("cuts", {}).get(cut_id)
            if selected_cut:
                roles_to_display = getattr(selected_cut, "roles", [])
            else:
                layout.addWidget(QLabel(f"(Error: Cut '{cut_id}' not found)"))
        elif not current_scene:
            layout.addWidget(QLabel("No scene selected."))
        else:
            layout.addWidget(QLabel("(このシーンにはカットが割り当てられていません)"))

        # UI構築が必要なロールがなければ、空のウィジェットを挿入して終了
        if not roles_to_display:
            layout.addStretch()
            self.prompt_gen_layout.insertWidget(1, self.role_assignment_widget)
            return

        # --- Actor List ---
        actor_list = sorted(self._db_data_ref.get("actors", {}).values(), key=lambda a: getattr(a, "name", "").lower())
        actor_names = ["-- Select Actor --"] + [getattr(a, "name", "Unnamed") for a in actor_list]
        actor_ids = [""] + [getattr(a, "id", None) for a in actor_list]
        valid_actor_ids = [aid for aid in actor_ids if aid is not None]

        # --- Build UI for Roles ---
        for role in roles_to_display:
            role_id = getattr(role, "id", None)
            if not role_id:
                continue

            role_name = getattr(role, "name_in_scene", "Unknown Role")
            role_layout = QHBoxLayout()
            label_text = f"{role_name} ([{role_id.upper()}])"
            role_layout.addWidget(QLabel(label_text))
            
            combo = QComboBox()
            combo.addItems(actor_names)

            assigned_actor_id = self._current_assignments.get(role_id)
            current_index = 0
            # --- DEBUG-UI PRINTS ---
            print(f"[DEBUG-UI] Processing Role ID: '{role_id}'")
            print(f"[DEBUG-UI]   - Assigned Actor ID (from _current_assignments): '{assigned_actor_id}'")
            print(f"[DEBUG-UI]   - Available Actor IDs (in valid_actor_ids): {valid_actor_ids}")
            # --- END DEBUG-UI PRINTS ---
            if assigned_actor_id and assigned_actor_id in valid_actor_ids:
                try:
                    current_index = valid_actor_ids.index(assigned_actor_id) + 1
                    print(f"[DEBUG-UI]   - Calculated QComboBox index: {current_index} for actor '{assigned_actor_id}'")
                except ValueError:
                    print(f"[DEBUG-UI]   - WARN: Assigned actor ID '{assigned_actor_id}' not found in 'valid_actor_ids' for role '{role_id}'. Setting to default.")
                    pass  # Actor not found, will default to index 0
            else:
                print(f"[DEBUG-UI]   - No assigned actor or assigned actor not in 'valid_actor_ids'. Setting to default (index 0).")

            combo.setCurrentIndex(current_index)
            combo.currentIndexChanged.connect(
                lambda index, r_id=role_id, ids=list(actor_ids): self._on_actor_assigned(
                    r_id, ids[index] if 0 <= index < len(ids) else ""
                )
            )
            role_layout.addWidget(combo)
            layout.addLayout(role_layout)

        layout.addStretch()
        
        # 3. 新しいウィジェットをレイアウトの所定の位置に挿入
        self.prompt_gen_layout.insertWidget(1, self.role_assignment_widget)

    def get_current_overrides(self) -> Dict[str, Dict[str, Optional[str]]]:
        return self._current_overrides.copy()

    @Slot(int)
    def _on_scene_changed(self, index: int):
        scene_list = sorted(
            self._db_data_ref.get("scenes", {}).values(),
            key=lambda s: getattr(s, "name", "").lower(),
        )
        new_scene_id = (
            getattr(scene_list[index], "id", None)
            if 0 <= index < len(scene_list)
            else None
        )

        if new_scene_id != self._current_scene_id:
            self.sceneChanged.emit(new_scene_id or "")

    @Slot(str, str)
    def _on_actor_assigned(self, role_id: str, actor_id: str):
        if actor_id:
            self._current_assignments[role_id] = actor_id
        elif role_id in self._current_assignments:
            del self._current_assignments[role_id]
        self.assignmentChanged.emit(self._current_assignments.copy())

    # _on_override_assigned and related functions are removed for simplicity
    # as the core issue is with role assignment UI updates. They can be added back if needed.