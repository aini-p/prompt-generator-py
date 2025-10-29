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
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QGroupBox,
    QAbstractItemView,
    QInputDialog,
    QDialog,
)
from PySide6.QtCore import Slot, Qt
from typing import Optional, Dict, List, Any, Set, Tuple

from .base_editor_dialog import BaseEditorDialog
from ..models import (
    Scene,
    FullDatabase,
    SceneRole,
    RoleDirection,
    Cut,
    Direction,
    Style,
    StableDiffusionParams,
    State,
    AdditionalPrompt,
)
from .generic_selection_dialog import GenericSelectionDialog


class SceneEditorDialog(BaseEditorDialog):
    def __init__(
        self, initial_data: Optional[Scene], db_dict: Dict[str, Dict], parent=None
    ):
        self.current_role_directions: List[RoleDirection] = []
        self.current_state_categories: List[str] = []
        self.current_additional_prompt_ids: List[str] = []
        if initial_data:
            self.current_role_directions = [
                RoleDirection(**rd.__dict__)
                for rd in getattr(initial_data, "role_directions", [])
            ]
            if hasattr(initial_data, "state_categories"):
                self.current_state_categories = list(initial_data.state_categories)
            if hasattr(initial_data, "additional_prompt_ids"):
                self.current_additional_prompt_ids = list(
                    initial_data.additional_prompt_ids
                )

        super().__init__(initial_data, db_dict, "シーン (Scene)", parent)

    def _populate_fields(self):
        """UI要素を作成し、配置します。"""
        self.form_layout = self.setup_form_layout()
        if not self.form_layout:
            return

        # --- Scene 基本情報 (変更なし) ---
        self.name_edit = QLineEdit(getattr(self.initial_data, "name", ""))
        self.tags_edit = QLineEdit(", ".join(getattr(self.initial_data, "tags", [])))

        # --- 参照ウィジェット (変更なし) ---
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
            allow_none=True,
            none_text="(パラメータなし/デフォルト)",
        )

        # --- レイアウトに追加 (State Category UI 以外は先に追加) ---
        self.form_layout.addRow("名前:", self.name_edit)
        self.form_layout.addRow("タグ:", self.tags_edit)
        self.form_layout.addRow("背景:", background_ref_widget)
        self.form_layout.addRow("照明:", lighting_ref_widget)
        self.form_layout.addRow("構図:", composition_ref_widget)
        self.form_layout.addRow("スタイル:", style_ref_widget)
        self.form_layout.addRow("SD Params:", sd_param_ref_widget)

        # --- Cut 選択、演出UIの追加 (変更なし) ---
        self.form_layout.addRow(QLabel("--- カット設定 ---"))
        cut_ref_widget = self._create_reference_editor_widget(
            field_name="cut_id",
            current_id=getattr(self.initial_data, "cut_id", None),
            reference_db_key="cuts",
            reference_modal_type="CUT",
            allow_none=True,
            none_text="(カット未選択)",
            display_attr="name",
        )
        self.form_layout.addRow("カット:", cut_ref_widget)
        cut_combo_box = self._reference_widgets.get("cut_id", {}).get("combo")
        if isinstance(cut_combo_box, QComboBox):
            cut_combo_box.currentIndexChanged.connect(self._on_cut_selection_changed)
        self.direction_group = QGroupBox("演出リスト (選択されたカットの配役)")
        self.direction_assignment_layout = QVBoxLayout(self.direction_group)
        self.form_layout.addRow(self.direction_group)

        # --- ▼▼▼ State Category UI を最後に移動 ▼▼▼ ---
        self.form_layout.addRow(QLabel("--- 状態カテゴリ (State Categories) ---"))
        # 選択済みリスト
        self.selected_categories_list = QListWidget()
        self.selected_categories_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._populate_category_list()  # 初期表示

        # ボタンレイアウト
        category_btn_layout = QHBoxLayout()
        add_category_btn = QPushButton("＋ カテゴリを追加...")
        remove_category_btn = QPushButton("－ 選択したカテゴリを削除")
        add_category_btn.clicked.connect(self._add_category_dialog)
        remove_category_btn.clicked.connect(self._remove_selected_category)

        category_btn_layout.addWidget(add_category_btn)
        category_btn_layout.addWidget(remove_category_btn)
        category_btn_layout.addStretch()

        self.form_layout.addRow(self.selected_categories_list)  # リストを配置
        self.form_layout.addRow(category_btn_layout)  # ボタンを配置

        # --- ▼▼▼ Additional Prompt UI を追加 ▼▼▼ ---
        self.form_layout.addRow(QLabel("--- 追加プロンプト (Additional Prompts) ---"))
        # 選択済みリスト
        self.selected_ap_list = QListWidget()  # ★ 変数名変更
        self.selected_ap_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.selected_ap_list.itemDoubleClicked.connect(
            self._handle_ap_double_clicked
        )  # ★ ダブルクリック追加
        self._populate_ap_list()  # ★ メソッド呼び出し

        # ボタンレイアウト
        ap_btn_layout = QHBoxLayout()
        add_ap_btn = QPushButton("＋ 追加プロンプトを選択...")
        add_new_ap_btn = QPushButton("＋ 新規作成")
        remove_ap_btn = QPushButton("－ 選択したものを削除")
        add_ap_btn.clicked.connect(self._add_ap_dialog)
        add_new_ap_btn.clicked.connect(self._handle_add_new_ap)
        remove_ap_btn.clicked.connect(self._remove_selected_ap)

        ap_btn_layout.addWidget(add_ap_btn)
        ap_btn_layout.addWidget(add_new_ap_btn)
        ap_btn_layout.addWidget(remove_ap_btn)
        ap_btn_layout.addStretch()

        self.form_layout.addRow(self.selected_ap_list)
        self.form_layout.addRow(ap_btn_layout)

        # _widgets への登録
        self._widgets["name"] = self.name_edit
        self._widgets["tags"] = self.tags_edit
        # state_categories は _widgets に登録しない

        # direction_items 初期化、初期演出UI構築 (変更なし)
        self.direction_items = list(self.db_dict.get("directions", {}).items())
        initial_cut_id = getattr(self.initial_data, "cut_id", None)
        initial_cut = (
            self.db_dict.get("cuts", {}).get(initial_cut_id) if initial_cut_id else None
        )
        self._update_direction_assignment_ui(initial_cut)

    # --- ▼▼▼ Additional Prompt リスト関連メソッドを追加 ▼▼▼ ---
    def _populate_ap_list(self):
        """選択済みの Additional Prompt リストを更新します。"""
        self.selected_ap_list.clear()
        all_aps = self.db_dict.get("additional_prompts", {})
        current_id_order = {
            ap_id: i for i, ap_id in enumerate(self.current_additional_prompt_ids)
        }
        sorted_ids = sorted(
            self.current_additional_prompt_ids,
            key=lambda ap_id: current_id_order.get(ap_id, float("inf")),
        )
        for ap_id in sorted_ids:
            ap = all_aps.get(ap_id)
            item_text = f"AP ID not found: {ap_id}"
            if ap:
                item_text = f"{getattr(ap, 'name', 'N/A')} ({ap_id})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, ap_id)
            self.selected_ap_list.addItem(item)

    @Slot()
    def _add_ap_dialog(self):
        """利用可能な Additional Prompt を選択するダイアログを表示し、追加します。"""
        all_aps = self.db_dict.get("additional_prompts", {})
        if not all_aps:  # ... (メッセージ表示) ...
            return
        selectable_aps = {
            ap_id: ap
            for ap_id, ap in all_aps.items()
            if ap_id not in self.current_additional_prompt_ids
        }
        if not selectable_aps:  # ... (メッセージ表示) ...
            return

        # --- ▼▼▼ GenericSelectionDialog を使用 ▼▼▼ ---
        # AdditionalPrompt オブジェクトを表示するための関数
        def display_ap(ap: AdditionalPrompt) -> str:
            return f"{getattr(ap, 'name', 'N/A')} ({getattr(ap, 'id', 'N/A')})"

        # ソート用の関数 (名前順)
        def sort_ap_key(item: Tuple[str, AdditionalPrompt]) -> str:
            ap = item[1]
            return getattr(ap, "name", "").lower()

        dialog = GenericSelectionDialog(
            items_data=selectable_aps,
            display_func=display_ap,
            window_title="Select Additional Prompt to Add",
            filter_placeholder="Filter by name or ID...",
            sort_key_func=sort_ap_key,  # 名前でソート
            parent=self,
        )
        # --- ▲▲▲ 修正ここまで ▲▲▲ ---

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_id = dialog.get_selected_item_id()  # ★ メソッド名変更
            if selected_id and selected_id not in self.current_additional_prompt_ids:
                self.current_additional_prompt_ids.append(selected_id)
                self._populate_ap_list()
                self._mark_data_changed()

    @Slot()
    def _handle_add_new_ap(self):
        """新規 Additional Prompt 作成ダイアログを開くリクエスト"""
        print(
            "[DEBUG] Requesting editor for new ADDITIONAL_PROMPT from SceneEditorDialog"
        )
        # ★ SimplePartEditorDialog を使うためのタイプ名を決定 (例: "ADDITIONAL_PROMPT")
        self.request_open_editor.emit("ADDITIONAL_PROMPT", None, None)

    @Slot()
    def _remove_selected_ap(self):
        """選択済みリストで選択された Additional Prompt を削除します。"""
        selected_items = self.selected_ap_list.selectedItems()
        if selected_items:
            ap_id_to_remove = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if ap_id_to_remove in self.current_additional_prompt_ids:
                self.current_additional_prompt_ids.remove(ap_id_to_remove)
                self._populate_ap_list()
                self._mark_data_changed()

    @Slot(QListWidgetItem)
    def _handle_ap_double_clicked(self, item: QListWidgetItem):
        """AP リストの項目がダブルクリックされたときの処理"""
        ap_id = item.data(Qt.ItemDataRole.UserRole)
        ap_data = self.db_dict.get("additional_prompts", {}).get(ap_id)
        if ap_data:
            print(f"[DEBUG] Requesting editor for ADDITIONAL_PROMPT {ap_id}")
            self.request_open_editor.emit("ADDITIONAL_PROMPT", ap_data, None)
        else:
            QMessageBox.warning(
                self, "Error", f"Could not find Additional Prompt data for ID: {ap_id}"
            )

    # --- ▼▼▼ State Category リスト関連メソッドを修正 ▼▼▼ ---
    def _get_available_categories(self) -> List[str]:
        """データベース内の全 State からユニークなカテゴリを取得します。"""
        all_states = self.db_dict.get("states", {})
        available_categories: Set[str] = set()
        if isinstance(all_states, dict):
            for state in all_states.values():
                category = getattr(state, "category", "").strip()
                if category:
                    available_categories.add(category)
        return sorted(list(available_categories))

    def _populate_category_list(self):  # ★ メソッド名変更 (単数形)
        """選択済みカテゴリのリストを更新します。"""
        self.selected_categories_list.clear()
        # self.available_categories_list は削除されたので関連処理も削除
        sorted_selected = sorted(self.current_state_categories)
        for category in sorted_selected:
            self.selected_categories_list.addItem(category)

    @Slot()
    def _add_category_dialog(self):  # ★ メソッド名変更
        """利用可能なカテゴリを選択するダイアログを表示し、追加します。"""
        available_categories = self._get_available_categories()
        # 現在選択されていないカテゴリのみを候補とする
        selectable_categories = [
            cat
            for cat in available_categories
            if cat not in self.current_state_categories
        ]

        if not selectable_categories:
            QMessageBox.information(
                self, "カテゴリ追加", "追加可能なカテゴリがありません。"
            )
            return

        # QInputDialog を使ってリストから選択させる
        category_to_add, ok = QInputDialog.getItem(
            self,
            "カテゴリ追加",
            "追加する状態カテゴリを選択してください:",
            selectable_categories,
            0,  # 初期選択インデックス
            False,  # 編集不可
        )

        if ok and category_to_add:
            if category_to_add not in self.current_state_categories:
                self.current_state_categories.append(category_to_add)
                self._populate_category_list()
                self._mark_data_changed()

    @Slot()
    def _remove_selected_category(self):  # ★ メソッド名変更
        """選択済みリストで選択されたカテゴリを削除します。"""
        selected_items = self.selected_categories_list.selectedItems()
        if selected_items:
            category_to_remove = selected_items[0].text()
            if category_to_remove in self.current_state_categories:
                self.current_state_categories.remove(category_to_remove)
                self._populate_category_list()
                self._mark_data_changed()

    # --- ▲▲▲ 修正ここまで ▲▲▲ ---

    # --- (以降のメソッド _on_cut_selection_changed, _update_direction_assignment_ui などは変更なし) ---
    @Slot(int)
    def _on_cut_selection_changed(self, index: int):
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

    def _update_direction_assignment_ui(self, selected_cut: Optional[Cut]):
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
                    if inner_item:
                        inner_widget = inner_item.widget()
                        inner_layout = inner_item.layout()
                        if inner_widget:
                            inner_widget.deleteLater()
                        elif inner_layout:
                            while inner_layout.count():
                                deep_item = inner_layout.takeAt(0)
                                if deep_item and deep_item.widget():
                                    deep_item.widget().deleteLater()
                            inner_layout.deleteLater()
                layout_item.deleteLater()

        if not selected_cut or not selected_cut.roles:
            self.direction_assignment_layout.addWidget(
                QLabel("(カットを選択するか、カットに配役を追加してください)")
            )
            return

        self.direction_items = list(self.db_dict.get("directions", {}).items())
        valid_role_ids_in_cut = {role.id for role in selected_cut.roles if role.id}

        for role in selected_cut.roles:
            if not role.id:
                continue
            role_widget = QWidget()
            role_layout = QVBoxLayout(role_widget)
            role_widget.setStyleSheet(
                "border: 1px solid #eee; padding: 5px; margin-bottom: 5px;"
            )
            role_layout.addWidget(QLabel(f"Role: {role.name_in_scene} ({role.id})"))

            role_dir_data = next(
                (rd for rd in self.current_role_directions if rd.role_id == role.id),
                None,
            )
            if role_dir_data is None:
                role_dir_data = RoleDirection(role_id=role.id, direction_ids=[])
                self.current_role_directions.append(role_dir_data)

            current_dirs = role_dir_data.direction_ids
            if not current_dirs:
                role_layout.addWidget(QLabel("(演出なし)", styleSheet="color: #777;"))

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

            add_dir_layout = QHBoxLayout()
            add_dir_combo = QComboBox()
            add_dir_combo.addItem("＋ 演出を追加...")
            sorted_directions = sorted(
                self.direction_items,
                key=lambda item: getattr(item[1], "name", "").lower(),
            )
            for dir_id, direction in sorted_directions:
                add_dir_combo.addItem(getattr(direction, "name", "(No Name)"), dir_id)

            add_dir_combo.activated.connect(
                lambda index,
                r_id=role.id,
                combo=add_dir_combo: self._add_direction_to_role(r_id, index, combo)
            )
            add_dir_layout.addWidget(add_dir_combo, 1)

            add_new_dir_btn = QPushButton("＋")
            add_new_dir_btn.setToolTip("Add new Direction")
            add_new_dir_btn.clicked.connect(
                lambda: self.request_open_editor.emit("DIRECTION", None, None)
            )
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

        self.current_role_directions = [
            rd
            for rd in self.current_role_directions
            if rd.role_id in valid_role_ids_in_cut
        ]

    @Slot(str, int, QComboBox)
    def _add_direction_to_role(self, role_id: str, combo_index: int, combo: QComboBox):
        if combo_index <= 0:
            return
        direction_id_to_add = combo.itemData(combo_index)
        if direction_id_to_add:
            role_dir_data = next(
                (rd for rd in self.current_role_directions if rd.role_id == role_id),
                None,
            )
            if role_dir_data and direction_id_to_add not in role_dir_data.direction_ids:
                role_dir_data.direction_ids.append(direction_id_to_add)
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
            direction_id_to_edit = combo.currentData()
            if direction_id_to_edit:
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

    @Slot(QWidget, str, str)
    def update_combo_box_after_edit(
        self, target_widget: QWidget, db_key: str, select_id: Optional[str]
    ):
        cut_combo_box = self._reference_widgets.get("cut_id", {}).get("combo")
        is_target_cut_combo = False
        if isinstance(target_widget, QComboBox):
            if target_widget == cut_combo_box and db_key == "cuts":
                is_target_cut_combo = True
            else:
                for ref_info in self._reference_widgets.values():
                    if ref_info.get("combo") == target_widget:
                        super().update_combo_box_after_edit(
                            target_widget, db_key, select_id
                        )
                        return

        if is_target_cut_combo:
            print(
                f"[DEBUG] SceneEditorDialog updating Cut combo box, selecting {select_id}"
            )
            super().update_combo_box_after_edit(target_widget, db_key, select_id)
            selected_cut = (
                self.db_dict.get("cuts", {}).get(select_id) if select_id else None
            )
            self._update_direction_assignment_ui(selected_cut)
        elif db_key == "directions":
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
        elif db_key == "states":
            print(
                "[DEBUG] SceneEditorDialog detected State change. Repopulating category lists."
            )
            self._populate_category_list()  # ★ メソッド名変更
        elif db_key == "additional_prompts":
            print(
                "[DEBUG] SceneEditorDialog detected Additional Prompt change. Repopulating AP list."
            )
            self._populate_ap_list()  # AP リストを再描画
        else:
            super().update_combo_box_after_edit(target_widget, db_key, select_id)

    def get_data(self) -> Optional[Scene]:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "名前は必須です。")
            return None

        cut_id = self._get_widget_value("cut_id")
        style_id = self._get_widget_value("style_id")
        sd_param_id = self._get_widget_value("sd_param_id")
        bg_id = self._get_widget_value("background_id")
        light_id = self._get_widget_value("lighting_id")
        comp_id = self._get_widget_value("composition_id")

        state_categories = sorted(self.current_state_categories)
        additional_prompt_ids = self.current_additional_prompt_ids

        selected_cut = self.db_dict.get("cuts", {}).get(cut_id) if cut_id else None
        valid_role_directions = []
        if selected_cut and isinstance(selected_cut, Cut):
            cut_role_ids = {role.id for role in selected_cut.roles if role.id}
            valid_role_directions = [
                rd for rd in self.current_role_directions if rd.role_id in cut_role_ids
            ]

        if self.initial_data:
            updated_scene = self.initial_data
            if not self._update_object_from_widgets(updated_scene):
                return None
            # --- ▼▼▼ 取得したIDをオブジェクトに設定 ▼▼▼ ---
            updated_scene.background_id = bg_id or ""  # None の場合は空文字に
            updated_scene.lighting_id = light_id or ""
            updated_scene.composition_id = comp_id or ""
            updated_scene.style_id = style_id  # None の可能性あり
            updated_scene.sd_param_id = sd_param_id  # None の可能性あり
            updated_scene.cut_id = cut_id  # None の可能性あり
            updated_scene.role_directions = valid_role_directions
            updated_scene.state_categories = state_categories
            updated_scene.additional_prompt_ids = additional_prompt_ids
            # --- ▲▲▲ 修正 ▲▲▲ ---
            print(f"[DEBUG] Returning updated scene: {updated_scene}")
            return updated_scene
        else:
            tags_text = self._widgets["tags"].text()
            new_scene = Scene(
                id=f"scene_{int(time.time())}",
                name=name,
                tags=[t.strip() for t in tags_text.split(",") if t.strip()],
                background_id=bg_id or "",
                lighting_id=light_id or "",
                composition_id=comp_id or "",
                cut_id=cut_id,
                role_directions=valid_role_directions,
                style_id=style_id,
                sd_param_id=sd_param_id,
                state_categories=state_categories,
                additional_prompt_ids=additional_prompt_ids,
            )
            return new_scene
