# src/widgets/costume_editor_dialog.py
import time
import json
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QTextEdit,
    QMessageBox,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QComboBox,
    QFormLayout,
    QListWidgetItem,  # ★ 追加
    QAbstractItemView,
    QListWidget,
    QWidget,
    QHBoxLayout,
    QPushButton,
    QDialog,
)
from PySide6.QtCore import Slot, Qt
from typing import Optional, Any, Dict, List, Tuple

from .base_editor_dialog import BaseEditorDialog
from ..models import Costume, ColorPaletteItem, State
from .generic_selection_dialog import GenericSelectionDialog

# Character クラスの属性名と表示名の対応
CHARACTER_COLOR_REFS = {
    "personal_color": "パーソナルカラー",
    "underwear_color": "下着カラー",
}


class CostumeEditorDialog(BaseEditorDialog):
    def __init__(
        self, initial_data: Optional[Costume], db_dict: Dict, db_key: str, parent=None
    ):
        # 内部状態 (カラーパレット編集用) - super().__init__ より先に初期化
        self.current_palette_items: List[ColorPaletteItem] = []
        # initial_data は super() より前で参照可能
        if initial_data and hasattr(initial_data, "color_palette"):
            # Deep copy
            self.current_palette_items = [
                ColorPaletteItem(**item.__dict__) for item in initial_data.color_palette
            ]
        # ▼▼▼ current_state_ids を初期化 ▼▼▼
        self.current_state_ids: List[str] = []
        if initial_data and hasattr(initial_data, "state_ids"):
            # Deep copy (文字列リストなので単純コピーでOK)
            self.current_state_ids = list(initial_data.state_ids)

        super().__init__(initial_data, db_dict, db_key, "Costume", parent)

        # UI構築
        # _populate_fields は基底クラスの __init__ から呼ばれる

    def _populate_fields(self):
        self.form_layout = self.setup_form_layout()  # 基底クラスのヘルパーを呼び出す
        if not self.form_layout:
            return  # エラー処理 (念のため)
        """UI要素を作成し、配置します。"""
        # --- Common fields (BaseInspector のロジックを流用) ---
        name_edit = QLineEdit(getattr(self.initial_data, "name", ""))
        tags_edit = QLineEdit(", ".join(getattr(self.initial_data, "tags", [])))
        prompt_edit = QTextEdit()
        prompt_edit.setPlainText(getattr(self.initial_data, "prompt", ""))  # ★ 変更
        prompt_edit.setFixedHeight(60)

        neg_prompt_edit = QTextEdit()
        neg_prompt_edit.setPlainText(
            getattr(self.initial_data, "negative_prompt", "")
        )  # ★ 変更
        neg_prompt_edit.setFixedHeight(60)

        # 基底クラスの form_layout を使用
        self.form_layout.addRow("Name:", name_edit)
        self.form_layout.addRow("Tags:", tags_edit)
        self.form_layout.addRow("Prompt:", prompt_edit)
        self.form_layout.addRow("Negative Prompt:", neg_prompt_edit)

        # _widgets に登録
        self._widgets["name"] = name_edit
        self._widgets["tags"] = tags_edit
        self._widgets["prompt"] = prompt_edit
        self._widgets["negative_prompt"] = neg_prompt_edit

        # --- Color Palette Editor (CostumeInspector のロジックを流用) ---
        self.form_layout.addRow(QLabel("--- Color Palette ---"))
        # color_palette リストの各項目を表示・編集するUIを動的に生成
        self.palette_widgets: List[Dict[str, QWidget]] = []  # 各行のウィジェットを保持
        self.palette_layout = QVBoxLayout()  # パレット項目用のレイアウト

        # UIを current_palette_items から構築
        for index, item in enumerate(self.current_palette_items):
            self._add_palette_row_ui(item, index)

        add_palette_button = QPushButton("＋ Add Palette Item")
        add_palette_button.clicked.connect(self._add_new_palette_item_ui)

        # QFormLayout に QVBoxLayout を追加するためのコンテナ
        palette_container = QWidget()
        palette_container.setLayout(self.palette_layout)
        self.form_layout.addRow(palette_container)
        self.form_layout.addRow(add_palette_button)
        # color_palette 自体は _widgets には含めず、get_data で特別に処理する

        # --- ▼▼▼ State ID リスト管理 UI を修正 ▼▼▼ ---
        self.form_layout.addRow(QLabel("--- 状態 (States) ---"))
        self.state_list_widget = QListWidget()
        self.state_list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.state_list_widget.itemDoubleClicked.connect(
            self._handle_state_double_clicked
        )
        self._populate_state_list()

        # --- ボタン用のウィジェットとレイアウトを作成 ---
        state_buttons_widget = QWidget()
        state_btn_layout = QHBoxLayout(state_buttons_widget)
        state_btn_layout.setContentsMargins(0, 0, 0, 0)  # マージン削除

        add_state_btn = QPushButton("＋ 状態を選択...")  # ボタンテキスト変更
        # ▼▼▼ 新規作成ボタンを追加 ▼▼▼
        add_new_state_btn = QPushButton("＋ 新規状態を作成")
        # ▲▲▲ 追加ここまで ▲▲▲
        remove_state_btn = QPushButton("－ 選択した状態を削除")

        add_state_btn.clicked.connect(self._open_state_selection_dialog)
        # ▼▼▼ 新規作成ボタンのシグナル接続 ▼▼▼
        add_new_state_btn.clicked.connect(self._handle_add_new_state)
        # ▲▲▲ 追加ここまで ▲▲▲
        remove_state_btn.clicked.connect(self._remove_selected_state)

        state_btn_layout.addWidget(add_state_btn)
        state_btn_layout.addWidget(add_new_state_btn)  # ボタンをレイアウトに追加
        state_btn_layout.addWidget(remove_state_btn)
        state_btn_layout.addStretch()

        self.form_layout.addRow(self.state_list_widget)
        self.form_layout.addRow(state_buttons_widget)  # ボタン用ウィジェットを配置

    @Slot()
    def _handle_add_new_state(self):
        """「＋ 新規状態を作成」ボタンが押されたときの処理"""
        print("[DEBUG] Requesting editor for new STATE from CostumeEditorDialog")
        # BaseEditorDialog の request_open_editor シグナルを発行
        # target_widget は None (更新は update_combo_box_after_edit で処理)
        self.request_open_editor.emit("STATE", None, None)

    @Slot(QListWidgetItem)
    def _handle_state_double_clicked(self, item: QListWidgetItem):
        """State リストの項目がダブルクリックされたときの処理"""
        state_id = item.data(Qt.ItemDataRole.UserRole)
        state_data = self.db_dict.get("states", {}).get(state_id)
        if state_data:
            print(
                f"[DEBUG] Requesting editor for STATE {state_id} from CostumeEditorDialog"
            )
            # target_widget は None (更新は update_combo_box_after_edit で処理)
            self.request_open_editor.emit("STATE", state_data, None)
        else:
            QMessageBox.warning(
                self, "Error", f"Could not find State data for ID: {state_id}"
            )

    @Slot(QWidget, str, str)
    def update_combo_box_after_edit(
        self, target_widget: QWidget, db_key: str, select_id: Optional[str]
    ):
        """ネストしたダイアログでの編集/追加後にリストやコンボボックスを更新"""
        # ★ State が追加/編集された場合の処理を追加
        if db_key == "states":
            print(
                f"[DEBUG] CostumeEditorDialog detected State change (new/edit ID: {select_id}). Repopulating list."
            )
            # --- ▼▼▼ State 編集後にリストを再描画 ▼▼▼ ---
            # db_dict は MainWindow で更新されているはずなので、それを元にリストを再描画
            self._populate_state_list()
            # --- ▲▲▲ 追加ここまで ▲▲▲ ---
            # StateSelectionDialog は DB から直接読むので ComboBox 更新は不要
            pass
        else:
            # 他の参照ウィジェット (Costume, Pose, Expression) の更新は基底クラスに任せる
            super().update_combo_box_after_edit(target_widget, db_key, select_id)

    # --- ▼▼▼ State リスト関連メソッドを追加 ▼▼▼ ---
    def _populate_state_list(self):
        """State ID リストウィジェットの内容を更新"""
        self.state_list_widget.clear()
        all_states = self.db_dict.get("states", {})
        # ▼▼▼ current_state_ids の順番を保持するように修正 ▼▼▼
        current_id_order = {
            state_id: i for i, state_id in enumerate(self.current_state_ids)
        }
        sorted_ids = sorted(
            self.current_state_ids,
            key=lambda state_id: current_id_order.get(state_id, float("inf")),
        )

        for state_id in sorted_ids:  # ★ ソート済みのリストを使用
            state = all_states.get(state_id)
            item_text = f"State ID not found: {state_id}"
            if state:
                item_text = f"{getattr(state, 'name', 'N/A')} [{getattr(state, 'category', 'N/A')}] ({state_id})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, state_id)
            self.state_list_widget.addItem(item)

    @Slot()
    def _open_state_selection_dialog(self):
        """State 選択ダイアログを開く"""
        all_states = self.db_dict.get("states", {})
        if not all_states:  # ... (メッセージ表示) ...
            return
        available_states = {
            s_id: s
            for s_id, s in all_states.items()
            if s_id not in self.current_state_ids
        }
        if not available_states:  # ... (メッセージ表示) ...
            return

        # --- ▼▼▼ GenericSelectionDialog を使用 ▼▼▼ ---
        # State オブジェクトを表示するための関数
        def display_state(state: State) -> str:
            return f"{getattr(state, 'name', 'N/A')} [{getattr(state, 'category', 'N/A')}] ({getattr(state, 'id', 'N/A')})"

        # ソート用の関数 (カテゴリ -> 名前)
        def sort_state_key(item: Tuple[str, State]) -> Tuple[str, str]:
            state = item[1]
            return (
                getattr(state, "category", "").lower(),
                getattr(state, "name", "").lower(),
            )

        dialog = GenericSelectionDialog(
            items_data=available_states,
            display_func=display_state,
            window_title="Select State to Add",
            filter_placeholder="Filter by name, category, or ID...",
            sort_key_func=sort_state_key,  # ソート関数を指定
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_id = dialog.get_selected_item_id()  # ★ メソッド名変更
            if selected_id and selected_id not in self.current_state_ids:
                self.current_state_ids.append(selected_id)
                self._populate_state_list()
                self._mark_data_changed()

    @Slot()
    def _remove_selected_state(self):
        """選択された State ID をリストから削除"""
        selected_items = self.state_list_widget.selectedItems()
        if not selected_items:
            return
        selected_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
        if selected_id in self.current_state_ids:
            self.current_state_ids.remove(selected_id)
            self._populate_state_list()
            self._mark_data_changed()

    # --- _add_palette_row_ui, _add_new_palette_item_ui,
    # --- _remove_palette_item_ui, _update_palette_row_labels は
    # --- costume_inspector.py からほぼそのまま移植 ---
    # (省略 - 上記の src/inspectors/costume_inspector.py 修正案と同じコード)
    def _add_palette_row_ui(self, item: ColorPaletteItem, index: int):
        """カラーパレットの1行分のUIを作成してレイアウトに追加します。"""
        row_layout = QHBoxLayout()
        placeholder_edit = QLineEdit(item.placeholder)
        placeholder_edit.setPlaceholderText("[C1]")
        color_ref_combo = QComboBox()

        ref_display_names = list(CHARACTER_COLOR_REFS.values())  # 表示名リスト
        ref_internal_names = list(
            CHARACTER_COLOR_REFS.keys()
        )  # 内部値 (属性文字列) リスト
        color_ref_combo.addItems(ref_display_names)
        try:
            current_ref_value = item.color_ref  # 文字列のはず
            display_name = CHARACTER_COLOR_REFS.get(
                current_ref_value, ref_display_names[0]
            )  # 見つからなければ先頭
            combo_index = ref_display_names.index(display_name)
            color_ref_combo.setCurrentIndex(combo_index)
        except (ValueError, IndexError):
            color_ref_combo.setCurrentIndex(0)

        remove_button = QPushButton("🗑️")

        row_layout.addWidget(QLabel(f"{index + 1}:"))
        row_layout.addWidget(placeholder_edit)
        row_layout.addWidget(QLabel("uses"))
        row_layout.addWidget(color_ref_combo)
        row_layout.addWidget(remove_button)

        self.palette_layout.addLayout(row_layout)

        row_widgets = {
            "index": index,
            "placeholder": placeholder_edit,
            "color_ref": color_ref_combo,
            "remove_button": remove_button,
            "layout": row_layout,
            "_internal_names": ref_internal_names,  # 選択肢の内部名を保持
        }
        remove_button.clicked.connect(
            lambda checked=False, widgets=row_widgets: self._remove_palette_item_ui(
                widgets
            )
        )
        self.palette_widgets.append(row_widgets)

    @Slot()
    def _add_new_palette_item_ui(self):
        """新しいカラーパレット項目を追加するためのUI行を生成します。"""
        new_index = len(self.palette_widgets)
        default_item = ColorPaletteItem(
            placeholder=f"[C{new_index + 1}]",
            color_ref=list(CHARACTER_COLOR_REFS.keys())[0],  # 最初の属性文字列
        )
        # current_palette_items にも追加しておく (get_data で使う場合があるため)
        self.current_palette_items.append(default_item)
        self._add_palette_row_ui(default_item, new_index)
        self._update_palette_row_labels()  # ラベル更新

    def _remove_palette_item_ui(self, widgets_to_remove: Dict[str, Any]):
        """指定されたカラーパレット項目のUI行を削除します。"""
        layout_to_remove = widgets_to_remove.get("layout")
        if not layout_to_remove:
            return

        # レイアウト内のウィジェットを削除
        while layout_to_remove.count():
            item = layout_to_remove.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # レイアウト自体を削除
        self.palette_layout.removeItem(layout_to_remove)
        layout_to_remove.deleteLater()

        # palette_widgets リストから該当する辞書を削除
        original_index = widgets_to_remove.get("index", -1)
        self.palette_widgets = [
            w for w in self.palette_widgets if w != widgets_to_remove
        ]

        # current_palette_items からも削除 (インデックスで)
        if 0 <= original_index < len(self.current_palette_items):
            self.current_palette_items.pop(original_index)

        # 残りの行のラベル番号などを更新
        self._update_palette_row_labels()

    def _update_palette_row_labels(self):
        """パレット行のインデックス表示と内部インデックスを更新します。"""
        for i, row_widgets in enumerate(self.palette_widgets):
            layout = row_widgets.get("layout")
            if layout:
                label_widget = layout.itemAt(0).widget()
                if isinstance(label_widget, QLabel):
                    label_widget.setText(f"{i + 1}:")
            row_widgets["index"] = i  # 内部インデックスも更新

    def get_data(self) -> Optional[Costume]:
        """UIからデータを取得し、Costumeオブジェクトを生成または更新して返します。"""
        # --- 基本属性のバリデーションと取得 ---
        name = self._widgets["name"].text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "Name は必須です。")
            return None

        # --- カラーパレット情報の取得とバリデーション ---
        new_palette_list: List[ColorPaletteItem] = []
        placeholders_seen = set()
        try:
            for i, row_widgets in enumerate(self.palette_widgets):
                placeholder_widget = row_widgets.get("placeholder")
                color_ref_widget = row_widgets.get("color_ref")
                internal_names = row_widgets.get(
                    "_internal_names"
                )  # 保存しておいた内部名リスト

                if (
                    isinstance(placeholder_widget, QLineEdit)
                    and isinstance(color_ref_widget, QComboBox)
                    and internal_names
                ):
                    placeholder = placeholder_widget.text().strip()
                    combo_index = color_ref_widget.currentIndex()
                    color_ref_value = (
                        internal_names[combo_index]
                        if 0 <= combo_index < len(internal_names)
                        else None
                    )

                    row_num = i + 1  # エラー表示用

                    if not placeholder:
                        raise ValueError(f"プレイスホルダーが空です (行 {row_num})。")
                    if not placeholder.startswith("[") or not placeholder.endswith("]"):
                        raise ValueError(
                            f"プレイスホルダー「{placeholder}」は角括弧 [...] で囲んでください (行 {row_num})。"
                        )
                    if placeholder in placeholders_seen:
                        raise ValueError(
                            f"プレイスホルダー「{placeholder}」が重複しています (行 {row_num})。"
                        )
                    if color_ref_value is None:
                        raise ValueError(
                            f"無効なカラー参照が選択されています (行 {row_num})。"
                        )

                    placeholders_seen.add(placeholder)
                    new_palette_list.append(
                        ColorPaletteItem(
                            placeholder=placeholder, color_ref=color_ref_value
                        )
                    )
            # --- バリデーションここまで ---

        except ValueError as ve:
            QMessageBox.warning(self, "入力エラー", f"カラーパレット: {ve}")
            return None
        except Exception as e:
            QMessageBox.critical(self, "Error", f"カラーパレット処理エラー: {e}")
            return None

        # --- オブジェクトの生成または更新 ---
        if self.initial_data:  # 更新
            updated_costume = self.initial_data
            # 基底クラスのヘルパーで基本属性更新
            self._update_object_from_widgets(updated_costume)
            # パレットはここで直接セット
            updated_costume.color_palette = new_palette_list
            updated_costume.state_ids = self.current_state_ids
            return updated_costume
        else:  # 新規作成
            tags_text = self._widgets["tags"].text()
            prompt_text = self._widgets["prompt"].toPlainText().strip()
            neg_prompt_text = self._widgets["negative_prompt"].toPlainText().strip()
            new_costume = Costume(
                id=f"costume_{int(time.time())}",
                name=name,
                tags=[t.strip() for t in tags_text.split(",") if t.strip()],
                prompt=prompt_text,
                negative_prompt=neg_prompt_text,
                color_palette=new_palette_list,
                state_ids=self.current_state_ids,
            )
            return new_costume
