# src/widgets/base_editor_dialog.py
import time
import json
import traceback
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QDialogButtonBox,
    QWidget,
    QFormLayout,
    QMessageBox,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QPushButton,
    QScrollArea,
    QHBoxLayout,
)
from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtGui import QIcon  # (未使用だがインポートが残っていても問題ない)
from typing import Optional, Dict, Any, Type, TypeVar, List, Tuple


# Helper function to find combo box by field name in layout
def _find_combo_box(layout: QFormLayout, field_name: str) -> Optional[QComboBox]:
    """Helper function to find a QComboBox associated with a field name."""
    for i in range(layout.rowCount()):
        label_item = layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
        widget_item = layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
        if label_item and widget_item:
            label_widget = label_item.widget()
            field_widget = widget_item.widget()
            # Assuming the label text corresponds to the field_name or similar logic
            # This needs a more robust way to associate label/widget with field_name if label text differs
            # For reference widgets, we rely on _reference_widgets instead
    return None  # Simplified, actual lookup needs implementation if used


T = TypeVar("T")


class BaseEditorDialog(QDialog):
    request_open_editor = Signal(
        str, object, QWidget
    )  # modal_type, initial_data, target_widget

    def __init__(
        self,
        initial_data: Optional[Any],
        db_dict: Dict[str, Dict],
        title_prefix: str,
        parent=None,
    ):
        super().__init__(parent)
        self.initial_data = initial_data
        self.db_dict = db_dict
        self.title_prefix = title_prefix
        self.saved_data: Optional[Any] = None
        self._widgets: Dict[str, QWidget] = {}
        self._reference_widgets: Dict[str, Dict[str, QWidget]] = {}
        self._data_changed = False
        self._nested_editors: Dict[QWidget, BaseEditorDialog] = {}

        self.setWindowTitle(
            f"{self.title_prefix} - {'編集' if initial_data else '新規作成'}"
        )
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self.resize(600, 500)

        # --- ▼▼▼ メインレイアウトとスクロールエリアの設定 ▼▼▼ ---
        self.main_layout = QVBoxLayout(self)

        # スクロールエリアを作成して self.scroll_area に代入
        self.scroll_area = QScrollArea(self)  # ★ 先に作成・代入
        self.scroll_area.setWidgetResizable(True)  # ★ 次に設定
        self.main_layout.addWidget(self.scroll_area)

        # フォームレイアウト用のウィジェットを作成し、スクロールエリアに設定
        self.form_widget = QWidget()
        self.scroll_area.setWidget(self.form_widget)
        # --- ▲▲▲ 修正ここまで ▲▲▲ ---

        # Save/Cancel Buttons (変更なし)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._save_and_accept)
        self.button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(self.button_box)

        # Save ボタンを最初は無効化 (変更なし)
        self.save_button = self.button_box.button(QDialogButtonBox.StandardButton.Save)
        if self.save_button:
            self.save_button.setEnabled(False)

        # サブクラスでフィールドを構築 (変更なし)
        self._populate_fields()

        # ウィジェット変更時にフラグを立てるシグナル接続 (変更なし)
        self._connect_change_signals()

    def setup_form_layout(self) -> QFormLayout:
        """
        QFormLayout を self.form_widget にセットアップし、それを返します。
        (変更なし)
        """
        layout = QFormLayout(self.form_widget)  # 親を self.form_widget に設定
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        return layout

    def _populate_fields(self):
        """サブクラスでUI要素を作成し配置する (変更なし)"""
        raise NotImplementedError("サブクラスで _populate_fields を実装してください。")

    def _connect_change_signals(self):
        """_widgets 及び _reference_widgets 内のウィジェットの変更シグナルを _mark_data_changed に接続 (変更なし)"""
        for widget in self._widgets.values():
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._mark_data_changed)
            elif isinstance(widget, QTextEdit):
                widget.textChanged.connect(self._mark_data_changed)
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._mark_data_changed)
        for ref_info in self._reference_widgets.values():
            combo_widget = ref_info.get("combo")
            if isinstance(combo_widget, QComboBox):
                combo_widget.currentIndexChanged.connect(self._mark_data_changed)

    @Slot()
    def _mark_data_changed(self):
        """データが変更されたことをマークし、Saveボタンを有効化 (変更なし)"""
        if not self._data_changed:
            self._data_changed = True
            print("[DEBUG] Data changed, enabling Save button.")
            if self.save_button:
                self.save_button.setEnabled(True)

    def get_data(self) -> Optional[Any]:
        """サブクラスでUIからデータを取得し、オブジェクトを返す (変更なし)"""
        raise NotImplementedError("サブクラスで get_data を実装してください。")

    @Slot()
    def _save_and_accept(self):
        """Saveボタンが押されたときの処理 (変更なし)"""
        print("[DEBUG] Save button clicked.")
        try:
            data = self.get_data()
            if data:
                self.saved_data = data
                print(
                    f"[DEBUG] get_data returned valid data: {getattr(data, 'id', 'N/A')}"
                )
                super().accept()
            else:
                print("[DEBUG] get_data returned None. Dialog remains open.")
        except Exception as e:
            QMessageBox.critical(
                self, "エラー", f"保存処理中にエラーが発生しました: {e}"
            )
            print(f"[ERROR] Exception during _save_and_accept -> get_data: {e}")
            traceback.print_exc()

    def _get_widget_value(self, key: str) -> Optional[Any]:
        """_widgets または _reference_widgets から値を取得 (変更なし)"""
        if key in self._widgets:
            widget = self._widgets[key]
            if isinstance(widget, QLineEdit):
                return widget.text().strip()
            elif isinstance(widget, QTextEdit):
                return widget.toPlainText().strip()
            elif isinstance(widget, QComboBox):
                return widget.currentData() or widget.currentText()
        elif key in self._reference_widgets:
            combo = self._reference_widgets[key].get("combo")
            if isinstance(combo, QComboBox):
                return combo.currentData()
        print(f"[WARN] Widget/Reference not found for key: {key}")
        return None

    def _update_object_from_widgets(self, obj: Any) -> bool:
        """_widgets の内容でオブジェクトの属性を更新 (変更なし)"""
        try:
            for key, widget in self._widgets.items():
                if not hasattr(obj, key):
                    continue
                value = None
                if isinstance(widget, QLineEdit):
                    value = widget.text().strip()
                    if key == "tags":
                        value = [t.strip() for t in value.split(",") if t.strip()]
                elif isinstance(widget, QTextEdit):
                    value = widget.toPlainText().strip()
                elif isinstance(widget, QComboBox):
                    value = (
                        widget.currentData()
                        if widget.currentData() is not None
                        else widget.currentText()
                    )
                if value is not None:
                    setattr(obj, key, value)
            return True
        except Exception as e:
            QMessageBox.critical(
                self, "更新エラー", f"データの更新中にエラーが発生しました: {e}"
            )
            print(f"[ERROR] Exception during _update_object_from_widgets: {e}")
            traceback.print_exc()
            return False

    def _create_reference_editor_widget(
        self,
        field_name: str,
        current_id: Optional[str],
        reference_db_key: str,
        reference_modal_type: str,
        allow_none: bool = False,
        none_text: str = "(なし)",
        display_attr: str = "name",
    ) -> QWidget:
        """
        参照選択用の ComboBox と編集/追加ボタンを持つウィジェットを作成 (変更なし)
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        combo = QComboBox()
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        layout.addWidget(combo, 1)

        if field_name not in self._reference_widgets:
            self._reference_widgets[field_name] = {}
        self._reference_widgets[field_name].update(
            {
                "combo": combo,
                "db_key": reference_db_key,
                "modal_type": reference_modal_type,
                "allow_none": allow_none,
                "none_text": none_text,
                "display_attr": display_attr,
            }
        )
        self._update_reference_combo(field_name, current_id)

        edit_btn = QPushButton("✎")
        edit_btn.setToolTip(f"Edit selected {reference_modal_type}")
        edit_btn.setEnabled(bool(current_id))
        edit_btn.clicked.connect(lambda: self._edit_reference(field_name))
        layout.addWidget(edit_btn)
        self._reference_widgets[field_name]["edit_btn"] = edit_btn

        add_btn = QPushButton("＋")
        add_btn.setToolTip(f"Add new {reference_modal_type}")
        add_btn.clicked.connect(lambda: self._add_reference(field_name))
        layout.addWidget(add_btn)

        combo.currentIndexChanged.connect(
            lambda index, btn=edit_btn, f_name=field_name: self._toggle_edit_button(
                index, btn, f_name
            )
        )
        return widget

    def _update_reference_combo(self, field_name: str, select_id: Optional[str]):
        """指定された参照コンボボックスの内容を更新し、指定IDを選択状態にする (変更なし)"""
        ref_info = self._reference_widgets.get(field_name)
        if not ref_info or not isinstance(ref_info.get("combo"), QComboBox):
            return
        combo: QComboBox = ref_info["combo"]
        db_key = ref_info["db_key"]
        allow_none = ref_info["allow_none"]
        none_text = ref_info["none_text"]
        display_attr = ref_info["display_attr"]
        items_dict = self.db_dict.get(db_key, {})

        combo.blockSignals(True)
        combo.clear()
        current_index = -1
        if allow_none:
            combo.addItem(none_text, None)
            if select_id is None:
                current_index = 0
        sorted_items = sorted(
            items_dict.values(),
            key=lambda x: getattr(x, display_attr, getattr(x, "id", "")).lower(),
        )
        for i, item in enumerate(sorted_items):
            item_id = getattr(item, "id", None)
            display_name = getattr(item, display_attr, item_id or "(No Name/ID)")
            combo.addItem(f"{display_name} ({item_id})", item_id)
            if item_id and item_id == select_id:
                current_index = i + (1 if allow_none else 0)
        combo.setCurrentIndex(current_index)
        combo.blockSignals(False)
        edit_btn = ref_info.get("edit_btn")
        if edit_btn:
            edit_btn.setEnabled(bool(combo.currentData()))

    @Slot()
    def _edit_reference(self, field_name: str):
        """参照項目の編集ボタンが押されたときの処理 (変更なし)"""
        ref_info = self._reference_widgets.get(field_name)
        if not ref_info or not isinstance(ref_info.get("combo"), QComboBox):
            return
        combo: QComboBox = ref_info["combo"]
        selected_id = combo.currentData()
        db_key = ref_info["db_key"]
        modal_type = ref_info["modal_type"]
        if selected_id:
            item_data = self.db_dict.get(db_key, {}).get(selected_id)
            if item_data:
                self.request_open_editor.emit(modal_type, item_data, combo)
            else:
                QMessageBox.warning(
                    self, "エラー", f"ID '{selected_id}' のデータが見つかりません。"
                )

    @Slot()
    def _add_reference(self, field_name: str):
        """参照項目の追加ボタンが押されたときの処理 (変更なし)"""
        ref_info = self._reference_widgets.get(field_name)
        if not ref_info:
            return
        combo: QWidget = ref_info.get("combo")
        modal_type = ref_info["modal_type"]
        self.request_open_editor.emit(modal_type, None, combo)

    @Slot(int, QPushButton, str)
    def _toggle_edit_button(self, index: int, button: QPushButton, field_name: str):
        """ComboBox の選択変更で編集ボタンの有効/無効を切り替え (変更なし)"""
        ref_info = self._reference_widgets.get(field_name)
        if not ref_info or not isinstance(ref_info.get("combo"), QComboBox):
            return
        combo: QComboBox = ref_info["combo"]
        selected_id = combo.currentData()
        button.setEnabled(bool(selected_id))

    @Slot(QWidget, str, str)
    def update_combo_box_after_edit(
        self, target_widget: QWidget, db_key: str, select_id: Optional[str]
    ):
        """
        ネストしたダイアログでの編集/追加後に、対応する参照コンボボックスを更新。
        (変更なし)
        """
        print(
            f"[DEBUG] BaseEditorDialog received update request: target={type(target_widget).__name__}, db_key={db_key}, select_id={select_id}"
        )
        target_field_name: Optional[str] = None
        for field_name, ref_info in self._reference_widgets.items():
            if (
                ref_info.get("combo") == target_widget
                and ref_info.get("db_key") == db_key
            ):
                target_field_name = field_name
                break
        if target_field_name:
            print(f"[DEBUG] Updating reference combo for field: {target_field_name}")
            self._update_reference_combo(target_field_name, select_id)
        else:
            print(
                f"[WARN] No matching reference combo box found to update for db_key={db_key}, target={type(target_widget).__name__}"
            )
