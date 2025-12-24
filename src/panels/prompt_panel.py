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
)
from PySide6.QtCore import Qt, Signal, Slot
from typing import Dict, List, Optional, Any, Tuple
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
)  # ★ SDParams をインポート


class PromptPanel(QWidget):
    # --- ▼▼▼ シグナル定義を変更 ▼▼▼ ---
    generatePromptsClicked = Signal()
    executeGenerationClicked = Signal()
    sceneChanged = Signal(str)
    assignmentChanged = Signal(dict)
    # --- ▲▲▲ 変更ここまで ▲▲▲ ---

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
        # self.update_scene_combo() # This call is removed to give MainWindow control over UI updates

    def set_current_scene(self, scene_id: Optional[str]):
        """MainWindow から現在のシーンIDが変更されたときに呼ばれます。"""
        if self._current_scene_id != scene_id:
            self._current_scene_id = scene_id
            print(f"[DEBUG] PromptPanel.set_current_scene: Scene set to {scene_id}.")
            # コンボボックスの選択状態を更新
            scene_list = sorted(
                self._db_data_ref.get("scenes", {}).values(),
                key=lambda s: getattr(s, "name", "").lower(),  # name がない場合も考慮
            )
            scene_ids = [getattr(s, "id", None) for s in scene_list]
            try:
                # None や空文字の ID がリストに含まれないようにフィルタリング
                valid_scene_ids = [sid for sid in scene_ids if sid]
                index = (
                    valid_scene_ids.index(scene_id)
                    if scene_id in valid_scene_ids
                    else -1
                )
                self.scene_combo.blockSignals(True)
                # インデックスが有効なら設定、無効なら未選択 (-1)
                self.scene_combo.setCurrentIndex(index if index >= 0 else -1)
                self.scene_combo.blockSignals(False)
            except ValueError:
                print(f"[DEBUG] Scene ID {scene_id} not found in combo after update.")
                self.scene_combo.setCurrentIndex(-1)  # 見つからない場合は未選択に
            self.build_role_assignment_ui()

    def set_assignments(self, assignments: Dict[str, str]):
        """MainWindow から初期の配役を設定します。"""
        self._current_assignments = assignments.copy()
        print(
            f"[DEBUG] PromptPanel.set_assignments: Initial assignments loaded: {self._current_assignments}"
        )
        # UI が構築された後に呼ぶ必要があるため、ここでは build_role_assignment_ui は呼ばない

    def _init_ui(self):
        """UI要素を初期化します。"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        group = QGroupBox("Prompt Generation")
        self.prompt_gen_layout = QVBoxLayout(group)

        # シーン選択
        scene_layout = QHBoxLayout()
        scene_layout.addWidget(QLabel("1. Select Scene:"))
        self.scene_combo = QComboBox()
        self.scene_combo.currentIndexChanged.connect(self._on_scene_changed)
        scene_layout.addWidget(self.scene_combo)
        self.prompt_gen_layout.addLayout(scene_layout)

        # 役割割り当て
        self.role_assignment_widget = QWidget()
        self.role_assignment_widget.setObjectName("RoleAssignmentWidgetContainer")
        self.prompt_gen_layout.addWidget(self.role_assignment_widget)

        # --- ▼▼▼ デバッグチェックボックスを追加 ▼▼▼ ---
        self.debug_mode_checkbox = QCheckBox("Debug Mode (Reduce Steps/Size)")
        self.debug_mode_checkbox.setToolTip(
            "If checked, reduces steps, width, and height by 30% (x0.7) when executing generation."
        )
        self.prompt_gen_layout.addWidget(self.debug_mode_checkbox)

        # ボタン
        generate_preview_btn = QPushButton("🔄 Generate Prompt Preview")
        generate_preview_btn.setStyleSheet("background-color: #ffc107;")
        generate_preview_btn.clicked.connect(self.generatePromptsClicked)

        self.execute_btn = QPushButton(
            "🚀 Execute Image Generation (Run Batch)"
        )  # 1. 'self.' を追加
        self.execute_btn.setStyleSheet("background-color: #28a745; color: white;")
        self.execute_btn.clicked.connect(self.executeGenerationClicked)

        self.prompt_gen_layout.addWidget(generate_preview_btn)
        self.prompt_gen_layout.addWidget(self.execute_btn)  # 2. 'self.' を追加
        main_layout.addWidget(group)

    # --- ▼▼▼ デバッグ状態取得メソッドを追加 ▼▼▼ ---
    def is_debug_mode_enabled(self) -> bool:
        """デバッグモードのチェックボックスの状態を返します。"""
        return self.debug_mode_checkbox.isChecked()

    def update_scene_combo(self):
        """シーン選択コンボボックスの内容を更新します。"""
        print("[DEBUG] PromptPanel.update_scene_combo called.")
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
            scene_ids = [getattr(s, "id", None) for s in scene_list]
            valid_scene_ids = [sid for sid in scene_ids if sid]  # None や空を除外
            self.scene_combo.addItems(
                [getattr(s, "name", "Unnamed") for s in scene_list]
            )

            current_scene_index = -1  # デフォルトは未選択
            if self._current_scene_id and self._current_scene_id in valid_scene_ids:
                try:
                    current_scene_index = valid_scene_ids.index(self._current_scene_id)
                except ValueError:
                    # ID がリストにない場合 (古い設定など) -> 最初の有効なシーンを選択
                    if valid_scene_ids:
                        self._current_scene_id = valid_scene_ids[0]
                        current_scene_index = 0
                    else:
                        self._current_scene_id = None
            elif valid_scene_ids:  # 現在IDがない場合は最初の有効なシーンを選択
                self._current_scene_id = valid_scene_ids[0]
                current_scene_index = 0
            else:  # 有効なシーンが一つもない
                self._current_scene_id = None

            if current_scene_index >= 0:
                self.scene_combo.setCurrentIndex(current_scene_index)
                self.scene_combo.setEnabled(True)
            else:
                self.scene_combo.setCurrentIndex(-1)  # setCurrentIndex(-1) は未選択状態
                self.scene_combo.setEnabled(False)

        self.scene_combo.blockSignals(False)
        print(
            f"[DEBUG] PromptPanel.update_scene_combo complete. Current scene: {self._current_scene_id}"
        )
        # コンボ更新後に役割割り当ても更新
        self.build_role_assignment_ui()

    def build_role_assignment_ui(self):
        """役割割り当てUIを動的に構築します。現在のシーンに紐づく *単一のカット* の配役を使用します。"""
        print(
            f"[DEBUG] PromptPanel.build_role_assignment_ui called for scene ID: {self._current_scene_id}"
        )
        self._role_override_combos.clear()
        self._current_overrides.clear()
        layout = self.role_assignment_widget.layout()
        # --- Layout Clear ---
        if layout is None:
            layout = QVBoxLayout(self.role_assignment_widget)
        else:  # クリア処理
            item = layout.takeAt(0)
            while item is not None:
                widget = item.widget()
                layout_item = item.layout()
                if widget:
                    widget.deleteLater()
                elif layout_item:
                    while layout_item.count():
                        inner = layout_item.takeAt(0)
                        if inner is None:
                            break
                        inner_w = inner.widget()
                        if inner_w:
                            inner_w.deleteLater()
                        inner_l = inner.layout()  # さらにネストも考慮
                        if inner_l:
                            while inner_l.count():
                                deep = inner_l.takeAt(0)
                                if deep is None:
                                    break
                                deep_w = deep.widget()
                                if deep_w:
                                    deep_w.deleteLater()
                            inner_l.deleteLater()
                    layout_item.deleteLater()
                # del item # item オブジェクト自体の削除は takeAt で行われるはず
                item = layout.takeAt(0)  # 次のアイテムを取得

        layout.addWidget(QLabel("2. Assign Actors to Roles:"))
        current_scene = (
            self._db_data_ref.get("scenes", {}).get(self._current_scene_id)
            if self._current_scene_id
            else None
        )

        # --- Get Roles from the single Cut ---
        selected_cut: Optional[Cut] = None
        roles_to_display: List[SceneRole] = []
        roles_with_empty_costumes: Set[str] = set()
        roles_with_empty_poses: Set[str] = set()
        roles_with_empty_expressions: Set[str] = set()

        if current_scene:
            cut_id = getattr(current_scene, "cut_id", None)
            if cut_id:
                selected_cut = self._db_data_ref.get("cuts", {}).get(cut_id)
                if selected_cut and isinstance(selected_cut, Cut):
                    roles_to_display = getattr(selected_cut, "roles", [])
                    scene_assignments_map = {
                        ra.role_id: ra for ra in current_scene.role_assignments
                    }
                    for role in roles_to_display:
                        if not role.id:
                            continue
                        role_assignment = scene_assignments_map.get(role.id)
                        if not role_assignment or not role_assignment.costume_ids:
                            roles_with_empty_costumes.add(role.id)
                        if not role_assignment or not role_assignment.pose_ids:
                            roles_with_empty_poses.add(role.id)
                        if not role_assignment or not role_assignment.expression_ids:
                            roles_with_empty_expressions.add(role.id)
                    print(f"[DEBUG] Using roles from Cut ID: {cut_id}")
                else:
                    print(f"[WARN] Cut object not found or invalid for ID: {cut_id}")
                    layout.addWidget(QLabel(f"(Error: Cut '{cut_id}' not found)"))
            else:
                layout.addWidget(
                    QLabel("(このシーンにはカットが割り当てられていません)")
                )
        elif not current_scene:
            layout.addWidget(QLabel("No scene selected."))
            if self._current_assignments:
                self._current_assignments = {}
                self.assignmentChanged.emit({})
            layout.addStretch()
            return

        # --- Actor List ---
        actor_list = sorted(
            self._db_data_ref.get("actors", {}).values(),
            key=lambda a: getattr(a, "name", "").lower(),
        )
        actor_names = ["-- Select Actor --"] + [
            getattr(a, "name", "Unnamed") for a in actor_list
        ]
        actor_ids = [""] + [getattr(a, "id", None) for a in actor_list]
        valid_actor_ids = [aid for aid in actor_ids if aid is not None]  # Noneを除外

        def get_appearance_items(
            db_key: str, default_label: str
        ) -> List[Tuple[str, Optional[str]]]:
            data = self._db_data_ref.get(db_key, {})
            sorted_items = sorted(data.values(), key=lambda a: getattr(a, "name", ""))
            items_list = [(f"({default_label})", "default")]  # "default" を識別子に
            for item in sorted_items:
                item_id = getattr(item, "id", None)
                item_name = getattr(item, "name", "Unnamed")
                if item_id:
                    items_list.append((f"{item_name} ({item_id})", item_id))
            return items_list

        costume_items = get_appearance_items("costumes", "Actor Default Costume")
        pose_items = get_appearance_items("poses", "Actor Default Pose")
        expression_items = get_appearance_items(
            "expressions", "Actor Default Expression"
        )

        # --- Build UI for Roles ---
        if (
            not roles_to_display
            and current_scene
            and getattr(current_scene, "cut_id", None)
        ):
            layout.addWidget(QLabel("(選択されたカットには配役が定義されていません)"))

        # Remove outdated assignments
        valid_role_ids = {
            getattr(role, "id", None)
            for role in roles_to_display
            if getattr(role, "id", None)
        }
        current_assignments_updated = False
        keys_to_delete = [
            role_id
            for role_id in self._current_assignments
            if role_id not in valid_role_ids
        ]
        if keys_to_delete:
            for key in keys_to_delete:
                del self._current_assignments[key]
            current_assignments_updated = True
            print(
                f"[DEBUG] Removed assignments for non-existent roles: {keys_to_delete}"
            )

        for role in roles_to_display:
            role_id = getattr(role, "id", None)
            role_name = getattr(role, "name_in_scene", "Unknown Role")
            if not role_id:
                continue  # ID がなければスキップ

            role_layout = QHBoxLayout()
            label_text = f"{role_name} ([{role_id.upper()}])"
            role_layout.addWidget(QLabel(label_text))
            combo = QComboBox()
            combo.addItems(actor_names)

            # Set current assignment
            assigned_actor_id = self._current_assignments.get(role_id)
            current_index = 0
            if assigned_actor_id and assigned_actor_id in valid_actor_ids:
                try:
                    # actor_ids には "" が含まれるので、valid_actor_ids でインデックスを探す
                    # インデックスは actor_names/actor_ids に合わせるため +1 する
                    current_index = valid_actor_ids.index(assigned_actor_id) + 1
                except ValueError:
                    print(
                        f"[DEBUG] Assigned actor ID '{assigned_actor_id}' for role '{role_id}' not found. Resetting."
                    )
                    if role_id in self._current_assignments:
                        del self._current_assignments[role_id]
                        current_assignments_updated = True

            combo.setCurrentIndex(current_index)
            # currentIndexChanged の ids も valid_actor_ids をベースに actor_ids を再構築
            # → lambda 内で ids=list(actor_ids) を渡しているので、actor_ids をそのまま使う
            combo.currentIndexChanged.connect(
                lambda index,
                r_id=role_id,
                ids=list(actor_ids): self._on_actor_assigned(
                    r_id, ids[index] if 0 <= index < len(ids) else ""
                )
            )
            role_layout.addWidget(combo)
            layout.addLayout(role_layout)

            self._role_override_combos[role_id] = {}
            override_form_layout = QFormLayout()
            override_form_layout.setContentsMargins(5, 5, 5, 5)

            def add_override_combo(
                role_id: str,
                key: str,  # "costume_id", "pose_id", ...
                label: str,
                items_list: List[Tuple[str, Optional[str]]],
            ):
                combo = QComboBox()
                for name, item_id_data in items_list:
                    combo.addItem(name, item_id_data)

                # 初期値は "default"
                current_override_id = self._current_overrides.get(role_id, {}).get(
                    key, "default"
                )
                found_index = combo.findData(current_override_id)
                combo.setCurrentIndex(found_index if found_index != -1 else 0)

                combo.currentIndexChanged.connect(
                    lambda index,
                    r_id=role_id,
                    k=key,
                    c=combo: self._on_override_assigned(r_id, k, c.itemData(index))
                )

                override_form_layout.addRow(f"  {label}:", combo)
                self._role_override_combos[role_id][key] = combo

            if role_id in roles_with_empty_costumes:
                add_override_combo(role_id, "costume_id", "Costume", costume_items)
            if role_id in roles_with_empty_poses:
                add_override_combo(role_id, "pose_id", "Pose", pose_items)
            if role_id in roles_with_empty_expressions:
                add_override_combo(
                    role_id, "expression_id", "Expression", expression_items
                )

            if override_form_layout.rowCount() > 0:  # コンボが追加されたら
                override_group = QGroupBox()
                override_group.setLayout(override_form_layout)
                override_group.setStyleSheet(
                    "QGroupBox { margin-top: 0px; margin-left: 10px; border: 1px solid #ddd; padding: 2px; }"
                )
                layout.addWidget(override_group)  # ★ QVBoxLayout に追加

        layout.addStretch()
        print("[DEBUG] PromptPanel.build_role_assignment_ui complete.")
        if current_assignments_updated:
            self.assignmentChanged.emit(self._current_assignments.copy())

    @Slot(str, str, str)
    def _on_override_assigned(self, role_id: str, key: str, override_id: Optional[str]):
        """Appearance オーバーライドの選択変更"""
        if role_id not in self._current_overrides:
            self._current_overrides[role_id] = {}

        if override_id and override_id != "default":
            self._current_overrides[role_id][key] = override_id
        elif key in self._current_overrides[role_id]:
            # "default" が選ばれたら、キーごと削除（=オーバーライドなし）
            del self._current_overrides[role_id][key]
            if not self._current_overrides[role_id]:  # ロールが空になったら
                del self._current_overrides[role_id]

        print(f"[DEBUG] Updated internal overrides: {self._current_overrides}")
        # ★ オーバーライド変更時も config 保存のトリガーとする
        self.assignmentChanged.emit(self._current_assignments.copy())

    # --- ▲▲▲ 追加 ▲▲▲ ---

    # --- ▼▼▼ Getter追加 ▼▼▼ ---
    def get_current_overrides(self) -> Dict[str, Dict[str, Optional[str]]]:
        return self._current_overrides.copy()

    @Slot(int)
    def _on_scene_changed(self, index: int):
        """シーンコンボボックスの選択が変更されたときの処理。"""
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
            print(f"[DEBUG] PromptPanel: Scene selection changed to {new_scene_id}")
            self._current_scene_id = new_scene_id
            self.sceneChanged.emit(new_scene_id or "")

    @Slot(str, str)
    def _on_actor_assigned(self, role_id: str, actor_id: str):
        """役割割り当てコンボボックスの選択変更を内部辞書に反映し、シグナルを発行します。"""
        print(
            f"[DEBUG] PromptPanel._on_actor_assigned: Role={role_id}, Actor={actor_id}"
        )
        if actor_id:
            self._current_assignments[role_id] = actor_id
        elif role_id in self._current_assignments:
            del self._current_assignments[role_id]
        print(f"[DEBUG] Updated internal assignments: {self._current_assignments}")
        self.assignmentChanged.emit(self._current_assignments.copy())
