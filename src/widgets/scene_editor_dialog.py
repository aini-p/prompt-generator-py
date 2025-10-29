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
from PySide6.QtCore import Slot, Qt, Signal
from typing import Optional, Dict, List, Any, Set, Tuple
import traceback
from .base_editor_dialog import BaseEditorDialog
from ..models import (
    Scene,
    FullDatabase,
    SceneRole,
    Cut,
    Style,
    StableDiffusionParams,
    State,
    AdditionalPrompt,
    RoleAppearanceAssignment,
    Costume,
    Pose,
    Expression,
    PromptPartBase,
    Actor,
)
from .generic_selection_dialog import GenericSelectionDialog


# ==============================================================================
# RoleAssignmentWidget: 配役ごとの 衣装/ポーズ/表情 リスト管理UI
# ==============================================================================
class RoleAssignmentWidget(QWidget):
    """配役ごとに衣装・ポーズ・表情のリストを管理するウィジェット"""

    # シグナル定義 (外部エディタを開くリクエスト用)
    request_add_new = Signal(str, str)  # modal_type, role_id (どのロールのボタンか)
    request_edit_item = Signal(str, str)  # modal_type, item_id
    assignment_changed = Signal()

    def __init__(
        self,
        role: SceneRole,
        assignment: RoleAppearanceAssignment,
        db_dict: Dict[str, Dict],
        parent=None,
    ):
        super().__init__(parent)
        self.role = role
        self.assignment = RoleAppearanceAssignment(  # ★ ディープコピー
            role_id=assignment.role_id,
            costume_ids=list(assignment.costume_ids),
            pose_ids=list(assignment.pose_ids),
            expression_ids=list(assignment.expression_ids),
        )
        self.db_dict = db_dict
        self._init_ui()

    def get_assignment_data(self) -> RoleAppearanceAssignment:
        """現在の割り当てデータを返す"""
        return self.assignment

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        self.setStyleSheet(
            "border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9;"
        )  # スタイル調整

        role_label = QLabel(f"<b>配役: {self.role.name_in_scene} ({self.role.id})</b>")
        main_layout.addWidget(role_label)

        h_layout = QHBoxLayout()
        main_layout.addLayout(h_layout)

        # 各 Appearance タイプ用のウィジェットを作成
        self.costume_widget = self._create_appearance_section(
            "衣装", "costumes", "COSTUME", self.assignment.costume_ids
        )
        self.pose_widget = self._create_appearance_section(
            "ポーズ", "poses", "POSE", self.assignment.pose_ids
        )
        self.expression_widget = self._create_appearance_section(
            "表情", "expressions", "EXPRESSION", self.assignment.expression_ids
        )

        h_layout.addWidget(self.costume_widget)
        h_layout.addWidget(self.pose_widget)
        h_layout.addWidget(self.expression_widget)

    def _create_appearance_section(
        self, title: str, db_key: str, modal_type: str, id_list: List[str]
    ) -> QGroupBox:
        """衣装/ポーズ/表情のリストとボタンを持つ GroupBox を作成"""
        group = QGroupBox(title)
        group.setStyleSheet(
            "QGroupBox { border: 1px solid #ccc; margin-top: 0.5em;} QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }"
        )  # スタイル調整
        layout = QVBoxLayout(group)

        list_widget = QListWidget()
        list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        list_widget.itemDoubleClicked.connect(
            lambda item, m_type=modal_type: self._handle_item_double_clicked(
                item, m_type
            )
        )
        layout.addWidget(list_widget)
        self._populate_list(list_widget, db_key, id_list)  # 初期表示

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("追加...")
        remove_btn = QPushButton("削除")
        new_btn = QPushButton("新規")

        add_btn.clicked.connect(
            lambda chk=False,
            lw=list_widget,
            dk=db_key,
            mt=modal_type,
            il=id_list: self._add_item_dialog(lw, dk, mt, il)
        )
        remove_btn.clicked.connect(
            lambda chk=False, lw=list_widget, dk=db_key, il=id_list: self._remove_item(
                lw, dk, il
            )
        )
        new_btn.clicked.connect(
            lambda chk=False, mt=modal_type: self.request_add_new.emit(mt, self.role.id)
        )

        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addWidget(new_btn)
        layout.addLayout(btn_layout)

        # 内部参照用にリストウィジェットを保持
        setattr(self, f"{db_key}_list_widget", list_widget)

        return group

    def _populate_list(self, list_widget: QListWidget, db_key: str, id_list: List[str]):
        """指定されたリストウィジェットの内容を更新"""
        list_widget.clear()
        all_items = self.db_dict.get(db_key, {})
        # 追加された順に表示
        current_id_order = {item_id: i for i, item_id in enumerate(id_list)}
        sorted_ids = sorted(
            id_list, key=lambda item_id: current_id_order.get(item_id, float("inf"))
        )

        for item_id in sorted_ids:
            item_obj = all_items.get(item_id)
            item_text = f"ID not found: {item_id}"
            if item_obj:
                item_text = f"{getattr(item_obj, 'name', 'N/A')} ({item_id})"
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.ItemDataRole.UserRole, item_id)
            list_widget.addItem(list_item)

    def _add_item_dialog(
        self, list_widget: QListWidget, db_key: str, modal_type: str, id_list: List[str]
    ):
        """選択ダイアログを開いてアイテムをリストに追加"""
        all_items = self.db_dict.get(db_key, {})
        if not all_items:
            QMessageBox.information(
                self, f"{modal_type} 追加", f"利用可能な {modal_type} がありません。"
            )
            return
        selectable_items = {
            item_id: item
            for item_id, item in all_items.items()
            if item_id not in id_list
        }
        if not selectable_items:
            QMessageBox.information(
                self, f"{modal_type} 追加", f"追加可能な {modal_type} がありません。"
            )
            return

        def display_func(item: Any) -> str:
            return f"{getattr(item, 'name', 'N/A')} ({getattr(item, 'id', 'N/A')})"

        def sort_func(item_tuple: Tuple[str, Any]) -> str:
            return getattr(item_tuple[1], "name", "").lower()

        dialog = GenericSelectionDialog(
            items_data=selectable_items,
            display_func=display_func,
            window_title=f"{modal_type} を選択",
            filter_placeholder="Filter by name or ID...",
            sort_key_func=lambda item: sort_func(item),
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_id = dialog.get_selected_item_id()
            if selected_id and selected_id not in id_list:
                id_list.append(selected_id)  # self.assignment のリストを変更
                self._populate_list(list_widget, db_key, id_list)
                self.assignment_changed.emit()  # ★ 変更を通知

    def _remove_item(self, list_widget: QListWidget, db_key: str, id_list: List[str]):
        """リストから選択中のアイテムを削除"""
        selected_items = list_widget.selectedItems()
        if selected_items:
            item_id_to_remove = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if item_id_to_remove in id_list:
                id_list.remove(item_id_to_remove)  # self.assignment のリストを変更
                self._populate_list(list_widget, db_key, id_list)
                self.assignment_changed.emit()  # ★ 変更を通知

    def _handle_item_double_clicked(self, item: QListWidgetItem, modal_type: str):
        """リスト項目ダブルクリックで編集ダイアログを開くリクエスト"""
        item_id = item.data(Qt.ItemDataRole.UserRole)
        # どの db_key かを modal_type から判断 (簡易的)
        db_key_map = {
            "COSTUME": "costumes",
            "POSE": "poses",
            "EXPRESSION": "expressions",
        }
        db_key = db_key_map.get(modal_type)
        if not db_key:
            return

        item_data = self.db_dict.get(db_key, {}).get(item_id)
        if item_data:
            print(
                f"[DEBUG] RoleAssignmentWidget requesting editor for {modal_type} {item_id}"
            )
            self.request_edit_item.emit(modal_type, item_id)  # SceneEditorDialog へ通知
        else:
            QMessageBox.warning(self, "Error", f"Could not find data for ID: {item_id}")

    def refresh_list(self, db_key: str):
        """指定されたタイプのリストを再描画する (外部からの呼び出し用)"""
        list_widget: Optional[QListWidget] = getattr(
            self, f"{db_key}_list_widget", None
        )
        id_list: Optional[List[str]] = None
        if db_key == "costumes":
            id_list = self.assignment.costume_ids
        elif db_key == "poses":
            id_list = self.assignment.pose_ids
        elif db_key == "expressions":
            id_list = self.assignment.expression_ids

        if list_widget and id_list is not None:
            self._populate_list(list_widget, db_key, id_list)


# ==============================================================================
# SceneEditorDialog
# ==============================================================================
class SceneEditorDialog(BaseEditorDialog):
    def __init__(
        self, initial_data: Optional[Scene], db_dict: Dict[str, Dict], parent=None
    ):
        # --- ▼▼▼ current_role_assignments を初期化 ▼▼▼ ---
        self.current_role_assignments: List[RoleAppearanceAssignment] = []
        # --- ▲▲▲ 追加ここまで ▲▲▲ ---
        self.current_state_categories: List[str] = []
        self.current_additional_prompt_ids: List[str] = []
        if initial_data:
            # ▼▼▼ role_assignments をディープコピー ▼▼▼
            if hasattr(initial_data, "role_assignments"):
                self.current_role_assignments = [
                    RoleAppearanceAssignment(
                        role_id=ra.role_id,
                        costume_ids=list(ra.costume_ids),
                        pose_ids=list(ra.pose_ids),
                        expression_ids=list(ra.expression_ids),
                    )
                    for ra in initial_data.role_assignments
                ]
            # ▲▲▲ 変更 ▲▲▲
            if hasattr(initial_data, "state_categories"):
                self.current_state_categories = list(initial_data.state_categories)
            if hasattr(initial_data, "additional_prompt_ids"):
                self.current_additional_prompt_ids = list(
                    initial_data.additional_prompt_ids
                )

        super().__init__(initial_data, db_dict, "シーン (Scene)", parent)
        # self._data_changed = False # 不要

    def _populate_fields(self):
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
            allow_none=True,  # 背景は任意
        )
        lighting_ref_widget = self._create_reference_editor_widget(
            field_name="lighting_id",
            current_id=getattr(self.initial_data, "lighting_id", None),
            reference_db_key="lighting",
            reference_modal_type="LIGHTING",
            allow_none=True,  # 照明は任意
        )
        composition_ref_widget = self._create_reference_editor_widget(
            field_name="composition_id",
            current_id=getattr(self.initial_data, "composition_id", None),
            reference_db_key="compositions",
            reference_modal_type="COMPOSITION",
            allow_none=True,  # 構図は任意
        )
        style_ref_widget = self._create_reference_editor_widget(
            field_name="style_id",
            current_id=getattr(self.initial_data, "style_id", None),
            reference_db_key="styles",
            reference_modal_type="STYLE",
            allow_none=True,  # Style は任意
        )
        sd_param_ref_widget = self._create_reference_editor_widget(
            field_name="sd_param_id",
            current_id=getattr(self.initial_data, "sd_param_id", None),
            reference_db_key="sdParams",
            reference_modal_type="SDPARAMS",
            allow_none=True,  # SD Params は任意
        )
        # --- レイアウトに追加 (State Category, AP UI 以外は先に追加) ---
        self.form_layout.addRow("名前:", self.name_edit)
        self.form_layout.addRow("タグ:", self.tags_edit)
        self.form_layout.addRow("背景:", background_ref_widget)
        self.form_layout.addRow("照明:", lighting_ref_widget)
        self.form_layout.addRow("構図:", composition_ref_widget)
        self.form_layout.addRow("スタイル:", style_ref_widget)
        self.form_layout.addRow("SD Params:", sd_param_ref_widget)

        # --- Cut 選択 (変更なし) ---
        # --- Cut 選択 ---
        self.form_layout.addRow(QLabel("--- カット設定 ---"))
        # --- ▼▼▼ Cut 参照ウィジェット呼び出し修正 ▼▼▼ ---
        cut_ref_widget = self._create_reference_editor_widget(
            field_name="cut_id",
            current_id=getattr(self.initial_data, "cut_id", None),
            reference_db_key="cuts",
            reference_modal_type="CUT",
            allow_none=False,  # Cut は必須とする場合
            none_text="- カットを選択 -",  # allow_none=False でも表示されるテキスト
        )
        # --- ▲▲▲ 修正ここまで ▲▲▲ ---
        self.form_layout.addRow("カット:", cut_ref_widget)
        # --- ▼▼▼ QComboBox を確実に取得するよう修正 ▼▼▼ ---
        cut_combo_box_widget = self._reference_widgets.get("cut_id", {}).get("combo")
        if isinstance(cut_combo_box_widget, QComboBox):
            cut_combo_box_widget.currentIndexChanged.connect(
                self._on_cut_selection_changed
            )
        # --- ▲▲▲ 修正ここまで ▲▲▲ ---

        # --- 配役ごとの Appearance 設定 UI ---
        self.assignment_group = QGroupBox("配役ごとの見た目設定")
        assignment_scroll_content = QWidget()
        self.assignment_layout = QVBoxLayout(assignment_scroll_content)
        assignment_scroll = QScrollArea()
        assignment_scroll.setWidgetResizable(True)
        assignment_scroll.setWidget(assignment_scroll_content)
        assignment_scroll.setMinimumHeight(200)

        group_layout = QVBoxLayout(self.assignment_group)
        group_layout.addWidget(assignment_scroll)
        self.form_layout.addRow(self.assignment_group)

        # --- State Category UI ---
        self.form_layout.addRow(QLabel("--- 状態カテゴリ (State Categories) ---"))
        self.selected_categories_list = QListWidget()
        self.selected_categories_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )  # 選択モード
        # ダブルクリックで削除する機能は削除 (ボタンを使う)
        self._populate_category_list()  # 初期リスト表示

        category_btn_layout = QHBoxLayout()
        add_category_btn = QPushButton("＋ カテゴリを選択...")
        remove_category_btn = QPushButton("－ 選択したカテゴリを削除")
        add_category_btn.clicked.connect(self._add_category_dialog)
        remove_category_btn.clicked.connect(self._remove_selected_category)
        category_btn_layout.addWidget(add_category_btn)
        category_btn_layout.addWidget(remove_category_btn)
        category_btn_layout.addStretch()

        self.form_layout.addRow(self.selected_categories_list)
        self.form_layout.addRow(category_btn_layout)

        # --- Additional Prompt UI ---
        self.form_layout.addRow(QLabel("--- 追加プロンプト (Additional Prompts) ---"))
        self.selected_ap_list = QListWidget()
        self.selected_ap_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )  # 選択モード
        self.selected_ap_list.itemDoubleClicked.connect(
            self._handle_ap_double_clicked
        )  # ダブルクリックで編集
        self._populate_ap_list()  # 初期リスト表示

        ap_btn_layout = QHBoxLayout()
        add_ap_btn = QPushButton("＋ APを選択...")
        add_new_ap_btn = QPushButton("＋ 新規APを作成")
        remove_ap_btn = QPushButton("－ 選択したAPを削除")
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
        # 参照ウィジェット (background_id など) は _reference_widgets に自動登録される

        # --- 初期 Appearance UI の構築 ---
        initial_cut_id = getattr(self.initial_data, "cut_id", None)
        initial_cut = (
            self.db_dict.get("cuts", {}).get(initial_cut_id) if initial_cut_id else None
        )
        self._update_appearance_assignment_ui(initial_cut)

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
        """Cut コンボボックスの選択が変更されたら、Appearance UIを更新"""
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
        # ▼▼▼ 新しいUI更新メソッドを呼び出す ▼▼▼
        self._update_appearance_assignment_ui(selected_cut)
        # ▲▲▲ 変更 ▲▲▲

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

    def _update_appearance_assignment_ui(self, selected_cut: Optional[Cut]):
        """選択された Cut の Roles に基づいて Appearance 割り当てUIを構築"""
        # 古いUIをクリア
        while self.assignment_layout.count():
            item = self.assignment_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not selected_cut or not selected_cut.roles:
            self.assignment_layout.addWidget(
                QLabel("(カットを選択するか、カットに配役を追加してください)")
            )
            # Cut がない場合、既存の current_role_assignments をどうするか？
            # - クリアする
            # - そのまま保持する (Cut を戻した時に復元されるように)
            # ここでは保持する方針とする
            return

        valid_role_ids_in_cut = {role.id for role in selected_cut.roles if role.id}

        # --- Cut の Role ごとにウィジェットを作成 ---
        for role in selected_cut.roles:
            if not role.id:
                continue

            # 対応する RoleAppearanceAssignment を探す (なければ新規作成)
            assignment = next(
                (ra for ra in self.current_role_assignments if ra.role_id == role.id),
                None,
            )
            if assignment is None:
                assignment = RoleAppearanceAssignment(role_id=role.id)
                self.current_role_assignments.append(assignment)

            # RoleAssignmentWidget を作成してレイアウトに追加
            role_widget = RoleAssignmentWidget(role, assignment, self.db_dict, self)
            # シグナルを接続 (外部エディタを開くリクエストを中継)
            role_widget.request_add_new.connect(self._handle_request_add_new_appearance)
            role_widget.request_edit_item.connect(self._handle_request_edit_appearance)
            role_widget.assignment_changed.connect(self._mark_data_changed)

            self.assignment_layout.addWidget(role_widget)

        # --- Cut に存在しなくなった Role の Assignment を current から削除 ---
        original_assignment_count = len(self.current_role_assignments)
        self.current_role_assignments = [
            ra
            for ra in self.current_role_assignments
            if ra.role_id in valid_role_ids_in_cut
        ]
        if len(self.current_role_assignments) != original_assignment_count:
            self._mark_data_changed()  # ★ 削除されたら変更フラグを立てる
        self.assignment_layout.addStretch()  # 最後にスペーサーを追加

    @Slot(str, str)
    def _handle_request_add_new_appearance(self, modal_type: str, role_id: str):
        """RoleAssignmentWidget からの新規作成リクエスト"""
        print(
            f"[DEBUG] SceneEditorDialog relaying request for new {modal_type} (for role {role_id})"
        )
        # target_widget として RoleAssignmentWidget を渡すことも可能だが、
        # update_combo_box_after_edit で db_key が分かれば十分
        self.request_open_editor.emit(modal_type, None, None)

    @Slot(str, str)
    def _handle_request_edit_appearance(self, modal_type: str, item_id: str):
        """RoleAssignmentWidget からの編集リクエスト"""
        db_key_map = {
            "COSTUME": "costumes",
            "POSE": "poses",
            "EXPRESSION": "expressions",
        }
        db_key = db_key_map.get(modal_type)
        if not db_key:
            return

        item_data = self.db_dict.get(db_key, {}).get(item_id)
        if item_data:
            print(
                f"[DEBUG] SceneEditorDialog relaying request to edit {modal_type} {item_id}"
            )
            self.request_open_editor.emit(modal_type, item_data, None)
        else:
            QMessageBox.warning(
                self, "Error", f"Data not found for {modal_type} ID: {item_id}"
            )

    @Slot(QWidget, str, str)
    def update_combo_box_after_edit(
        self, target_widget: QWidget, db_key: str, select_id: Optional[str]
    ):
        """ネストしたダイアログでの編集/追加後にリストやコンボボックスを更新"""
        # --- ▼▼▼ Appearance (Costume, Pose, Expression) 更新時の処理 ▼▼▼ ---
        if db_key in ["costumes", "poses", "expressions"]:
            print(
                f"[DEBUG] SceneEditorDialog detected {db_key} change. Refreshing RoleAssignmentWidgets."
            )
            # 影響を受ける可能性のあるすべての RoleAssignmentWidget のリストを更新
            for i in range(self.assignment_layout.count()):
                widget = self.assignment_layout.itemAt(i).widget()
                if isinstance(widget, RoleAssignmentWidget):
                    widget.refresh_list(db_key)
            # 選択ダイアログ (GenericSelectionDialog) は db_dict を参照するため、
            # 次回開いたときには自動的に更新後のリストが表示される
        # --- ▲▲▲ 修正 ▲▲▲ ---
        elif db_key == "cuts":  # Cut 更新時 (変更なし)
            cut_combo_box = self._reference_widgets.get("cut_id", {}).get("combo")
            if target_widget == cut_combo_box:  # Cut 参照ウィジェット自身の更新
                super().update_combo_box_after_edit(target_widget, db_key, select_id)
                selected_cut = (
                    self.db_dict.get("cuts", {}).get(select_id) if select_id else None
                )
                self._update_appearance_assignment_ui(
                    selected_cut
                )  # ★ UI 更新メソッド呼び出し
            else:  # 他のダイアログから Cut が編集された場合 (通常は発生しない想定)
                super().update_combo_box_after_edit(target_widget, db_key, select_id)
        elif db_key == "states":  # State 更新時 (変更なし)
            print(
                "[DEBUG] SceneEditorDialog detected State change. Repopulating category lists."
            )
            self._populate_category_list()
        elif db_key == "additional_prompts":  # AP 更新時 (変更なし)
            print(
                "[DEBUG] SceneEditorDialog detected Additional Prompt change. Repopulating AP list."
            )
            self._populate_ap_list()
        else:  # Background, Style などの参照ウィジェット更新 (変更なし)
            super().update_combo_box_after_edit(target_widget, db_key, select_id)

    def get_data(self) -> Optional[Scene]:
        try:
            name = self.name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, "入力エラー", "名前は必須です。")
                return None

            bg_id = self._get_widget_value("background_id")
            light_id = self._get_widget_value("lighting_id")
            comp_id = self._get_widget_value("composition_id")
            style_id = self._get_widget_value("style_id")
            sd_param_id = self._get_widget_value("sd_param_id")
            cut_id = self._get_widget_value("cut_id")

            state_categories = sorted(self.current_state_categories)
            additional_prompt_ids = self.current_additional_prompt_ids

            # --- ▼▼▼ RoleAssignmentWidget から最新のデータを収集 ▼▼▼ ---
            current_role_assignments_from_widgets: List[RoleAppearanceAssignment] = []
            for i in range(self.assignment_layout.count()):
                widget_item = self.assignment_layout.itemAt(i)
                if widget_item:
                    widget = widget_item.widget()
                    if isinstance(widget, RoleAssignmentWidget):
                        # 各ウィジェットから最新のデータを取得
                        current_role_assignments_from_widgets.append(
                            widget.get_assignment_data()
                        )
            # --- ▲▲▲ 修正ここまで ▲▲▲ ---

            # --- ▼▼▼ 収集した最新データでバリデーションと設定 ▼▼▼ ---
            selected_cut = self.db_dict.get("cuts", {}).get(cut_id) if cut_id else None
            valid_role_ids_in_cut = (
                {role.id for role in selected_cut.roles if role.id}
                if selected_cut
                else set()
            )
            # 収集したデータの中から、現在のCutに存在するRoleのものだけを抽出
            valid_role_assignments = [
                ra
                for ra in current_role_assignments_from_widgets  # ★ 変更
                if ra.role_id in valid_role_ids_in_cut
            ]
            # --- ▲▲▲ 修正ここまで ▲▲▲ ---

            if self.initial_data:
                updated_scene = self.initial_data
                # --- ▼▼▼ _update_object_from_widgets は name, tags のみ更新 ▼▼▼ ---
                # self._update_object_from_widgets(updated_scene) # <- これだと参照IDまで上書きしようとする
                updated_scene.name = name
                updated_scene.tags = [
                    t.strip() for t in self.tags_edit.text().split(",") if t.strip()
                ]
                # 属性を直接更新
                updated_scene.background_id = bg_id or ""
                updated_scene.lighting_id = light_id or ""
                updated_scene.composition_id = comp_id or ""
                updated_scene.style_id = style_id
                updated_scene.sd_param_id = sd_param_id
                updated_scene.cut_id = cut_id
                updated_scene.role_assignments = valid_role_assignments  # ★ 更新
                updated_scene.state_categories = state_categories
                updated_scene.additional_prompt_ids = additional_prompt_ids
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
                    role_assignments=valid_role_assignments,  # ★ 設定
                    style_id=style_id,
                    sd_param_id=sd_param_id,
                    state_categories=state_categories,
                    additional_prompt_ids=additional_prompt_ids,
                )
                print(f"[DEBUG] Returning new scene: {new_scene}")
                return new_scene
        except Exception as e:
            print(f"[ERROR] Exception in SceneEditorDialog.get_data: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self, "Error", f"An error occurred while getting data: {e}"
            )
            return None
