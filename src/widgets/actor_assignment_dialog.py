# src/widgets/actor_assignment_dialog.py
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QLabel,
    QDialogButtonBox,
    QMessageBox,
    QScrollArea,
    QWidget,
)
from PySide6.QtCore import Slot, Qt  # ★ Qt をインポート
from typing import Dict, List, Optional, Set, Any

from ..models import Sequence, Scene, Cut, Actor, SceneRole


class ActorAssignmentDialog(QDialog):
    def __init__(
        self,
        sequence: Sequence,
        initial_assignments: Dict[str, str],
        db_data: Dict[str, Dict[str, Any]],
        parent=None,
    ):
        super().__init__(parent)
        self.sequence = sequence
        self.db_data = db_data
        self.assignments = initial_assignments.copy()  # 編集用のコピー
        self.role_combos: Dict[str, QComboBox] = {}

        self.setWindowTitle(f"Assign Actors for Sequence: {sequence.name}")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Assign actors to roles required in this sequence:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        self.form_layout = QFormLayout(content_widget)

        # --- 必要な Role ID を収集 ---
        required_role_ids: Set[str] = set()
        scenes_data = self.db_data.get("scenes", {})
        cuts_data = self.db_data.get("cuts", {})
        unique_roles_info: Dict[str, List[str]] = {}

        for entry in self.sequence.scene_entries:
            if not entry.is_enabled:
                continue
            scene: Optional[Scene] = scenes_data.get(entry.scene_id)
            if not scene or not scene.cut_id:
                continue
            cut: Optional[Cut] = cuts_data.get(scene.cut_id)
            if not cut:
                continue
            for role in cut.roles:
                if not role.id:
                    continue  # IDがないRoleは無視
                required_role_ids.add(role.id)
                if role.id not in unique_roles_info:
                    unique_roles_info[role.id] = []
                if (
                    role.name_in_scene not in unique_roles_info[role.id]
                    and len(unique_roles_info[role.id]) < 3
                ):
                    unique_roles_info[role.id].append(role.name_in_scene)

        # --- アクターリスト準備 ---
        actors_data = self.db_data.get("actors", {})
        sorted_actors = sorted(
            actors_data.values(), key=lambda a: getattr(a, "name", "")
        )
        # ★★★ QComboBox 用のリスト (ID を itemData に設定するため変更) ★★★
        # actor_names = ["-- Select Actor --"] + [getattr(a, "name", "Unnamed") for a in sorted_actors]
        # actor_ids = [""] + [getattr(a, "id", None) for a in sorted_actors]
        actor_items: List[Tuple[str, Optional[str]]] = [
            ("-- Select Actor --", None)
        ]  # (表示名, ID) のタプルリスト
        actor_ids_for_check = [None]  # 初期値チェック用
        for actor in sorted_actors:
            actor_id = getattr(actor, "id", None)
            actor_name = getattr(actor, "name", "Unnamed")
            if actor_id:
                actor_items.append((f"{actor_name} ({actor_id})", actor_id))
                actor_ids_for_check.append(actor_id)
        # ★★★ 変更ここまで ★★★

        # --- UI構築 ---
        if not required_role_ids:
            self.form_layout.addRow(QLabel("No roles found in enabled scenes."))
        else:
            sorted_role_ids = sorted(list(required_role_ids))
            for role_id in sorted_role_ids:
                combo = QComboBox()
                # ▼▼▼ QComboBox へのアイテム追加方法を変更 ▼▼▼
                # combo.addItems(actor_names) # <- これをやめる
                for name, actor_id_data in actor_items:
                    combo.addItem(
                        name, actor_id_data
                    )  # 第2引数に itemData (アクターID) を設定
                # ▲▲▲ 変更ここまで ▲▲▲

                # 初期値設定
                current_actor_id = self.assignments.get(role_id)  # get() で None も取得
                current_index = 0  # デフォルトは "-- Select Actor --"
                if current_actor_id in actor_ids_for_check:
                    try:
                        # itemData を使ってインデックスを検索
                        # findData は一致する最初のインデックスを返す
                        found_index = combo.findData(current_actor_id)
                        if found_index != -1:
                            current_index = found_index
                    except ValueError:  # 通常 findData では発生しない
                        pass
                combo.setCurrentIndex(current_index)

                self.role_combos[role_id] = combo
                role_label = f"Role ID: {role_id}"
                example_names = unique_roles_info.get(role_id, [])
                if example_names:
                    role_label += f" (e.g., {', '.join(example_names)})"

                self.form_layout.addRow(role_label, combo)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._save_assignments)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    @Slot()
    def _save_assignments(self):
        # コンボボックスから値を取得して self.assignments を更新
        # all_assigned = True # 必須割り当てチェックは一旦削除
        for role_id, combo in self.role_combos.items():
            # ▼▼▼ currentData() で itemData (アクターID) を取得 ▼▼▼
            selected_actor_id = (
                combo.currentData()
            )  # Correctly gets the actor_id (or None)
            # ▲▲▲ 変更ここまで ▲▲▲
            if selected_actor_id:
                self.assignments[role_id] = selected_actor_id
            elif role_id in self.assignments:
                del self.assignments[role_id]  # 未選択なら割り当てを削除
                # all_assigned = False

        self.accept()

    def get_assignments(self) -> Dict[str, str]:
        return self.assignments
