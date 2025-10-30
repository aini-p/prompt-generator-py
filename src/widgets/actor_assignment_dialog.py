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
from typing import Dict, List, Optional, Set, Any, Tuple

from ..models import Sequence, Scene, Cut, Actor, SceneRole


class ActorAssignmentDialog(QDialog):
    def __init__(
        self,
        sequence: Sequence,
        initial_assignments: Dict[str, str],
        initial_overrides: Dict[str, Dict[str, Optional[str]]],
        db_data: Dict[str, Dict[str, Any]],
        parent=None,
    ):
        super().__init__(parent)
        self.sequence = sequence
        self.db_data = db_data
        self.assignments = initial_assignments.copy()  # 編集用のコピー
        self.overrides = initial_overrides.copy()
        self.role_override_combos: Dict[str, Dict[str, QComboBox]] = {}
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
        roles_with_empty_costumes: Set[str] = set()
        roles_with_empty_poses: Set[str] = set()
        roles_with_empty_expressions: Set[str] = set()

        for entry in self.sequence.scene_entries:
            if not entry.is_enabled:
                continue
            scene: Optional[Scene] = scenes_data.get(entry.scene_id)
            if not scene:  # ★ scene が None の場合を考慮
                continue

            # --- ▼▼▼ RoleAppearanceAssignment を確認 ▼▼▼ ---
            cut: Optional[Cut] = cuts_data.get(scene.cut_id) if scene.cut_id else None
            if not cut:
                continue

            scene_assignments_map = {ra.role_id: ra for ra in scene.role_assignments}

            for role in cut.roles:
                if not role.id:
                    continue
                required_role_ids.add(role.id)
                if (
                    role.id not in unique_roles_info
                ):  # (unique_roles_info の収集ロジック)
                    unique_roles_info[role.id] = []
                if (
                    role.name_in_scene not in unique_roles_info[role.id]
                    and len(unique_roles_info[role.id]) < 3
                ):
                    unique_roles_info[role.id].append(role.name_in_scene)

                # --- 空スロットのチェック ---
                role_assignment = scene_assignments_map.get(role.id)
                # シーンに設定がない(None)か、あってもリストが空([])の場合
                if not role_assignment or not role_assignment.costume_ids:
                    roles_with_empty_costumes.add(role.id)
                if not role_assignment or not role_assignment.pose_ids:
                    roles_with_empty_poses.add(role.id)
                if not role_assignment or not role_assignment.expression_ids:
                    roles_with_empty_expressions.add(role.id)

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

        def get_appearance_items(
            db_key: str, default_label: str
        ) -> List[Tuple[str, Optional[str]]]:
            data = self.db_data.get(db_key, {})
            sorted_items = sorted(data.values(), key=lambda a: getattr(a, "name", ""))
            # "default" を、アクターのベース設定を使用する識別子として itemData に設定
            items_list = [(f"({default_label})", "default")]
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

        # --- UI構築 ---
        if not required_role_ids:
            self.form_layout.addRow(QLabel("No roles found in enabled scenes."))
        else:
            sorted_role_ids = sorted(list(required_role_ids))
            for role_id in sorted_role_ids:
                # --- アクター割り当て (変更なし) ---
                combo = QComboBox()
                for name, actor_id_data in actor_items:
                    combo.addItem(name, actor_id_data)

                current_actor_id = self.assignments.get(role_id)
                current_index = (
                    combo.findData(current_actor_id) if current_actor_id else 0
                )
                if current_index == -1:
                    current_index = 0
                combo.setCurrentIndex(current_index)

                self.role_combos[role_id] = combo
                role_label = f"Role ID: {role_id}"
                example_names = unique_roles_info.get(role_id, [])
                if example_names:
                    role_label += f" (e.g., {', '.join(example_names)})"

                self.form_layout.addRow(role_label, combo)

                # --- ▼▼▼ Appearance オーバーライド UI を追加 ▼▼▼ ---
                self.role_override_combos[role_id] = {}

                def add_override_combo(
                    role_id: str,
                    key: str,  # "costume_id", "pose_id", ...
                    label: str,
                    items_list: List[Tuple[str, Optional[str]]],
                ):
                    combo = QComboBox()
                    for name, item_id_data in items_list:
                        combo.addItem(name, item_id_data)

                    # 初期値設定
                    # 保存されているオーバーライド値、なければ "default"
                    current_override_id = self.overrides.get(role_id, {}).get(
                        key, "default"
                    )
                    found_index = combo.findData(current_override_id)
                    combo.setCurrentIndex(
                        found_index if found_index != -1 else 0
                    )  # "default" が見つかるはず

                    self.form_layout.addRow(
                        f"  └ {label}:", combo
                    )  # QFormLayout に追加
                    self.role_override_combos[role_id][key] = combo

                # シーン側でリストが空だった項目についてのみ、コンボボックスを追加
                if role_id in roles_with_empty_costumes:
                    add_override_combo(role_id, "costume_id", "Costume", costume_items)
                if role_id in roles_with_empty_poses:
                    add_override_combo(role_id, "pose_id", "Pose", pose_items)
                if role_id in roles_with_empty_expressions:
                    add_override_combo(
                        role_id, "expression_id", "Expression", expression_items
                    )

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
        # アクター割り当てを取得 (変更なし)
        for role_id, combo in self.role_combos.items():
            selected_actor_id = combo.currentData()
            if selected_actor_id:
                self.assignments[role_id] = selected_actor_id
            elif role_id in self.assignments:
                del self.assignments[role_id]

        # --- ▼▼▼ オーバーライド設定を取得 ▼▼▼ ---
        self.overrides.clear()  # 一旦クリア
        for role_id, override_combos in self.role_override_combos.items():
            overrides_for_role: Dict[str, Optional[str]] = {}
            for key, combo in override_combos.items():
                selected_override_id = (
                    combo.currentData()
                )  # "default" または "costume_abc"

                # "default" 以外 (＝具体的なIDが選択された) 場合のみ保存
                if selected_override_id and selected_override_id != "default":
                    overrides_for_role[key] = selected_override_id

            if overrides_for_role:  # 何か具体的な設定があれば
                self.overrides[role_id] = overrides_for_role
        # --- ▲▲▲ 追加 ▲▲▲ ---

        self.accept()

    def get_assignments(self) -> Dict[str, str]:
        return self.assignments

    def get_appearance_overrides(self) -> Dict[str, Dict[str, Optional[str]]]:
        return self.overrides
