# src/widgets/scene_editor_dialog.py (旧 add_scene_form.py)
import time
import json
from PySide6.QtWidgets import (
    # QDialog は BaseEditorDialog が継承
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QPushButton,
    QDialogButtonBox,
    QWidget,
    QScrollArea,
    QMessageBox,
    QFormLayout,
)
from PySide6.QtCore import Slot
from typing import Optional, Dict, List, Any

from .base_editor_dialog import BaseEditorDialog  # 基底クラスをインポート
from ..models import Scene, FullDatabase, SceneRole, RoleDirection


class SceneEditorDialog(BaseEditorDialog):
    def __init__(
        self, initial_data: Optional[Scene], db_dict: Dict[str, Dict], parent=None
    ):
        # --- ▼▼▼ ここを super() の前に移動 ▼▼▼ ---
        # 内部状態 (Role/Direction編集用) - super().__init__ より先に初期化
        self.current_roles: List[SceneRole] = []
        self.current_role_directions: List[RoleDirection] = []
        # initial_data は super() より前で参照可能
        if initial_data:
            # Deep copy
            self.current_roles = [
                SceneRole(**r.__dict__) for r in getattr(initial_data, "roles", [])
            ]
            self.current_role_directions = [
                RoleDirection(**rd.__dict__)
                for rd in getattr(initial_data, "role_directions", [])
            ]
        else:
            # 新規の場合のデフォルト Role/Direction
            new_role_id = "r1"
            self.current_roles = [SceneRole(id=new_role_id, name_in_scene="主人公")]
            self.current_role_directions = [
                RoleDirection(role_id=new_role_id, direction_ids=[])
            ]
        # --- ▲▲▲ 移動ここまで ▲▲▲ ---

        # 基底クラスの __init__ を呼び出す (これにより _populate_fields が呼ばれる)
        super().__init__(initial_data, db_dict, "シーン (Scene)", parent)

        # UI構築 (_populate_fields は基底クラスの __init__ から呼ばれるのでここでは不要)

    def _populate_fields(self):
        """UI要素を作成し、配置します。"""
        # 基底クラスの form_widget に QVBoxLayout を設定
        editor_layout = QVBoxLayout(self.form_widget)

        # --- UI要素の作成 ---
        self.name_edit = QLineEdit()
        self.tags_edit = QLineEdit()
        self.prompt_template_edit = QTextEdit()
        self.negative_template_edit = QTextEdit()
        self.ref_image_edit = QLineEdit()
        self.image_mode_combo = QComboBox()
        self.image_mode_combo.addItems(["txt2img", "img2img", "img2img_polish"])

        # --- 参照ウィジェットを作成 ---
        background_ref_widget = self._create_reference_editor_widget(
            field_name="background_id",
            current_id=getattr(self.initial_data, "background_id", None),
            reference_db_key="backgrounds",
            reference_modal_type="BACKGROUND",
            allow_none=True,
            none_text="(なし)",
        )
        lighting_ref_widget = self._create_reference_editor_widget(
            field_name="lighting_id",
            current_id=getattr(self.initial_data, "lighting_id", None),
            reference_db_key="lighting",
            reference_modal_type="LIGHTING",
            allow_none=True,
            none_text="(なし)",
        )
        composition_ref_widget = self._create_reference_editor_widget(
            field_name="composition_id",
            current_id=getattr(self.initial_data, "composition_id", None),
            reference_db_key="compositions",
            reference_modal_type="COMPOSITION",
            allow_none=True,
            none_text="(なし)",
        )
        # direction_items は Role/Direction UI で使う
        self.direction_items = list(self.db_dict.get("directions", {}).items())

        # --- レイアウト ---
        basic_group = QWidget()
        basic_layout = QFormLayout(basic_group)
        basic_layout.addRow("名前:", self.name_edit)
        basic_layout.addRow("タグ (カンマ区切り):", self.tags_edit)
        basic_layout.addRow("背景:", background_ref_widget)
        basic_layout.addRow("照明:", lighting_ref_widget)
        basic_layout.addRow("構図:", composition_ref_widget)
        editor_layout.addWidget(basic_group)

        image_mode_group = QWidget()
        image_mode_layout = QFormLayout(image_mode_group)
        image_mode_layout.addRow("参考画像パス:", self.ref_image_edit)
        image_mode_layout.addRow("モード (参考画像):", self.image_mode_combo)
        editor_layout.addWidget(image_mode_group)

        prompt_group = QWidget()
        prompt_layout = QVBoxLayout(prompt_group)
        prompt_layout.addWidget(QLabel("台本 Positive:"))
        prompt_layout.addWidget(self.prompt_template_edit)
        prompt_layout.addWidget(QLabel("台本 Negative:"))
        prompt_layout.addWidget(self.negative_template_edit)
        editor_layout.addWidget(prompt_group)

        self.roles_directions_widget = QWidget()
        self.roles_directions_layout = QVBoxLayout(self.roles_directions_widget)
        editor_layout.addWidget(self.roles_directions_widget)
        self.add_role_button = QPushButton("＋ 配役を追加")
        self.add_role_button.clicked.connect(self.add_role_ui)
        editor_layout.addWidget(self.add_role_button)

        self.form_widget.setLayout(editor_layout)

        # --- _widgets への登録 ---
        self._widgets["name"] = self.name_edit
        self._widgets["tags"] = self.tags_edit
        self._widgets["prompt_template"] = self.prompt_template_edit
        self._widgets["negative_template"] = self.negative_template_edit
        # background_id などは _reference_widgets に自動登録される
        self._widgets["reference_image_path"] = self.ref_image_edit
        self._widgets["image_mode"] = self.image_mode_combo

        # --- 初期データ設定 ---
        if self.initial_data:
            self.name_edit.setText(getattr(self.initial_data, "name", ""))
            self.tags_edit.setText(", ".join(getattr(self.initial_data, "tags", [])))
            self.prompt_template_edit.setPlainText(
                getattr(self.initial_data, "prompt_template", "")
            )
            self.negative_template_edit.setPlainText(
                getattr(self.initial_data, "negative_template", "")
            )
            self.ref_image_edit.setText(
                getattr(self.initial_data, "reference_image_path", "")
            )
            self.image_mode_combo.setCurrentText(
                getattr(self.initial_data, "image_mode", "txt2img")
            )
            # コンボボックスの選択は _create_reference_editor_widget で処理済み
        else:
            # 新規の場合のデフォルト値
            self.prompt_template_edit.setPlainText("masterpiece, best quality, ([R1])")
            self.negative_template_edit.setPlainText("worst quality, low quality")
            self.image_mode_combo.setCurrentText("txt2img")

        # --- Role/Direction UI の初期構築 ---
        self.rebuild_roles_directions_ui()

    def rebuild_roles_directions_ui(self):
        """配役と演出リストのUIを再構築する"""
        # 古いUIをクリア
        while self.roles_directions_layout.count():
            item = self.roles_directions_layout.takeAt(0)
            widget = item.widget()
            layout_item = item.layout()  # レイアウトの場合もある
            if widget:
                widget.deleteLater()
            elif layout_item:
                # レイアウト内のウィジェットを再帰的に削除
                while layout_item.count():
                    inner_item = layout_item.takeAt(0)
                    inner_widget = inner_item.widget()
                    inner_layout = inner_item.layout()
                    if inner_widget:
                        inner_widget.deleteLater()
                    elif inner_layout:
                        # さらにネストされたレイアウトもクリア (通常はここまで深くないはず)
                        while inner_layout.count():
                            deep_item = inner_layout.takeAt(0)
                            deep_widget = deep_item.widget()
                            if deep_widget:
                                deep_widget.deleteLater()
                        inner_layout.deleteLater()
                layout_item.deleteLater()

        self.roles_directions_layout.addWidget(QLabel("配役 (Roles) と 演出リスト:"))
        # self.current_roles と self.current_role_directions を基にUIを生成
        for index, role in enumerate(self.current_roles):
            role_widget = QWidget()
            role_layout = QVBoxLayout(role_widget)
            role_widget.setStyleSheet(
                "border: 1px solid #ddd; padding: 5px; margin-bottom: 5px; border-radius: 4px;"
            )

            # Role編集部分
            role_edit_layout = QHBoxLayout()
            id_edit = QLineEdit(role.id)
            id_edit.setPlaceholderText("ID (例: r1)")
            name_edit = QLineEdit(role.name_in_scene)
            name_edit.setPlaceholderText("表示名 (例: 主人公)")
            remove_role_btn = QPushButton("🗑️")

            id_edit.textChanged.connect(
                lambda text, idx=index: self.handle_role_change(idx, "id", text)
            )
            name_edit.textChanged.connect(
                lambda text, idx=index: self.handle_role_change(
                    idx, "name_in_scene", text
                )
            )
            remove_role_btn.clicked.connect(
                lambda checked=False, idx=index: self.remove_role_ui(idx)
            )
            role_edit_layout.addWidget(id_edit)
            role_edit_layout.addWidget(name_edit)
            role_edit_layout.addWidget(remove_role_btn)
            role_layout.addLayout(role_edit_layout)

            # Directionリスト編集部分
            dir_list_widget = QWidget()
            dir_list_layout = QVBoxLayout(dir_list_widget)
            dir_list_layout.setContentsMargins(10, 5, 0, 0)
            dir_list_layout.addWidget(
                QLabel("演出リスト:", styleSheet="font-size: 0.9em;")
            )

            role_dir_data = next(
                (rd for rd in self.current_role_directions if rd.role_id == role.id),
                None,
            )
            current_dirs = role_dir_data.direction_ids if role_dir_data else []

            if not current_dirs:
                dir_list_layout.addWidget(
                    QLabel(
                        "(演出なし - 基本状態)",
                        styleSheet="font-size: 0.8em; color: #777;",
                    )
                )

            for dir_id in current_dirs:
                dir_item_layout = QHBoxLayout()
                dir_name = "(不明)"
                dir_obj = next(
                    (d[1] for d in self.direction_items if d[0] == dir_id), None
                )
                if dir_obj:
                    dir_name = getattr(dir_obj, "name", "(不明)")

                dir_item_layout.addWidget(
                    QLabel(f"- {dir_name} ({dir_id})", styleSheet="font-size: 0.9em;")
                )
                remove_dir_btn = QPushButton("🗑️")
                remove_dir_btn.clicked.connect(
                    lambda checked=False,
                    r_id=role.id,
                    d_id=dir_id: self.remove_direction_from_role_ui(r_id, d_id)
                )
                dir_item_layout.addWidget(remove_dir_btn)
                dir_list_layout.addLayout(dir_item_layout)

            add_dir_combo = QComboBox()
            add_dir_combo.addItem("＋ 演出を追加...")
            add_dir_combo.addItems(
                [d[1].name for d in self.direction_items if getattr(d[1], "name", None)]
            )
            add_dir_combo.activated.connect(
                lambda index, r_id=role.id: self.add_direction_to_role_ui(r_id, index)
            )
            dir_list_layout.addWidget(add_dir_combo)

            role_layout.addWidget(dir_list_widget)
            self.roles_directions_layout.addWidget(role_widget)

    @Slot()
    def add_role_ui(self):
        next_role_num = len(self.current_roles) + 1
        new_role_id = f"r{next_role_num}"
        while any(r.id == new_role_id for r in self.current_roles):
            next_role_num += 1
            new_role_id = f"r{next_role_num}"

        self.current_roles.append(
            SceneRole(id=new_role_id, name_in_scene=f"配役 {next_role_num}")
        )
        self.current_role_directions.append(
            RoleDirection(role_id=new_role_id, direction_ids=[])
        )
        self.rebuild_roles_directions_ui()

    @Slot(int, str, str)
    def handle_role_change(self, index: int, field: str, value: str):
        if 0 <= index < len(self.current_roles):
            old_role_id = self.current_roles[index].id
            new_value = value.strip()
            setattr(self.current_roles[index], field, new_value)
            if field == "id":
                new_role_id = new_value.lower()
                setattr(self.current_roles[index], "id", new_role_id)
                for rd in self.current_role_directions:
                    if rd.role_id == old_role_id:
                        rd.role_id = new_role_id
                        break
                # ID変更時はUI再構築が必要
                self.rebuild_roles_directions_ui()

    @Slot(int)
    def remove_role_ui(self, index: int):
        if 0 <= index < len(self.current_roles):
            role_id_to_remove = self.current_roles[index].id
            self.current_roles.pop(index)
            self.current_role_directions = [
                rd
                for rd in self.current_role_directions
                if rd.role_id != role_id_to_remove
            ]
            self.rebuild_roles_directions_ui()

    @Slot(str, int)
    def add_direction_to_role_ui(self, role_id: str, combo_index: int):
        if combo_index <= 0:
            return
        dir_index = combo_index - 1
        if 0 <= dir_index < len(self.direction_items):
            direction_id_to_add = self.direction_items[dir_index][0]
            for rd in self.current_role_directions:
                if rd.role_id == role_id:
                    if direction_id_to_add not in rd.direction_ids:
                        rd.direction_ids.append(direction_id_to_add)
                        self.rebuild_roles_directions_ui()
                    break

    @Slot(str, str)
    def remove_direction_from_role_ui(self, role_id: str, direction_id: str):
        for rd in self.current_role_directions:
            if rd.role_id == role_id:
                if direction_id in rd.direction_ids:
                    rd.direction_ids.remove(direction_id)
                    self.rebuild_roles_directions_ui()
                break

    def get_data(self) -> Optional[Scene]:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "名前は必須です。")
            return None

        # Role ID のバリデーション
        role_ids = []
        role_id_valid = True
        placeholder_warning = False
        placeholder_missing = []
        prompt_template = self.prompt_template_edit.toPlainText().strip()
        negative_template = self.negative_template_edit.toPlainText().strip()
        for r in self.current_roles:
            r_id = r.id.strip().lower()
            if not r_id:
                QMessageBox.warning(
                    self, "入力エラー", f"配役 '{r.name_in_scene}' のIDが空です。"
                )
                return None
            if not r_id.startswith("r") or not r_id[1:].isdigit():
                role_id_valid = False
            if r_id in role_ids:
                QMessageBox.warning(
                    self, "入力エラー", f"配役ID '{r_id}' が重複しています。"
                )
                return None
            role_ids.append(r_id)
            r.id = r_id

            placeholder = f"[{r_id.upper()}]"
            if (
                placeholder not in prompt_template
                and placeholder not in negative_template
            ):
                placeholder_warning = True
                placeholder_missing.append(placeholder)

        if not role_id_valid:
            QMessageBox.warning(
                self,
                "入力エラー",
                "無効な配役IDがあります。'r' + 数字の形式に修正してください。",
            )
            return None
        if placeholder_warning:
            print(
                f"警告: プレイスホルダー {', '.join(placeholder_missing)} が台本中に見つかりません。"
            )

        # コンボボックスと他の値は _update_object_from_widgets/_get_widget_value で取得

        if self.initial_data:  # 更新
            updated_scene = self.initial_data
            if not self._update_object_from_widgets(updated_scene):
                return None
            # Role と Direction は直接更新
            updated_scene.roles = self.current_roles
            updated_scene.role_directions = self.current_role_directions
            # image_mode と path も個別に再計算してセット
            ref_image_path = updated_scene.reference_image_path
            updated_scene.image_mode = (
                "txt2img" if not ref_image_path else updated_scene.image_mode
            )
            updated_scene.reference_image_path = (
                ref_image_path if updated_scene.image_mode != "txt2img" else ""
            )
            return updated_scene
        else:  # 新規作成
            tags_text = self.tags_edit.text()
            ref_image_path = self.ref_image_edit.text().strip()
            image_mode = self.image_mode_combo.currentText()
            bg_id = self._get_widget_value("background_id")
            light_id = self._get_widget_value("lighting_id")
            comp_id = self._get_widget_value("composition_id")
            final_image_mode = "txt2img" if not ref_image_path else image_mode

            new_scene = Scene(
                id=f"scene_{int(time.time())}",
                name=name,
                tags=[t.strip() for t in tags_text.split(",") if t.strip()],
                prompt_template=prompt_template,
                negative_template=negative_template,
                background_id=bg_id or "",
                lighting_id=light_id or "",
                composition_id=comp_id or "",
                roles=self.current_roles,
                role_directions=self.current_role_directions,
                reference_image_path=ref_image_path
                if final_image_mode != "txt2img"
                else "",
                image_mode=final_image_mode,
            )
            return new_scene
