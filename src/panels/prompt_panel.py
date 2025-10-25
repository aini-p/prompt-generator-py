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
from ..models import (
    Scene,
    Actor,
    Style,
    Cut,
    SceneRole,
    StableDiffusionParams,
)  # ★ SDParams をインポート


class PromptPanel(QWidget):
    # --- ▼▼▼ シグナル定義を変更 ▼▼▼ ---
    generatePromptsClicked = Signal()
    executeGenerationClicked = Signal()
    sceneChanged = Signal(str)
    assignmentChanged = Signal(dict)
    styleChanged = Signal(str)
    # editSdParamsClicked = Signal() # ← 削除
    sdParamsChanged = Signal(str)  # ★ 追加
    # --- ▲▲▲ 変更ここまで ▲▲▲ ---

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._db_data_ref: Dict[str, Dict[str, Any]] = {}
        self._current_assignments: Dict[str, str] = {}
        self._current_scene_id: Optional[str] = None
        self._current_style_id: Optional[str] = None
        self._current_sd_param_id: Optional[str] = None  # ★ 追加
        self._init_ui()

    def set_data_reference(self, db_data: Dict[str, Dict[str, Any]]):
        self._db_data_ref = db_data
        self.update_scene_combo()
        self._update_style_combo()
        self._update_sd_params_combo()  # ★ 追加

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

    def set_current_style(self, style_id: Optional[str]):
        """MainWindow から現在の Style ID が設定されたときに呼ばれます。"""
        if self._current_style_id != style_id:
            self._current_style_id = style_id
            # コンボボックスの選択状態を更新
            style_ids = [""] + [
                s.id
                for s in sorted(
                    self._db_data_ref.get("styles", {}).values(),
                    key=lambda s: getattr(s, "name", "").lower(),
                )
                if getattr(s, "id", None)  # ID があるものだけ
            ]
            try:
                index = (
                    style_ids.index(style_id) if style_id in style_ids else 0
                )  # 未選択 or 見つからなければ 0 ("(None)")
                self.style_combo.blockSignals(True)
                self.style_combo.setCurrentIndex(index)
                self.style_combo.blockSignals(False)
            except ValueError:
                self.style_combo.setCurrentIndex(0)  # エラー時も "(None)"

    # --- ▼▼▼ set_current_sd_params を追加 ▼▼▼ ---
    def set_current_sd_params(self, sd_param_id: Optional[str]):
        """MainWindow から現在の SD Param ID が設定されたときに呼ばれます。"""
        if self._current_sd_param_id != sd_param_id:
            self._current_sd_param_id = sd_param_id
            # コンボボックスの選択状態を更新
            param_ids = [""] + [
                p.id
                for p in sorted(
                    self._db_data_ref.get("sdParams", {}).values(),
                    key=lambda p: getattr(p, "name", "").lower(),
                )
                if getattr(p, "id", None)  # ID があるものだけ
            ]
            try:
                index = (
                    param_ids.index(sd_param_id) if sd_param_id in param_ids else 0
                )  # 未選択 or 見つからなければ 0 ("(None)")
                self.sd_params_combo.blockSignals(True)
                self.sd_params_combo.setCurrentIndex(index)
                self.sd_params_combo.blockSignals(False)
            except ValueError:
                self.sd_params_combo.setCurrentIndex(0)  # エラー時も "(None)"

    # --- ▲▲▲ 追加ここまで ▲▲▲ ---

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

        # --- Style 選択と SD Params 選択に変更 ---
        style_sd_layout = QHBoxLayout()

        # Style 選択部分
        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel("Style:"))
        self.style_combo = QComboBox()
        self.style_combo.currentIndexChanged.connect(self._on_style_changed)
        style_layout.addWidget(self.style_combo, 1)
        style_sd_layout.addLayout(style_layout)

        # SD Params 選択部分
        sd_params_layout = QHBoxLayout()
        sd_params_layout.addWidget(QLabel("SD Params:"))
        self.sd_params_combo = QComboBox()
        self.sd_params_combo.currentIndexChanged.connect(self._on_sd_params_changed)
        sd_params_layout.addWidget(self.sd_params_combo, 1)
        style_sd_layout.addLayout(sd_params_layout)  # ★ SD Params レイアウトを追加

        self.prompt_gen_layout.addLayout(style_sd_layout)
        # --- 修正ここまで ---

        # 役割割り当て
        self.role_assignment_widget = QWidget()
        self.role_assignment_widget.setObjectName("RoleAssignmentWidgetContainer")
        self.prompt_gen_layout.addWidget(self.role_assignment_widget)

        # ボタン
        generate_preview_btn = QPushButton("🔄 Generate Prompt Preview")
        generate_preview_btn.setStyleSheet("background-color: #ffc107;")
        generate_preview_btn.clicked.connect(self.generatePromptsClicked)

        execute_btn = QPushButton("🚀 Execute Image Generation (Run Batch)")
        execute_btn.setStyleSheet("background-color: #28a745; color: white;")
        execute_btn.clicked.connect(self.executeGenerationClicked)

        self.prompt_gen_layout.addWidget(generate_preview_btn)
        self.prompt_gen_layout.addWidget(execute_btn)

        main_layout.addWidget(group)

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

    def _update_style_combo(self):
        """Style 選択コンボボックスの内容を更新します。"""
        print("[DEBUG] PromptPanel._update_style_combo called.")
        self.style_combo.blockSignals(True)
        self.style_combo.clear()
        self.style_combo.addItem("(None)", "")  # itemData に空文字
        style_list = sorted(
            self._db_data_ref.get("styles", {}).values(),
            key=lambda s: getattr(s, "name", "").lower(),
        )

        if not style_list:
            self.style_combo.setEnabled(False)
        else:
            style_ids = [""]  # 先頭は "(None)"
            for style in style_list:
                style_id = getattr(style, "id", None)
                style_name = getattr(style, "name", "Unnamed")
                if style_id:
                    self.style_combo.addItem(style_name, style_id)  # itemData に ID
                    style_ids.append(style_id)

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

    # --- ▼▼▼ _update_sd_params_combo を追加 ▼▼▼ ---
    def _update_sd_params_combo(self):
        """SD Params 選択コンボボックスの内容を更新します。"""
        print("[DEBUG] PromptPanel._update_sd_params_combo called.")
        self.sd_params_combo.blockSignals(True)
        self.sd_params_combo.clear()
        self.sd_params_combo.addItem("(None)", "")  # itemData に空文字
        param_list = sorted(
            self._db_data_ref.get("sdParams", {}).values(),
            key=lambda p: getattr(p, "name", "").lower(),
        )

        if not param_list:
            self.sd_params_combo.setEnabled(False)
        else:
            param_ids = [""]  # 先頭は "(None)"
            for param in param_list:
                param_id = getattr(param, "id", None)
                param_name = getattr(param, "name", "Unnamed")
                if param_id:
                    self.sd_params_combo.addItem(param_name, param_id)  # itemData に ID
                    param_ids.append(param_id)

            current_param_index = 0
            if self._current_sd_param_id and self._current_sd_param_id in param_ids:
                try:
                    current_param_index = param_ids.index(self._current_sd_param_id)
                except ValueError:
                    self._current_sd_param_id = None

            self.sd_params_combo.setCurrentIndex(current_param_index)
            self.sd_params_combo.setEnabled(True)

        self.sd_params_combo.blockSignals(False)
        print(
            f"[DEBUG] PromptPanel._update_sd_params_combo complete. Current SD Param: {self._current_sd_param_id}"
        )

    # --- ▲▲▲ 追加ここまで ▲▲▲ ---

    def build_role_assignment_ui(self):
        """役割割り当てUIを動的に構築します。現在のシーンに紐づく *単一のカット* の配役を使用します。"""
        print(
            f"[DEBUG] PromptPanel.build_role_assignment_ui called for scene ID: {self._current_scene_id}"
        )
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

        if current_scene:
            cut_id = getattr(current_scene, "cut_id", None)
            if cut_id:
                selected_cut = self._db_data_ref.get("cuts", {}).get(cut_id)
                if selected_cut and isinstance(selected_cut, Cut):
                    roles_to_display = getattr(selected_cut, "roles", [])
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

        layout.addStretch()
        print("[DEBUG] PromptPanel.build_role_assignment_ui complete.")
        if current_assignments_updated:
            self.assignmentChanged.emit(self._current_assignments.copy())

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
            self.build_role_assignment_ui()

    @Slot(int)
    def _on_style_changed(self, index: int):
        """Style コンボボックスの選択が変更されたときの処理。"""
        new_style_id = self.style_combo.itemData(index)
        if new_style_id != self._current_style_id:
            print(f"[DEBUG] PromptPanel: Style changed to {new_style_id}")
            self._current_style_id = new_style_id if new_style_id else None
            self.styleChanged.emit(new_style_id or "")

    # --- ▼▼▼ _on_sd_params_changed を追加 ▼▼▼ ---
    @Slot(int)
    def _on_sd_params_changed(self, index: int):
        """SD Params コンボボックスの選択が変更されたときの処理。"""
        new_sd_param_id = self.sd_params_combo.itemData(index)
        if new_sd_param_id != self._current_sd_param_id:
            print(f"[DEBUG] PromptPanel: SD Params changed to {new_sd_param_id}")
            self._current_sd_param_id = new_sd_param_id if new_sd_param_id else None
            self.sdParamsChanged.emit(new_sd_param_id or "")

    # --- ▲▲▲ 追加ここまで ▲▲▲ ---

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
