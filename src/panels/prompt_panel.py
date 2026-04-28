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
            scene_list = self._get_recent_first_items("scenes")
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
        scene_list = self._get_recent_first_items("scenes")

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
        actor_list = self._get_recent_first_items("actors")
        actor_names = ["-- Select Actor --"] + [getattr(a, "name", "Unnamed") for a in actor_list]
        actor_ids = [""] + [getattr(a, "id", None) for a in actor_list]
        valid_actor_ids = [aid for aid in actor_ids if aid is not None]

        # --- Costume / Pose / Expression item lists ---
        def _build_item_list(db_key: str):
            items = self._get_recent_first_items(db_key)
            names = ["-- Default --"] + [getattr(i, "name", "Unnamed") for i in items]
            ids = [""] + [getattr(i, "id", None) for i in items]
            return names, ids

        costume_names, costume_ids = _build_item_list("costumes")
        pose_names, pose_ids = _build_item_list("poses")
        expression_names, expression_ids = _build_item_list("expressions")

        # --- Build UI for Roles ---
        for role in roles_to_display:
            role_id = getattr(role, "id", None)
            if not role_id:
                continue

            role_name = getattr(role, "name_in_scene", "Unknown Role")

            # Role group box
            role_group = QGroupBox(f"{role_name}  [{role_id.upper()}]")
            role_form = QFormLayout(role_group)
            role_form.setContentsMargins(6, 4, 6, 4)

            # --- Actor combo ---
            actor_combo = QComboBox()
            actor_combo.addItems(actor_names)
            assigned_actor_id = self._current_assignments.get(role_id)
            actor_index = 0
            if assigned_actor_id and assigned_actor_id in valid_actor_ids:
                try:
                    actor_index = valid_actor_ids.index(assigned_actor_id)
                except ValueError:
                    pass
            actor_combo.setCurrentIndex(actor_index)
            actor_combo.currentIndexChanged.connect(
                lambda index, r_id=role_id, ids=list(actor_ids): self._on_actor_assigned(
                    r_id, ids[index] if 0 <= index < len(ids) else ""
                )
            )
            role_form.addRow("Actor:", actor_combo)

            # --- Override combos (Costume / Pose / Expression) ---
            role_overrides = self._current_overrides.get(role_id, {})
            override_specs = [
                ("Costume:", costume_names, costume_ids, "costume_id"),
                ("Pose:", pose_names, pose_ids, "pose_id"),
                ("Expression:", expression_names, expression_ids, "expression_id"),
            ]
            self._role_override_combos[role_id] = {}
            for label, names, ids, key in override_specs:
                ov_combo = QComboBox()
                ov_combo.addItems(names)
                saved_id = role_overrides.get(key, "")
                ov_index = 0
                if saved_id and saved_id in ids:
                    try:
                        ov_index = ids.index(saved_id)
                    except ValueError:
                        pass
                ov_combo.setCurrentIndex(ov_index)
                ov_combo.currentIndexChanged.connect(
                    lambda index, r_id=role_id, k=key, id_list=list(ids): self._on_override_assigned(
                        r_id, k, id_list[index] if 0 <= index < len(id_list) else ""
                    )
                )
                self._role_override_combos[role_id][key] = ov_combo
                role_form.addRow(label, ov_combo)

            layout.addWidget(role_group)

        layout.addStretch()
        
        # 3. 新しいウィジェットをレイアウトの所定の位置に挿入
        self.prompt_gen_layout.insertWidget(1, self.role_assignment_widget)

    def get_current_overrides(self) -> Dict[str, Dict[str, Optional[str]]]:
        return self._current_overrides.copy()

    @Slot(int)
    def _on_scene_changed(self, index: int):
        scene_list = self._get_recent_first_items("scenes")
        new_scene_id = (
            getattr(scene_list[index], "id", None)
            if 0 <= index < len(scene_list)
            else None
        )

        if new_scene_id != self._current_scene_id:
            self.sceneChanged.emit(new_scene_id or "")

    def _get_recent_first_items(self, db_key: str) -> List[Any]:
        """created_at の降順（新しい順）で並べたリストを返す。"""
        items = list(self._db_data_ref.get(db_key, {}).values())
        return sorted(items, key=lambda item: getattr(item, "created_at", 0) or 0, reverse=True)

    @Slot(str, str)
    def _on_actor_assigned(self, role_id: str, actor_id: str):
        if actor_id:
            self._current_assignments[role_id] = actor_id
        elif role_id in self._current_assignments:
            del self._current_assignments[role_id]
        self.assignmentChanged.emit(self._current_assignments.copy())

    @Slot(str, str, str)
    def _on_override_assigned(self, role_id: str, key: str, value: str):
        if role_id not in self._current_overrides:
            self._current_overrides[role_id] = {}
        if value:
            self._current_overrides[role_id][key] = value
        else:
            self._current_overrides[role_id].pop(key, None)