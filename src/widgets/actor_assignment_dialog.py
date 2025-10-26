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
from PySide6.QtCore import Slot
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
        self.form_layout = QFormLayout(content_widget)  # フォームレイアウトを使用

        # --- 必要な Role ID を収集 ---
        required_role_ids: Set[str] = set()
        scenes_data = self.db_data.get("scenes", {})
        cuts_data = self.db_data.get("cuts", {})
        unique_roles_info: Dict[
            str, List[str]
        ] = {}  # role_id: [example_name_in_scene, ...]

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
                required_role_ids.add(role.id)
                if role.id not in unique_roles_info:
                    unique_roles_info[role.id] = []
                # 例としていくつかの名前を保持 (表示用)
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
        actor_names = ["-- Select Actor --"] + [
            getattr(a, "name", "Unnamed") for a in sorted_actors
        ]
        actor_ids = [""] + [getattr(a, "id", None) for a in sorted_actors]

        # --- UI構築 ---
        if not required_role_ids:
            self.form_layout.addRow(QLabel("No roles found in enabled scenes."))
        else:
            sorted_role_ids = sorted(list(required_role_ids))
            for role_id in sorted_role_ids:
                combo = QComboBox()
                combo.addItems(actor_names)

                # 初期値設定
                current_actor_id = self.assignments.get(role_id, "")
                current_index = 0
                if current_actor_id in actor_ids:
                    try:
                        current_index = actor_ids.index(current_actor_id)
                    except ValueError:
                        pass  # 見つからなければ 0 (-- Select Actor --)
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
        all_assigned = True
        for role_id, combo in self.role_combos.items():
            selected_actor_id = (
                combo.currentData()
            )  # itemData に ID を設定しておく必要あり (要修正)
            # ToDo: _init_ui で combo.addItem(name, id) のように itemData を設定する
            if selected_actor_id:
                self.assignments[role_id] = selected_actor_id
            elif role_id in self.assignments:
                del self.assignments[role_id]  # 未選択なら削除
                all_assigned = False  # 必須ではないかもしれないがフラグだけ立てる

        # if not all_assigned:
        #     # 必要なら警告を出す
        #     pass

        self.accept()

    def get_assignments(self) -> Dict[str, str]:
        return self.assignments
