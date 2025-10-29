# src/widgets/cut_editor_dialog.py
import time
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QTextEdit,
    QMessageBox,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFormLayout,
    QListWidget,
    QListWidgetItem,
    QComboBox,
)
from PySide6.QtCore import Slot, Qt
from typing import Optional, Dict, List, Any

from .base_editor_dialog import BaseEditorDialog
from ..models import Cut, SceneRole


class CutEditorDialog(BaseEditorDialog):
    def __init__(
        self, initial_data: Optional[Cut], db_dict: Dict[str, Dict], parent=None
    ):
        # 内部状態 (Roles編集用) - super().__init__ より先に初期化
        self.current_roles: List[SceneRole] = []
        # initial_data は super() より前で参照可能
        if initial_data and hasattr(initial_data, "roles"):
            self.current_roles = [SceneRole(**r.__dict__) for r in initial_data.roles]
        # --- ▲▲▲ 移動ここまで ▲▲▲ ---

        # db_dict は使わない想定だがインターフェースを合わせる
        super().__init__(initial_data, db_dict, "カット (Cut)", parent)

    def _populate_fields(self):
        self.form_layout = self.setup_form_layout()
        if not self.form_layout:
            return

        # --- 基本フィールド ---
        self.name_edit = QLineEdit(getattr(self.initial_data, "name", ""))
        self.prompt_template_edit = QTextEdit(
            getattr(self.initial_data, "prompt_template", "")
        )
        self.negative_template_edit = QTextEdit(
            getattr(self.initial_data, "negative_template", "")
        )
        self.ref_image_edit = QLineEdit(
            getattr(self.initial_data, "reference_image_path", "")
        )
        self.image_mode_combo = QComboBox()
        self.image_mode_combo.addItems(["txt2img", "img2img", "img2img_polish"])
        self.image_mode_combo.setCurrentText(
            getattr(self.initial_data, "image_mode", "txt2img")
        )

        self.form_layout.addRow("カット名 (オプション):", self.name_edit)
        self.form_layout.addRow("台本 Positive:", self.prompt_template_edit)
        self.form_layout.addRow("台本 Negative:", self.negative_template_edit)
        self.form_layout.addRow("参考画像パス:", self.ref_image_edit)
        self.form_layout.addRow("モード(参考画像):", self.image_mode_combo)

        # --- Roles 編集 UI ---
        self.form_layout.addRow(QLabel("--- 配役 (Roles) ---"))
        self.roles_widget = QWidget()
        self.roles_layout = QVBoxLayout(self.roles_widget)
        self.rebuild_roles_ui()  # 初期UI構築

        add_role_button = QPushButton("＋ 配役を追加")
        add_role_button.clicked.connect(self.add_role_ui)

        self.form_layout.addRow(self.roles_widget)
        self.form_layout.addRow(add_role_button)

        # _widgets への登録 (roles は除く)
        self._widgets["name"] = self.name_edit
        self._widgets["prompt_template"] = self.prompt_template_edit
        self._widgets["negative_template"] = self.negative_template_edit
        self._widgets["reference_image_path"] = self.ref_image_edit
        self._widgets["image_mode"] = self.image_mode_combo

    def rebuild_roles_ui(self):
        """配役リストのUIを再構築する"""
        while self.roles_layout.count():
            item = self.roles_layout.takeAt(0)
            widget = item.widget()
            layout_item = item.layout()
            if widget:
                widget.deleteLater()
            elif layout_item:
                while layout_item.count():  # QHBoxLayoutの中身を削除
                    inner_item = layout_item.takeAt(0)
                    inner_widget = inner_item.widget()
                    if inner_widget:
                        inner_widget.deleteLater()
                layout_item.deleteLater()

        for index, role in enumerate(self.current_roles):
            row_layout = QHBoxLayout()
            id_edit = QLineEdit(role.id)
            id_edit.setPlaceholderText("ID (例: r1)")
            name_edit = QLineEdit(role.name_in_scene)
            name_edit.setPlaceholderText("表示名 (例: 主人公)")
            remove_btn = QPushButton("🗑️")

            id_edit.textChanged.connect(
                lambda text, idx=index: self.handle_role_change(idx, "id", text)
            )
            name_edit.textChanged.connect(
                lambda text, idx=index: self.handle_role_change(
                    idx, "name_in_scene", text
                )
            )
            remove_btn.clicked.connect(
                lambda checked=False, idx=index: self.remove_role_ui(idx)
            )

            row_layout.addWidget(QLabel(f"{index + 1}:"))
            row_layout.addWidget(id_edit)
            row_layout.addWidget(name_edit)
            row_layout.addWidget(remove_btn)
            self.roles_layout.addLayout(row_layout)

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
        self.rebuild_roles_ui()

    @Slot(int, str, str)
    def handle_role_change(self, index: int, field: str, value: str):
        if 0 <= index < len(self.current_roles):
            new_value = value.strip()
            setattr(self.current_roles[index], field, new_value)
            # ID 変更時は小文字化などの処理を追加しても良い
            if field == "id":
                setattr(self.current_roles[index], "id", new_value.lower())
                # ID変更時はUI再構築が必要になる場合がある (今回は不要)

    @Slot(int)
    def remove_role_ui(self, index: int):
        if 0 <= index < len(self.current_roles):
            self.current_roles.pop(index)
            self.rebuild_roles_ui()

    def get_data(self) -> Optional[Cut]:
        # 基本属性は _update_object_from_widgets で取得
        prompt_template = self.prompt_template_edit.toPlainText().strip()
        # バリデーション (例: Prompt Template は必須)
        if not prompt_template:
            QMessageBox.warning(self, "入力エラー", "台本 Positive は必須です。")
            return None

        # Roles のバリデーション (ID重複、空ID、形式チェックなど)
        role_ids = []
        for index, role in enumerate(self.current_roles):
            r_id = role.id.strip().lower()  # 保存前に整形
            if not r_id:
                QMessageBox.warning(
                    self, "入力エラー", f"{index + 1}番目の配役 ID が空です。"
                )
                return None
            if not r_id.startswith("r") or not r_id[1:].isdigit():
                QMessageBox.warning(
                    self,
                    "入力エラー",
                    f"配役ID '{r_id}' は 'r' + 数字 (例: r1) の形式にしてください。",
                )
                return None
            if r_id in role_ids:
                QMessageBox.warning(
                    self, "入力エラー", f"配役ID '{r_id}' が重複しています。"
                )
                return None
            role_ids.append(r_id)
            role.id = r_id  # 整形したIDを内部データにも反映

        ref_image_path = self.ref_image_edit.text().strip()
        image_mode = self.image_mode_combo.currentText()
        final_image_mode = "txt2img" if not ref_image_path else image_mode
        final_ref_image_path = ref_image_path if final_image_mode != "txt2img" else ""

        if self.initial_data:  # 更新
            updated_cut = self.initial_data
            self._update_object_from_widgets(updated_cut)
            updated_cut.roles = self.current_roles  # 更新されたRoleリストを設定
            updated_cut.reference_image_path = final_ref_image_path  # ★ 更新
            updated_cut.image_mode = final_image_mode  # ★ 更新
            return updated_cut
        else:  # 新規作成
            name = self.name_edit.text().strip()
            negative_template = self.negative_template_edit.toPlainText().strip()
            new_cut = Cut(
                id=f"cut_{int(time.time())}",
                name=name,
                prompt_template=prompt_template,
                negative_template=negative_template,
                roles=self.current_roles,
                reference_image_path=final_ref_image_path,
                image_mode=final_image_mode,
            )
            return new_cut
