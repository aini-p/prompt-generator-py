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
)
from PySide6.QtCore import Qt, Signal, Slot
from typing import Dict, List, Optional, Any
from ..models import Scene, Actor, Style  # 必要なモデル


class PromptPanel(QWidget):
    # --- シグナル定義 ---
    generatePromptsClicked = Signal()
    executeGenerationClicked = Signal()
    sceneChanged = Signal(str)  # 新しい Scene ID
    assignmentChanged = Signal(dict)
    styleChanged = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._db_data_ref: Dict[str, Dict[str, Any]] = {}
        self._current_assignments: Dict[str, str] = {}
        self._current_scene_id: Optional[str] = None
        self._current_style_id: Optional[str] = None
        self._init_ui()

    def set_data_reference(self, db_data: Dict[str, Dict[str, Any]]):
        """MainWindow からデータへの参照を設定します。"""
        self._db_data_ref = db_data
        self.update_scene_combo()
        self._update_style_combo()

    def set_current_scene(self, scene_id: Optional[str]):
        """MainWindow から現在のシーンIDが変更されたときに呼ばれます。"""
        if self._current_scene_id != scene_id:
            self._current_scene_id = scene_id
            print(
                f"[DEBUG] PromptPanel.set_current_scene: Scene set to {scene_id}. Assignments kept temporarily."
            )
            # コンボボックスの選択状態を更新
            scene_list = sorted(
                self._db_data_ref.get("scenes", {}).values(),
                key=lambda s: s.name.lower(),
            )
            scene_ids = [s.id for s in scene_list]
            try:
                index = scene_ids.index(scene_id) if scene_id in scene_ids else -1
                self.scene_combo.blockSignals(True)
                self.scene_combo.setCurrentIndex(index)
                self.scene_combo.blockSignals(False)
            except ValueError:
                print(f"[DEBUG] Scene ID {scene_id} not found in combo after update.")
                self.scene_combo.setCurrentIndex(-1)  # 見つからない場合は未選択に
            self.build_role_assignment_ui()

    # --- ★ 追加: 現在の Style を設定するメソッド ---
    def set_current_style(self, style_id: Optional[str]):
        """MainWindow から現在の Style ID が設定されたときに呼ばれます。"""
        if self._current_style_id != style_id:
            self._current_style_id = style_id
            # コンボボックスの選択状態を更新
            style_ids = [""] + [
                s.id
                for s in sorted(
                    self._db_data_ref.get("styles", {}).values(),
                    key=lambda s: s.name.lower(),
                )
            ]
            try:
                index = (
                    style_ids.index(style_id) if style_id in style_ids else 0
                )  # 未選択は 0 ("(None)")
                self.style_combo.blockSignals(True)
                self.style_combo.setCurrentIndex(index)
                self.style_combo.blockSignals(False)
            except ValueError:
                pass  # IDが見つからない場合

    def set_assignments(self, assignments: Dict[str, str]):
        """MainWindow から初期の配役を設定します。"""
        self._current_assignments = assignments.copy()
        print(
            f"[DEBUG] PromptPanel.set_assignments: Initial assignments loaded: {self._current_assignments}"
        )
        # UI が構築された後に呼ぶ必要があるため、ここでは build_role_assignment_ui は呼ばない
        # set_current_scene -> build_role_assignment_ui の流れで反映される想定

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

        # --- ★ Style 選択を追加 ---
        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel("Style:"))
        self.style_combo = QComboBox()
        self.style_combo.currentIndexChanged.connect(self._on_style_changed)
        style_layout.addWidget(self.style_combo)
        self.prompt_gen_layout.addLayout(style_layout)

        # 役割割り当て (動的UI用ウィジェット)
        self.role_assignment_widget = QWidget()
        self.role_assignment_widget.setObjectName("RoleAssignmentWidgetContainer")
        self.prompt_gen_layout.addWidget(self.role_assignment_widget)
        # build_role_assignment_ui はデータ参照設定後/シーン変更後に呼ばれる

        # ボタン
        generate_preview_btn = QPushButton("🔄 Generate Prompt Preview")
        generate_preview_btn.setStyleSheet("background-color: #ffc107;")
        generate_preview_btn.clicked.connect(
            self.generatePromptsClicked
        )  # シグナル発行

        execute_btn = QPushButton("🚀 Execute Image Generation (Run Batch)")
        execute_btn.setStyleSheet("background-color: #28a745; color: white;")
        execute_btn.clicked.connect(self.executeGenerationClicked)  # シグナル発行

        self.prompt_gen_layout.addWidget(generate_preview_btn)
        self.prompt_gen_layout.addWidget(execute_btn)

        main_layout.addWidget(group)

    def update_scene_combo(self):
        """シーン選択コンボボックスの内容を更新します。"""
        print("[DEBUG] PromptPanel.update_scene_combo called.")
        self.scene_combo.blockSignals(True)
        self.scene_combo.clear()
        scene_list = sorted(
            self._db_data_ref.get("scenes", {}).values(), key=lambda s: s.name.lower()
        )

        if not scene_list:
            self.scene_combo.addItem("No scenes available")
            self.scene_combo.setEnabled(False)
            self._current_scene_id = None
        else:
            scene_ids = [s.id for s in scene_list]
            self.scene_combo.addItems([s.name for s in scene_list])

            current_scene_index = 0
            if self._current_scene_id and self._current_scene_id in scene_ids:
                try:
                    current_scene_index = scene_ids.index(self._current_scene_id)
                except ValueError:
                    self._current_scene_id = scene_ids[0]  # フォールバック
            elif scene_ids:
                self._current_scene_id = scene_ids[0]
            else:
                self._current_scene_id = None
                current_scene_index = -1

            if self._current_scene_id is not None and current_scene_index >= 0:
                self.scene_combo.setCurrentIndex(current_scene_index)
                self.scene_combo.setEnabled(True)
            else:
                self.scene_combo.setCurrentIndex(-1)
                self.scene_combo.setEnabled(False)

        self.scene_combo.blockSignals(False)
        print(
            f"[DEBUG] PromptPanel.update_scene_combo complete. Current scene: {self._current_scene_id}"
        )
        # コンボ更新後に役割割り当ても更新
        self.build_role_assignment_ui()

    # --- ★ 追加: Style コンボボックス更新メソッド ---
    def _update_style_combo(self):
        """Style 選択コンボボックスの内容を更新します。"""
        print("[DEBUG] PromptPanel._update_style_combo called.")
        self.style_combo.blockSignals(True)
        self.style_combo.clear()
        self.style_combo.addItem("(None)", "")  # itemData に空文字
        style_list = sorted(
            self._db_data_ref.get("styles", {}).values(), key=lambda s: s.name.lower()
        )

        if not style_list:
            self.style_combo.setEnabled(False)
        else:
            style_ids = [""]  # 先頭は "(None)"
            for style in style_list:
                self.style_combo.addItem(style.name, style.id)  # itemData に ID
                style_ids.append(style.id)

            current_style_index = 0
            if self._current_style_id and self._current_style_id in style_ids:
                try:
                    current_style_index = style_ids.index(self._current_style_id)
                except ValueError:
                    self._current_style_id = None  # 見つからなければリセット
            # else: self._current_style_id = None # "(None)" が選択されている状態

            self.style_combo.setCurrentIndex(current_style_index)
            self.style_combo.setEnabled(True)

        self.style_combo.blockSignals(False)
        print(
            f"[DEBUG] PromptPanel._update_style_combo complete. Current style: {self._current_style_id}"
        )

    def build_role_assignment_ui(self):
        """役割割り当てUIを動的に構築します。"""
        print(
            f"[DEBUG] PromptPanel.build_role_assignment_ui called for scene ID: {self._current_scene_id}"
        )
        layout = self.role_assignment_widget.layout()
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
                        inner_w = inner.widget()
                        if inner_w:
                            inner_w.deleteLater()
                    layout_item.deleteLater()
                item = layout.takeAt(0)

        layout.addWidget(QLabel("2. Assign Actors to Roles:"))
        current_scene = (
            self._db_data_ref.get("scenes", {}).get(self._current_scene_id)
            if self._current_scene_id
            else None
        )

        if not current_scene:
            layout.addWidget(QLabel("No scene selected."))
            layout.addStretch()
            # シーンがない場合は内部割り当てもクリアすべきか？ -> クリアする
            if self._current_assignments:  # クリアする場合のみ通知
                self._current_assignments = {}
                self.assignmentChanged.emit({})  # MainWindow に通知
            return

        actor_list = list(self._db_data_ref.get("actors", {}).values())
        actor_names = ["-- Select Actor --"] + [a.name for a in actor_list]
        actor_ids = [""] + [a.id for a in actor_list]

        if not current_scene.roles:
            layout.addWidget(QLabel("(このシーンには配役が定義されていません)"))

        # 不要になった配役を削除
        valid_role_ids = {role.id for role in current_scene.roles}
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

        for role in current_scene.roles:
            role_layout = QHBoxLayout()
            label_text = f"{role.name_in_scene} ([{role.id.upper()}])"
            role_layout.addWidget(QLabel(label_text))
            combo = QComboBox()
            combo.addItems(actor_names)

            assigned_actor_id = self._current_assignments.get(role.id)  # 内部状態を参照
            current_index = 0
            if assigned_actor_id and assigned_actor_id in actor_ids:
                try:
                    current_index = actor_ids.index(assigned_actor_id)
                except ValueError:
                    # 割り当てられていた Actor が削除された場合など
                    print(
                        f"[DEBUG] Assigned actor ID '{assigned_actor_id}' for role '{role.id}' not found. Resetting."
                    )
                    if role.id in self._current_assignments:
                        del self._current_assignments[role.id]  # 内部状態からも削除
                        current_assignments_updated = True

            combo.setCurrentIndex(current_index)
            # 選択変更時に MainWindow のメソッドを直接呼ぶ代わりに、辞書を直接更新
            combo.currentIndexChanged.connect(
                lambda index,
                r_id=role.id,
                ids=list(actor_ids): self._on_actor_assigned(
                    r_id, ids[index] if 0 <= index < len(ids) else ""
                )
            )
            role_layout.addWidget(combo)
            layout.addLayout(role_layout)

        layout.addStretch()
        print("[DEBUG] PromptPanel.build_role_assignment_ui complete.")
        # 不要な配役を削除した場合、変更を通知
        if current_assignments_updated:
            self.assignmentChanged.emit(self._current_assignments.copy())

    @Slot(int)
    def _on_scene_changed(self, index: int):
        """シーンコンボボックスの選択が変更されたときの処理。"""
        scene_list = sorted(
            self._db_data_ref.get("scenes", {}).values(), key=lambda s: s.name.lower()
        )
        new_scene_id = scene_list[index].id if 0 <= index < len(scene_list) else None

        if new_scene_id != self._current_scene_id:
            print(f"[DEBUG] PromptPanel: Scene selection changed to {new_scene_id}")
            self._current_scene_id = new_scene_id
            # self._current_assignments = {} # ← この行を削除またはコメントアウト
            self.sceneChanged.emit(new_scene_id or "")  # MainWindow に通知
            self.build_role_assignment_ui()  # UI 更新 (配役維持を試みる)

    # --- ★ 追加: Style 変更ハンドラ ---
    @Slot(int)
    def _on_style_changed(self, index: int):
        """Style コンボボックスの選択が変更されたときの処理。"""
        new_style_id = self.style_combo.itemData(
            index
        )  # itemData (ID または "") を取得
        if new_style_id != self._current_style_id:
            print(f"[DEBUG] PromptPanel: Style changed to {new_style_id}")
            self._current_style_id = new_style_id if new_style_id else None
            self.styleChanged.emit(
                new_style_id or ""
            )  # MainWindow に通知 (None は空文字で)

    # --- ★ 追加ここまで ---

    @Slot(str, str)
    def _on_actor_assigned(self, role_id: str, actor_id: str):
        """役割割り当てコンボボックスの選択変更を内部辞書に反映し、シグナルを発行します。"""
        print(
            f"[DEBUG] PromptPanel._on_actor_assigned: Role={role_id}, Actor={actor_id}"
        )
        # 内部辞書 (_current_assignments) を更新
        if actor_id:
            self._current_assignments[role_id] = actor_id
        elif role_id in self._current_assignments:
            del self._current_assignments[role_id]
        print(f"[DEBUG] Updated internal assignments: {self._current_assignments}")
        # 変更後の内部辞書を MainWindow に通知
        self.assignmentChanged.emit(self._current_assignments.copy())  # コピーを渡す
