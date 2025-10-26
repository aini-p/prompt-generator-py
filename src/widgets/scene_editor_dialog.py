# src/widgets/scene_editor_dialog.py
import time
import json
from PySide6.QtWidgets import (
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
    QListWidget,  # (未使用だが import が残っていても害はない)
    QListWidgetItem,  # (未使用だが import が残っていても害はない)
    QSplitter,  # (未使用だが import が残っていても害はない)
    QGroupBox,  # ★ QGroupBox をインポート
)
from PySide6.QtCore import Slot, Qt
from typing import Optional, Dict, List, Any

from .base_editor_dialog import BaseEditorDialog  # 基底クラスをインポート
from ..models import Scene, FullDatabase, SceneRole, RoleDirection, Cut, Direction


class SceneEditorDialog(BaseEditorDialog):
    def __init__(
        self, initial_data: Optional[Scene], db_dict: Dict[str, Dict], parent=None
    ):
        # 内部状態 (RoleDirection編集用) - super() 前に初期化
        self.current_role_directions: List[RoleDirection] = []
        if initial_data:
            # Deep copy
            self.current_role_directions = [
                RoleDirection(**rd.__dict__)
                for rd in getattr(initial_data, "role_directions", [])
            ]
        # else: 新規の場合のデフォルトは Cut 選択時に設定

        # 基底クラスの __init__ を呼び出す (これにより _populate_fields が呼ばれる)
        super().__init__(initial_data, db_dict, "シーン (Scene)", parent)

    def _populate_fields(self):
        """UI要素を作成し、配置します。"""
        # --- QFormLayout を使用 ---
        self.form_layout = self.setup_form_layout()
        if not self.form_layout:
            return

        # Scene 基本情報
        self.name_edit = QLineEdit(getattr(self.initial_data, "name", ""))
        self.tags_edit = QLineEdit(", ".join(getattr(self.initial_data, "tags", [])))

        # --- ▼▼▼ 引数を正しく渡す ▼▼▼ ---
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
        style_ref_widget = self._create_reference_editor_widget(
            field_name="style_id",
            current_id=getattr(self.initial_data, "style_id", None),
            reference_db_key="styles",
            reference_modal_type="STYLE",
            allow_none=True,
            none_text="(スタイルなし)",
        )
        sd_param_ref_widget = self._create_reference_editor_widget(
            field_name="sd_param_id",
            current_id=getattr(self.initial_data, "sd_param_id", None),
            reference_db_key="sdParams",
            reference_modal_type="SDPARAMS",
            allow_none=True,  # パラメータ未選択も許可 (デフォルトを使う想定)
            none_text="(パラメータなし/デフォルト)",
        )

        self.ref_image_edit = QLineEdit(
            getattr(self.initial_data, "reference_image_path", "")
        )
        self.image_mode_combo = QComboBox()
        self.image_mode_combo.addItems(["txt2img", "img2img", "img2img_polish"])
        self.image_mode_combo.setCurrentText(
            getattr(self.initial_data, "image_mode", "txt2img")
        )

        self.form_layout.addRow("名前:", self.name_edit)
        self.form_layout.addRow("タグ:", self.tags_edit)
        self.form_layout.addRow("背景:", background_ref_widget)
        self.form_layout.addRow("照明:", lighting_ref_widget)
        self.form_layout.addRow("構図:", composition_ref_widget)
        self.form_layout.addRow("スタイル:", style_ref_widget)  # ★ 追加
        self.form_layout.addRow("SD Params:", sd_param_ref_widget)  # ★ 追加
        self.form_layout.addRow("参考画像パス:", self.ref_image_edit)
        self.form_layout.addRow("モード(参考画像):", self.image_mode_combo)

        # --- ▼▼▼ Cut 選択ウィジェットに変更 ▼▼▼ ---
        self.form_layout.addRow(QLabel("--- カット設定 ---"))
        cut_ref_widget = self._create_reference_editor_widget(
            field_name="cut_id",  # 対応する属性名
            current_id=getattr(self.initial_data, "cut_id", None),
            reference_db_key="cuts",
            reference_modal_type="CUT",  # MainWindow のマッピングキー
            allow_none=True,  # Cut が未選択の場合も許容
            none_text="(カット未選択)",
            display_attr="name",  # Cut の name を表示 (なければ id)
        )
        self.form_layout.addRow("カット:", cut_ref_widget)

        # Cut 選択変更時のシグナルを接続
        cut_combo_box = self._reference_widgets.get("cut_id", {}).get("combo")
        if isinstance(cut_combo_box, QComboBox):
            cut_combo_box.currentIndexChanged.connect(self._on_cut_selection_changed)
        # --- ▲▲▲ 変更ここまで ▲▲▲ ---

        # --- ▼▼▼ 演出設定UI (右パネル) を GroupBox に変更 ▼▼▼ ---
        self.direction_group = QGroupBox("演出リスト (選択されたカットの配役)")
        self.direction_assignment_layout = QVBoxLayout(self.direction_group)
        self.form_layout.addRow(self.direction_group)
        # --- ▲▲▲ 変更ここまで ▲▲▲ ---

        # _widgets への登録
        self._widgets["name"] = self.name_edit
        self._widgets["tags"] = self.tags_edit
        self._widgets["reference_image_path"] = self.ref_image_edit
        self._widgets["image_mode"] = self.image_mode_combo
        # background_id, lighting_id, composition_id, cut_id は _reference_widgets に

        # direction_items の初期化
        self.direction_items = list(self.db_dict.get("directions", {}).items())

        # --- ▼▼▼ 初期演出 UI の構築 (cut_id ベース) ▼▼▼ ---
        initial_cut_id = getattr(self.initial_data, "cut_id", None)
        initial_cut = (
            self.db_dict.get("cuts", {}).get(initial_cut_id) if initial_cut_id else None
        )
        self._update_direction_assignment_ui(initial_cut)
        # --- ▲▲▲ 変更ここまで ▲▲▲ ---

    # --- 削除: _populate_cuts_list ---

    # --- ▼▼▼ _on_cut_selection_changed を修正 (QComboBox 用) ▼▼▼ ---
    @Slot(int)
    def _on_cut_selection_changed(self, index: int):
        """Cut コンボボックスの選択が変更されたら、演出UIを更新"""
        cut_combo_box = self._reference_widgets.get("cut_id", {}).get("combo")
        selected_cut_id = (
            cut_combo_box.itemData(index)
            if isinstance(cut_combo_box, QComboBox)
            else None
        )

        selected_cut: Optional[Cut] = None
        if selected_cut_id:
            selected_cut = self.db_dict.get("cuts", {}).get(selected_cut_id)

        print(f"[DEBUG] Cut selection changed to: {selected_cut_id}")
        self._update_direction_assignment_ui(selected_cut)

    # --- ▲▲▲ 修正ここまで ▲▲▲ ---

    def _update_direction_assignment_ui(self, selected_cut: Optional[Cut]):
        """選択された Cut の Roles に基づいて演出割り当てUIを構築"""
        # 古いUIをクリア
        while self.direction_assignment_layout.count():
            item = self.direction_assignment_layout.takeAt(0)
            widget = item.widget()
            layout_item = item.layout()
            if widget:
                widget.deleteLater()
            elif layout_item:
                while layout_item.count():
                    inner_item = layout_item.takeAt(0)
                    inner_widget = inner_item.widget()
                    inner_layout = inner_item.layout()
                    if inner_widget:
                        inner_widget.deleteLater()
                    elif inner_layout:
                        while inner_layout.count():
                            deep_item = inner_layout.takeAt(0)
                            deep_widget = deep_item.widget()
                            if deep_widget:
                                deep_widget.deleteLater()
                        inner_layout.deleteLater()
                layout_item.deleteLater()

        if not selected_cut or not selected_cut.roles:
            self.direction_assignment_layout.addWidget(
                QLabel("(カットを選択するか、カットに配役を追加してください)")
            )
            return

        # Direction データリストを取得 (ComboBox作成用)
        self.direction_items = list(
            self.db_dict.get("directions", {}).items()
        )  # 最新の状態を取得

        for role in selected_cut.roles:
            role_widget = QWidget()
            role_layout = QVBoxLayout(role_widget)
            role_widget.setStyleSheet(
                "border: 1px solid #eee; padding: 5px; margin-bottom: 5px;"
            )
            role_layout.addWidget(QLabel(f"Role: {role.name_in_scene} ({role.id})"))

            # Scene が持つ RoleDirection を探す
            role_dir_data = next(
                (rd for rd in self.current_role_directions if rd.role_id == role.id),
                None,
            )
            # なければ作成してリストに追加
            if role_dir_data is None:
                role_dir_data = RoleDirection(role_id=role.id, direction_ids=[])
                self.current_role_directions.append(role_dir_data)

            current_dirs = role_dir_data.direction_ids

            if not current_dirs:
                role_layout.addWidget(QLabel("(演出なし)", styleSheet="color: #777;"))

            # 割り当て済み Direction の表示と削除ボタン
            for dir_id in current_dirs:
                dir_item_layout = QHBoxLayout()
                dir_name = "(不明)"
                dir_obj = next(
                    (d[1] for d in self.direction_items if d[0] == dir_id), None
                )
                if dir_obj:
                    dir_name = getattr(dir_obj, "name", "(不明)")
                dir_item_layout.addWidget(QLabel(f"- {dir_name} ({dir_id})"))
                remove_dir_btn = QPushButton("🗑️")
                remove_dir_btn.clicked.connect(
                    lambda chk=False,
                    r_id=role.id,
                    d_id=dir_id: self._remove_direction_from_role(r_id, d_id)
                )
                dir_item_layout.addWidget(remove_dir_btn)
                role_layout.addLayout(dir_item_layout)

            # Direction 追加用ウィジェット
            add_dir_layout = QHBoxLayout()
            add_dir_combo = QComboBox()
            add_dir_combo.addItem("＋ 演出を追加...")
            add_dir_combo.addItems(
                [d[1].name for d in self.direction_items if getattr(d[1], "name", None)]
            )
            add_dir_combo.activated.connect(
                lambda index,
                r_id=role.id,
                combo=add_dir_combo: self._add_direction_to_role(r_id, index, combo)
            )
            add_dir_layout.addWidget(add_dir_combo, 1)

            # Direction 新規作成ボタン
            add_new_dir_btn = QPushButton("＋")
            add_new_dir_btn.setToolTip("Add new Direction")
            add_new_dir_btn.clicked.connect(
                lambda: self.request_open_editor.emit("DIRECTION", None, None)
            )
            # Direction 編集ボタン
            edit_dir_btn = QPushButton("✎")
            edit_dir_btn.setToolTip("Edit selected Direction")
            edit_dir_btn.setEnabled(False)
            edit_dir_btn.clicked.connect(
                lambda chk=False, combo=add_dir_combo: self._edit_direction(combo)
            )
            add_dir_combo.currentIndexChanged.connect(
                lambda index, btn=edit_dir_btn: btn.setEnabled(index > 0)
            )

            add_dir_layout.addWidget(add_new_dir_btn)
            add_dir_layout.addWidget(edit_dir_btn)
            role_layout.addLayout(add_dir_layout)

            self.direction_assignment_layout.addWidget(role_widget)

    # --- 削除: _add_cut, _edit_cut, _remove_cut ---

    # --- Direction 割り当て用スロット (変更なし) ---
    @Slot(str, int, QComboBox)
    def _add_direction_to_role(self, role_id: str, combo_index: int, combo: QComboBox):
        if combo_index <= 0:
            return
        dir_index = combo_index - 1
        if 0 <= dir_index < len(self.direction_items):
            direction_id_to_add = self.direction_items[dir_index][0]
            role_dir_data = next(
                (rd for rd in self.current_role_directions if rd.role_id == role_id),
                None,
            )
            if role_dir_data and direction_id_to_add not in role_dir_data.direction_ids:
                role_dir_data.direction_ids.append(direction_id_to_add)
                # UI を再構築
                cut_combo_box = self._reference_widgets.get("cut_id", {}).get("combo")
                selected_cut_id = (
                    cut_combo_box.currentData()
                    if isinstance(cut_combo_box, QComboBox)
                    else None
                )
                selected_cut = (
                    self.db_dict.get("cuts", {}).get(selected_cut_id)
                    if selected_cut_id
                    else None
                )
                self._update_direction_assignment_ui(selected_cut)
            combo.setCurrentIndex(0)

    @Slot(str, str)
    def _remove_direction_from_role(self, role_id: str, direction_id: str):
        role_dir_data = next(
            (rd for rd in self.current_role_directions if rd.role_id == role_id), None
        )
        if role_dir_data and direction_id in role_dir_data.direction_ids:
            role_dir_data.direction_ids.remove(direction_id)
            # UI を再構築
            cut_combo_box = self._reference_widgets.get("cut_id", {}).get("combo")
            selected_cut_id = (
                cut_combo_box.currentData()
                if isinstance(cut_combo_box, QComboBox)
                else None
            )
            selected_cut = (
                self.db_dict.get("cuts", {}).get(selected_cut_id)
                if selected_cut_id
                else None
            )
            self._update_direction_assignment_ui(selected_cut)

    @Slot(QComboBox)
    def _edit_direction(self, combo: QComboBox):
        selected_index = combo.currentIndex()
        if selected_index > 0:
            dir_index = selected_index - 1
            if 0 <= dir_index < len(self.direction_items):
                direction_id_to_edit = self.direction_items[dir_index][0]
                direction_obj_to_edit = self.db_dict.get("directions", {}).get(
                    direction_id_to_edit
                )
                if direction_obj_to_edit:
                    self.request_open_editor.emit(
                        "DIRECTION", direction_obj_to_edit, None
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Error",
                        f"Direction ID '{direction_id_to_edit}' not found.",
                    )

    # --- ▼▼▼ update_combo_box_after_edit を修正 (Cutリスト -> Cutコンボ更新) ▼▼▼ ---
    @Slot(QWidget, str, str)
    def update_combo_box_after_edit(
        self, target_widget: QWidget, db_key: str, select_id: Optional[str]
    ):
        """ネストしたダイアログでの編集/追加後にリストやコンボボックスを更新"""
        # Cut が追加/編集された -> Cut ComboBox を更新
        cut_combo_box = self._reference_widgets.get("cut_id", {}).get("combo")
        if target_widget == cut_combo_box and db_key == "cuts":
            print(
                f"[DEBUG] SceneEditorDialog updating Cut combo box, selecting {select_id}"
            )
            # 基底クラスのメソッドを呼び出して ComboBox を更新
            super().update_combo_box_after_edit(target_widget, db_key, select_id)
            # ★ 選択が変更されたので、演出UIも更新トリガー
            self._on_cut_selection_changed(cut_combo_box.currentIndex())

        elif db_key == "directions":
            # Direction が追加/編集された -> 演出UIを再構築
            print(
                "[DEBUG] SceneEditorDialog detected Direction change. Rebuilding Direction UI."
            )
            self.direction_items = list(
                self.db_dict.get("directions", {}).items()
            )  # 最新リスト取得
            # 現在選択中の Cut を取得して UI 更新
            cut_combo_box = self._reference_widgets.get("cut_id", {}).get("combo")
            selected_cut_id = (
                cut_combo_box.currentData()
                if isinstance(cut_combo_box, QComboBox)
                else None
            )
            selected_cut = (
                self.db_dict.get("cuts", {}).get(selected_cut_id)
                if selected_cut_id
                else None
            )
            self._update_direction_assignment_ui(selected_cut)

        else:
            # 他の ComboBox (Background など) の更新は基底クラスに任せる
            super().update_combo_box_after_edit(target_widget, db_key, select_id)

    # --- ▲▲▲ 変更ここまで ▲▲▲ ---

    # --- 削除: rebuild_roles_directions_ui, add_role_ui, handle_role_change, remove_role_ui ---

    def get_data(self) -> Optional[Scene]:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "名前は必須です。")
            return None

        # --- ID をヘルパーから取得 ---
        cut_id = self._get_widget_value("cut_id")
        style_id = self._get_widget_value("style_id")  # ★ Style ID 取得
        sd_param_id = self._get_widget_value("sd_param_id")  # ★ SD Param ID 取得
        bg_id = self._get_widget_value("background_id")
        light_id = self._get_widget_value("lighting_id")
        comp_id = self._get_widget_value("composition_id")

        # --- (オプション) Cut が選択されているかチェック ---
        # if not cut_id:
        #     QMessageBox.warning(self, "入力エラー", "カットを選択してください。")
        #     return None

        # Role ID の一貫性チェック
        selected_cut = self.db_dict.get("cuts", {}).get(cut_id) if cut_id else None
        valid_role_directions = []
        if selected_cut and isinstance(selected_cut, Cut):
            cut_role_ids = {role.id for role in selected_cut.roles}
            valid_role_directions = [
                rd for rd in self.current_role_directions if rd.role_id in cut_role_ids
            ]
        else:
            valid_role_directions = []  # Cut がない、または Role がない場合

        if self.initial_data:  # 更新
            updated_scene = self.initial_data
            if not self._update_object_from_widgets(updated_scene):
                return None
            # cut_id と RoleDirections を更新
            updated_scene.cut_id = cut_id
            updated_scene.role_directions = valid_role_directions
            # image_mode と path
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
                background_id=bg_id or "",
                lighting_id=light_id or "",
                composition_id=comp_id or "",
                cut_id=cut_id,  # ★ cut_id を設定
                role_directions=valid_role_directions,
                reference_image_path=ref_image_path
                if final_image_mode != "txt2img"
                else "",
                image_mode=final_image_mode,
                style_id=style_id,  # ★ 追加
                sd_param_id=sd_param_id,  # ★ 追加
            )
            return new_scene

    @Slot(QWidget, str, str)
    def update_combo_box_after_edit(
        self, target_widget: QWidget, db_key: str, select_id: Optional[str]
    ):
        """ネストしたダイアログでの編集/追加後にリストやコンボボックスを更新"""
        # カット、スタイル、SDパラメータ、または他の参照ウィジェットのコンボボックスかチェック
        target_combo_box = None
        for field_name, ref_info in self._reference_widgets.items():
            if ref_info.get("combo") == target_widget:
                target_combo_box = target_widget
                break

        if target_combo_box and (
            db_key == "cuts"
            or db_key == "styles"
            or db_key == "sdParams"
            or db_key == "backgrounds"
            or db_key == "lighting"
            or db_key == "compositions"
        ):
            print(
                f"[DEBUG] SceneEditorDialog updating {db_key} combo box, selecting {select_id}"
            )
            # 基底クラスのメソッドを呼び出して ComboBox を更新
            super().update_combo_box_after_edit(target_widget, db_key, select_id)
            # カットが変更された場合のみ演出UIを更新
            if db_key == "cuts":
                self._on_cut_selection_changed(target_combo_box.currentIndex())

        elif db_key == "directions":
            # Direction が追加/編集された -> 演出UIを再構築 (変更なし)
            print(
                "[DEBUG] SceneEditorDialog detected Direction change. Rebuilding Direction UI."
            )
            self.direction_items = list(self.db_dict.get("directions", {}).items())
            cut_combo_box = self._reference_widgets.get("cut_id", {}).get("combo")
            selected_cut_id = (
                cut_combo_box.currentData()
                if isinstance(cut_combo_box, QComboBox)
                else None
            )
            selected_cut = (
                self.db_dict.get("cuts", {}).get(selected_cut_id)
                if selected_cut_id
                else None
            )
            self._update_direction_assignment_ui(selected_cut)
        else:
            # 他のケース（Actor編集など）は基底クラスに任せる
            super().update_combo_box_after_edit(target_widget, db_key, select_id)
