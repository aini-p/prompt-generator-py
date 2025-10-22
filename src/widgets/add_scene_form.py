# src/widgets/add_scene_form.py
import time
import json  # For JSON validation if needed
from PySide6.QtWidgets import (
    QDialog,
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
)
from PySide6.QtCore import Slot
from typing import Optional, Dict, List, Any

# srcフォルダを基準にインポート
from ..models import Scene, FullDatabase, SceneRole, RoleDirection


class AddSceneForm(QDialog):
    def __init__(
        self, initial_data: Optional[Scene], db_dict: Dict[str, Dict], parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle(
            "シーン (Scene) の編集" if initial_data else "新規 シーン (Scene) の追加"
        )
        self.db_dict = db_dict
        self.initial_data = initial_data
        self.saved_data: Optional[Scene] = None

        # --- フォームの内部状態 (編集中) ---
        self.current_roles: List[SceneRole] = []
        self.current_role_directions: List[RoleDirection] = []

        # --- UI要素の作成 ---
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

        self.background_combo.addItems(
            [b.name for _, b in self.background_items]
            if self.background_items
            else ["(なし)"]
        )
        self.lighting_combo.addItems(
            [l.name for _, l in self.lighting_items]
            if self.lighting_items
            else ["(なし)"]
        )
        self.composition_combo.addItems(
            [c.name for _, c in self.composition_items]
            if self.composition_items
            else ["(なし)"]
        )
        self.image_mode_combo.addItems(["txt2img", "img2img", "img2img_polish"])

        # --- レイアウト ---
        main_layout = QVBoxLayout(self)

        # --- 基本情報セクション ---
        basic_group = QWidget()
        basic_layout = QVBoxLayout(basic_group)
        basic_layout.addWidget(QLabel("名前:"))
        basic_layout.addWidget(self.name_edit)
        basic_layout.addWidget(QLabel("タグ (カンマ区切り):"))
        basic_layout.addWidget(self.tags_edit)
        combo_layout = QHBoxLayout()
        combo_layout.addWidget(self.background_combo)
        combo_layout.addWidget(self.lighting_combo)
        combo_layout.addWidget(self.composition_combo)
        basic_layout.addLayout(combo_layout)
        main_layout.addWidget(basic_group)

        # --- 画像モードセクション ---
        image_mode_group = QWidget()
        image_mode_layout = QVBoxLayout(image_mode_group)
        image_mode_layout.addWidget(QLabel("参考画像パス (URL or Local Path):"))
        image_mode_layout.addWidget(self.ref_image_edit)
        image_mode_layout.addWidget(QLabel("モード (参考画像がある場合):"))
        image_mode_layout.addWidget(self.image_mode_combo)
        main_layout.addWidget(image_mode_group)

        # --- 台本セクション ---
        prompt_group = QWidget()
        prompt_layout = QVBoxLayout(prompt_group)
        prompt_layout.addWidget(
            QLabel("台本 Positive (プレイスホルダー [R1] などを使用):")
        )
        prompt_layout.addWidget(self.prompt_template_edit)
        prompt_layout.addWidget(
            QLabel("台本 Negative (プレイスホルダー [R1] などを使用):")
        )
        prompt_layout.addWidget(self.negative_template_edit)
        main_layout.addWidget(prompt_group)

        # --- 配役 & 演出リストセクション (動的) ---
        self.roles_directions_widget = QWidget()
        self.roles_directions_layout = QVBoxLayout(self.roles_directions_widget)
        main_layout.addWidget(self.roles_directions_widget)
        self.add_role_button = QPushButton("＋ 配役を追加")
        self.add_role_button.clicked.connect(self.add_role_ui)
        main_layout.addWidget(self.add_role_button)

        # --- 保存/キャンセルボタン ---
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        # 初期データを設定 (レイアウト作成後)
        self.set_initial_data(initial_data)
        # 最初のUIを構築
        self.rebuild_roles_directions_ui()

    def set_initial_data(self, initial_data: Optional[Scene]):
        """フォームに初期データを設定する"""
        if initial_data:
            self.name_edit.setText(initial_data.name)
            self.tags_edit.setText(", ".join(initial_data.tags))
            self.prompt_template_edit.setPlainText(initial_data.prompt_template)
            self.negative_template_edit.setPlainText(initial_data.negative_template)
            self.ref_image_edit.setText(initial_data.reference_image_path)
            self.image_mode_combo.setCurrentText(initial_data.image_mode)
            # コンボボックスの選択
            try:
                self.background_combo.setCurrentIndex(
                    [bid for bid, _ in self.background_items].index(
                        initial_data.background_id
                    )
                )
            except (ValueError, IndexError):
                pass
            try:
                self.lighting_combo.setCurrentIndex(
                    [lid for lid, _ in self.lighting_items].index(
                        initial_data.lighting_id
                    )
                )
            except (ValueError, IndexError):
                pass
            try:
                self.composition_combo.setCurrentIndex(
                    [cid for cid, _ in self.composition_items].index(
                        initial_data.composition_id
                    )
                )
            except (ValueError, IndexError):
                pass
            # Role と Direction を内部状態にコピー
            self.current_roles = [
                SceneRole(**r.__dict__) for r in initial_data.roles
            ]  # Deep copy
            self.current_role_directions = [
                RoleDirection(**rd.__dict__) for rd in initial_data.role_directions
            ]  # Deep copy
        else:
            # 新規
            self.name_edit.setText("")
            self.tags_edit.setText("")
            self.prompt_template_edit.setPlainText("masterpiece, best quality, ([R1])")
            self.negative_template_edit.setPlainText("worst quality, low quality")
            self.ref_image_edit.setText("")
            self.image_mode_combo.setCurrentText("txt2img")
            if self.background_items:
                self.background_combo.setCurrentIndex(0)
            if self.lighting_items:
                self.lighting_combo.setCurrentIndex(0)
            if self.composition_items:
                self.composition_combo.setCurrentIndex(0)
            # デフォルトの Role と Direction
            new_role_id = "r1"
            self.current_roles = [SceneRole(id=new_role_id, name_in_scene="主人公")]
            self.current_role_directions = [
                RoleDirection(role_id=new_role_id, direction_ids=[])
            ]

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
                dir_name = (
                    self.db_dict.get("directions", {})
                    .get(dir_id, {"name": "不明"})
                    .name
                )
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
            add_dir_combo.addItems([d.name for _, d in self.direction_items])
            # lambdaで現在のrole.idをキャプチャ
            add_dir_combo.activated.connect(
                lambda index, r_id=role.id: self.add_direction_to_role_ui(r_id, index)
            )
            dir_list_layout.addWidget(add_dir_combo)

            role_layout.addWidget(dir_list_widget)
            self.roles_directions_layout.addWidget(role_widget)

    # --- UI操作 -> 内部状態変更ハンドラ ---
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
            setattr(self.current_roles[index], field, value)
            # IDが変わったら RoleDirections も更新
            if field == "id":
                new_role_id = value.lower()  # IDは小文字に統一
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
            return  # "-- 演出を追加 --" を選択した場合
        dir_index = combo_index - 1  # "-- 演出を追加 --" の分を引く
        if 0 <= dir_index < len(self.direction_items):
            direction_id_to_add = self.direction_items[dir_index][0]  # IDを取得
            for rd in self.current_role_directions:
                if rd.role_id == role_id:
                    if direction_id_to_add not in rd.direction_ids:
                        rd.direction_ids.append(direction_id_to_add)
                        self.rebuild_roles_directions_ui()  # UI更新
                    break

    def remove_direction_from_role_ui(self, role_id: str, direction_id: str):
        for rd in self.current_role_directions:
            if rd.role_id == role_id:
                rd.direction_ids = [
                    did for did in rd.direction_ids if did != direction_id
                ]
                self.rebuild_roles_directions_ui()  # UI更新
                break

    @Slot()
    def accept(self):
        # フォームの入力値を取得 & 検証
        name = self.name_edit.text().strip()
        prompt_template = self.prompt_template_edit.toPlainText().strip()
        negative_template = self.negative_template_edit.toPlainText().strip()
        ref_image_path = self.ref_image_edit.text().strip()
        image_mode = self.image_mode_combo.currentText()

        if not name:
            QMessageBox.warning(self, "入力エラー", "名前は必須です。")
            return

        # Role IDの重複チェック
        role_ids = [r.id for r in self.current_roles]
        if len(role_ids) != len(set(role_ids)):
            QMessageBox.warning(self, "入力エラー", "配役(Role)のIDが重複しています。")
            return
        if not all(r_id.startswith("r") and r_id[1:].isdigit() for r_id in role_ids):
            QMessageBox.warning(
                self,
                "入力エラー",
                "配役(Role)のIDは 'r' + 数字 (例: r1, r2) の形式にしてください。",
            )
            return

        # プレイスホルダーチェック (簡易)
        for r_id in role_ids:
            placeholder = f"[{r_id.upper()}]"
            if (
                placeholder not in prompt_template
                and placeholder not in negative_template
            ):
                print(
                    f"警告: プレイスホルダー {placeholder} が台本中に見つかりません。"
                )
                # QMessageBox.warning(self, "確認", f"プレイスホルダー {placeholder} が台本中に見つかりません。")

        # コンボボックスからIDを取得
        bg_id = (
            self.background_items[self.background_combo.currentIndex()][0]
            if self.background_items and self.background_combo.currentIndex() >= 0
            else ""
        )
        light_id = (
            self.lighting_items[self.lighting_combo.currentIndex()][0]
            if self.lighting_items and self.lighting_combo.currentIndex() >= 0
            else ""
        )
        comp_id = (
            self.composition_items[self.composition_combo.currentIndex()][0]
            if self.composition_items and self.composition_combo.currentIndex() >= 0
            else ""
        )

        # モードを決定 (ref_imageが空なら強制的にtxt2img)
        final_image_mode = "txt2img" if not ref_image_path else image_mode

        self.saved_data = Scene(
            id=self.initial_data.id
            if self.initial_data
            else f"scene_{int(time.time())}",
            name=name,
            tags=[t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
            prompt_template=prompt_template,
            negative_template=negative_template,
            background_id=bg_id,
            lighting_id=light_id,
            composition_id=comp_id,
            roles=self.current_roles,  # 保存時の内部状態
            role_directions=self.current_role_directions,  # 保存時の内部状態
            reference_image_path=ref_image_path
            if final_image_mode != "txt2img"
            else "",  # txt2imgならパスは空
            image_mode=final_image_mode,
        )
        super().accept()

    def get_data(self) -> Optional[Scene]:
        return self.saved_data


# --- スタイル定義 (ダイアログ内で閉じる) ---
modalOverlayStyle: Dict[str, Any] = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "right": 0,
    "bottom": 0,
    "backgroundColor": "rgba(0, 0, 0, 0.5)",
    "display": "flex",
    "alignItems": "center",
    "justifyContent": "center",
    "zIndex": 1000,
}
modalContentStyle: Dict[str, Any] = {
    "border": "1px solid #ccc",
    "padding": "20px",
    "backgroundColor": "white",
    "borderRadius": "8px",
    "width": "600px",
    "maxHeight": "90vh",
    "overflowY": "auto",
}
formGroupStyle: Dict[str, Any] = {
    "marginBottom": "10px",
    "display": "flex",
    "flexDirection": "column",
}
inputStyle: Dict[str, Any] = {
    "width": "95%",
    "padding": "8px",
    "marginTop": "4px",
    "fontSize": "14px",
}
sectionStyle: Dict[str, Any] = {
    "marginBottom": "10px",
    "paddingBottom": "10px",
    "borderBottom": "1px solid #eee",
}
tinyButtonStyle: Dict[str, Any] = {
    "fontSize": "10px",
    "padding": "2px 4px",
    "margin": "0 2px",
}
directionItemStyle: Dict[str, Any] = {
    "display": "flex",
    "justifyContent": "space-between",
    "padding": "2px 4px",
    "fontSize": "0.9em",
    "backgroundColor": "#f9f9f9",
    "margin": "2px 0",
    "borderRadius": "3px",
}
