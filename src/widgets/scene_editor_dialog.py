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
    QFormLayout,  # QFormLayout を追加
)
from PySide6.QtCore import Slot
from typing import Optional, Dict, List, Any

from .base_editor_dialog import BaseEditorDialog  # 基底クラスをインポート
from ..models import Scene, FullDatabase, SceneRole, RoleDirection


# --- ▼▼▼ クラス定義を変更 ▼▼▼ ---
class SceneEditorDialog(BaseEditorDialog):
    # --- ▲▲▲ 変更ここまで ▲▲▲ ---
    def __init__(
        self, initial_data: Optional[Scene], db_dict: Dict[str, Dict], parent=None
    ):
        # --- ▼▼▼ super().__init__ の呼び出しを変更 ▼▼▼ ---
        super().__init__(initial_data, db_dict, "シーン (Scene)", parent)
        # --- ▲▲▲ 変更ここまで ▲▲▲ ---

        # self.db_dict と self.initial_data は基底クラスで設定される
        # self.saved_data も基底クラスにある

        # --- フォームの内部状態 (編集中) ---
        self.current_roles: List[SceneRole] = []
        self.current_role_directions: List[RoleDirection] = []
        if self.initial_data:
            # Deep copy
            self.current_roles = [
                SceneRole(**r.__dict__) for r in getattr(self.initial_data, "roles", [])
            ]
            self.current_role_directions = [
                RoleDirection(**rd.__dict__)
                for rd in getattr(self.initial_data, "role_directions", [])
            ]
        else:
            # 新規の場合のデフォルト Role/Direction
            new_role_id = "r1"
            self.current_roles = [SceneRole(id=new_role_id, name_in_scene="主人公")]
            self.current_role_directions = [
                RoleDirection(role_id=new_role_id, direction_ids=[])
            ]

        # --- UI構築は _populate_fields で行う ---
        # 基底クラスの __init__ から _populate_fields が呼ばれる

    def _populate_fields(self):
        """UI要素を作成し、配置します。"""
        # 基底クラスの form_layout を使うか、独自のレイアウトを使うか選択
        # Scene は複雑なので QVBoxLayout を使う
        editor_layout = QVBoxLayout(self.form_widget)  # 基底の form_widget に設定

        # --- UI要素の作成 (元の __init__ から移動) ---
        self.name_edit = QLineEdit()
        self.tags_edit = QLineEdit()
        self.prompt_template_edit = QTextEdit()
        self.negative_template_edit = QTextEdit()
        self.background_combo = QComboBox()
        self.lighting_combo = QComboBox()
        self.composition_combo = QComboBox()
        self.ref_image_edit = QLineEdit()
        self.image_mode_combo = QComboBox()

        # コンボボックスに選択肢を追加
        self.background_items = list(self.db_dict.get("backgrounds", {}).items())
        self.lighting_items = list(self.db_dict.get("lighting", {}).items())
        self.composition_items = list(self.db_dict.get("compositions", {}).items())
        self.direction_items = list(
            self.db_dict.get("directions", {}).items()
        )  # For timeline

        # --- ▼▼▼ _create_combo_box ヘルパーを使用 ▼▼▼ ---
        self.background_combo = self._create_combo_box(
            getattr(self.initial_data, "background_id", None),
            self.db_dict.get("backgrounds", {}),
            allow_none=True,
            none_text="(なし)",
        )
        self.lighting_combo = self._create_combo_box(
            getattr(self.initial_data, "lighting_id", None),
            self.db_dict.get("lighting", {}),
            allow_none=True,
            none_text="(なし)",
        )
        self.composition_combo = self._create_combo_box(
            getattr(self.initial_data, "composition_id", None),
            self.db_dict.get("compositions", {}),
            allow_none=True,
            none_text="(なし)",
        )
        # --- ▲▲▲ 変更ここまで ▲▲▲ ---

        self.image_mode_combo.addItems(["txt2img", "img2img", "img2img_polish"])

        # --- レイアウト (元の __init__ から移動) ---
        basic_group = QWidget()
        basic_layout = QFormLayout(basic_group)  # QFormLayout に変更
        basic_layout.addRow("名前:", self.name_edit)
        basic_layout.addRow("タグ (カンマ区切り):", self.tags_edit)
        basic_layout.addRow("背景:", self.background_combo)
        basic_layout.addRow("照明:", self.lighting_combo)
        basic_layout.addRow("構図:", self.composition_combo)
        editor_layout.addWidget(basic_group)

        image_mode_group = QWidget()
        image_mode_layout = QFormLayout(image_mode_group)
        image_mode_layout.addRow("参考画像パス:", self.ref_image_edit)
        image_mode_layout.addRow("モード (参考画像):", self.image_mode_combo)
        editor_layout.addWidget(image_mode_group)

        prompt_group = QWidget()
        prompt_layout = QVBoxLayout(prompt_group)  # ここは QVBoxLayout のまま
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

        # --- _widgets への登録 ---
        self._widgets["name"] = self.name_edit
        self._widgets["tags"] = self.tags_edit
        self._widgets["prompt_template"] = self.prompt_template_edit
        self._widgets["negative_template"] = self.negative_template_edit
        self._widgets["background_id"] = self.background_combo
        self._widgets["lighting_id"] = self.lighting_combo
        self._widgets["composition_id"] = self.composition_combo
        self._widgets["reference_image_path"] = self.ref_image_edit
        self._widgets["image_mode"] = self.image_mode_combo
        # roles と role_directions は別管理

        # --- 初期データ設定 (元の set_initial_data から移動・簡略化) ---
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
            # コンボボックスの選択は _create_combo_box で処理済み
            # Role/Direction の内部状態は __init__ でコピー済み
        else:
            # 新規の場合のデフォルト値
            self.prompt_template_edit.setPlainText("masterpiece, best quality, ([R1])")
            self.negative_template_edit.setPlainText("worst quality, low quality")
            self.image_mode_combo.setCurrentText("txt2img")
            # コンボボックスの初期選択は _create_combo_box で (None) が選択されるはず

        # --- Role/Direction UI の初期構築 ---
        self.rebuild_roles_directions_ui()

        # --- 不要なコード削除 ---
        # button_box の作成と接続は基底クラスで行うので削除
        # set_initial_data メソッド自体も不要なので削除

    # --- rebuild_roles_directions_ui, add_role_ui, handle_role_change, remove_role_ui,
    # --- add_direction_to_role_ui, remove_direction_from_role_ui は変更なし ---
    # (省略)
    def rebuild_roles_directions_ui(self):
        """配役と演出リストのUIを再構築する"""
        # 古いUIをクリア
        while self.roles_directions_layout.count():
            item = self.roles_directions_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

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
            # lambdaで現在のindexをキャプチャ
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
            dir_list_layout.setContentsMargins(10, 5, 0, 0)  # インデント
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
                dir_name = "(不明)"  # デフォルト名
                # direction_items は [(id, obj), ...] のリスト
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
            # direction_items は [(id, obj), ...] のリストなので、名前だけ抽出
            add_dir_combo.addItems(
                [d[1].name for d in self.direction_items if getattr(d[1], "name", None)]
            )
            # lambdaで現在のrole.idをキャプチャ
            add_dir_combo.activated.connect(
                lambda index, r_id=role.id: self.add_direction_to_role_ui(r_id, index)
            )
            dir_list_layout.addWidget(add_dir_combo)

            role_layout.addWidget(dir_list_widget)
            self.roles_directions_layout.addWidget(role_widget)

    def add_role_ui(self):
        next_role_num = len(self.current_roles) + 1
        new_role_id = f"r{next_role_num}"
        # IDが重複しないように確認 (簡易)
        while any(r.id == new_role_id for r in self.current_roles):
            next_role_num += 1
            new_role_id = f"r{next_role_num}"

        self.current_roles.append(
            SceneRole(id=new_role_id, name_in_scene=f"配役 {next_role_num}")
        )
        self.current_role_directions.append(
            RoleDirection(role_id=new_role_id, direction_ids=[])
        )
        self.rebuild_roles_directions_ui()  # UI更新

    def handle_role_change(self, index: int, field: str, value: str):
        if 0 <= index < len(self.current_roles):
            old_role_id = self.current_roles[index].id
            new_value = value.strip()
            setattr(self.current_roles[index], field, new_value)
            # IDが変わったら RoleDirections も更新
            if field == "id":
                new_role_id = new_value.lower()  # IDは小文字に統一推奨
                setattr(self.current_roles[index], "id", new_role_id)  # state更新
                for rd in self.current_role_directions:
                    if rd.role_id == old_role_id:
                        rd.role_id = new_role_id
                        break  # IDはユニークなはず
                self.rebuild_roles_directions_ui()  # ID表示が変わるのでUI更新

    def remove_role_ui(self, index: int):
        if 0 <= index < len(self.current_roles):
            role_id_to_remove = self.current_roles[index].id
            self.current_roles.pop(index)
            self.current_role_directions = [
                rd
                for rd in self.current_role_directions
                if rd.role_id != role_id_to_remove
            ]
            self.rebuild_roles_directions_ui()  # UI更新

    def add_direction_to_role_ui(self, role_id: str, combo_index: int):
        if combo_index <= 0:
            return  # "＋ 演出を追加..."
        dir_index = combo_index - 1
        if 0 <= dir_index < len(self.direction_items):
            direction_id_to_add = self.direction_items[dir_index][0]
            for rd in self.current_role_directions:
                if rd.role_id == role_id:
                    if direction_id_to_add not in rd.direction_ids:
                        rd.direction_ids.append(direction_id_to_add)
                        self.rebuild_roles_directions_ui()
                    break

    def remove_direction_from_role_ui(self, role_id: str, direction_id: str):
        for rd in self.current_role_directions:
            if rd.role_id == role_id:
                if direction_id in rd.direction_ids:
                    rd.direction_ids.remove(direction_id)
                    self.rebuild_roles_directions_ui()
                break

    # --- ▼▼▼ accept を get_data に変更 ▼▼▼ ---
    def get_data(self) -> Optional[Scene]:
        # --- 基本的な値の取得とバリデーション ---
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "名前は必須です。")
            return None  # バリデーションエラー

        prompt_template = self.prompt_template_edit.toPlainText().strip()
        negative_template = self.negative_template_edit.toPlainText().strip()
        ref_image_path = self.ref_image_edit.text().strip()
        image_mode = self.image_mode_combo.currentText()

        # --- Role ID のバリデーション ---
        role_ids = []
        role_id_valid = True
        placeholder_warning = False
        placeholder_missing = []
        for r in self.current_roles:
            r_id = r.id.strip().lower()  # 保存前に空白除去と小文字化
            if not r_id:
                QMessageBox.warning(
                    self, "入力エラー", f"配役 '{r.name_in_scene}' のIDが空です。"
                )
                return None
            if not r_id.startswith("r") or not r_id[1:].isdigit():
                QMessageBox.warning(
                    self,
                    "入力エラー",
                    f"配役ID '{r_id}' は 'r' + 数字 (例: r1) の形式にしてください。",
                )
                role_id_valid = (
                    False  # エラーにはせずフラグを立てる (後で修正可能にするため)
                )
                # return None # ここで中断しても良い
            if r_id in role_ids:
                QMessageBox.warning(
                    self, "入力エラー", f"配役ID '{r_id}' が重複しています。"
                )
                return None
            role_ids.append(r_id)
            r.id = r_id  # 内部データも更新

            # プレイスホルダーチェック
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
            return None  # ID形式エラーは中断

        if placeholder_warning:
            # 警告のみで中断はしない
            print(
                f"警告: プレイスホルダー {', '.join(placeholder_missing)} が台本中に見つかりません。"
            )
        # QMessageBox.warning(self, "確認", f"プレイスホルダー {', '.join(placeholder_missing)} が台本中に見つかりません。")

        # --- コンボボックスからIDを取得 (_widgets 経由) ---
        bg_id = self._widgets["background_id"].currentData() or ""
        light_id = self._widgets["lighting_id"].currentData() or ""
        comp_id = self._widgets["composition_id"].currentData() or ""

        # モードを決定
        final_image_mode = "txt2img" if not ref_image_path else image_mode

        # --- 新規作成か更新かで Scene オブジェクトを作成/更新 ---
        if self.initial_data:  # 更新
            updated_scene = self.initial_data
            # 基底クラスのヘルパーで基本的な属性を更新
            self._update_object_from_widgets(updated_scene)
            # Role と Direction は直接更新
            updated_scene.roles = self.current_roles
            updated_scene.role_directions = self.current_role_directions
            # image_mode と path も個別にセット
            updated_scene.image_mode = final_image_mode
            updated_scene.reference_image_path = (
                ref_image_path if final_image_mode != "txt2img" else ""
            )
            return updated_scene
        else:  # 新規作成
            new_scene = Scene(
                id=f"scene_{int(time.time())}",
                name=name,
                tags=[t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
                prompt_template=prompt_template,
                negative_template=negative_template,
                background_id=bg_id,
                lighting_id=light_id,
                composition_id=comp_id,
                roles=self.current_roles,
                role_directions=self.current_role_directions,
                reference_image_path=ref_image_path
                if final_image_mode != "txt2img"
                else "",
                image_mode=final_image_mode,
            )
            return new_scene

    # --- ▲▲▲ 変更ここまで ▲▲▲ ---

    # --- 元の get_data は不要なので削除 ---
    # def get_data(self) -> Optional[Scene]:
    #     return self.saved_data


# --- スタイル定義は削除 (必要であれば main_window.py などに移動) ---
