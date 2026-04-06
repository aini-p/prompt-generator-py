# src/widgets/base_editor_dialog.py
import time
import json
import traceback
import copy
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
    QSpinBox,
    QDoubleSpinBox,
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
    # シグナル定義
    request_open_editor = Signal(str, object)
    dataSaved = Signal(str, object, object) # db_key, saved_data, original_data

    def __init__(
        self,
        initial_data: Optional[Any],
        db_dict: Dict[str, Dict],
        db_key: str,
        title_prefix: str,
        parent=None,
    ):
        super().__init__(parent)
        self.original_data = copy.deepcopy(initial_data)
        self.initial_data = initial_data
        self.db_dict = db_dict
        self.db_key = db_key
        self.title_prefix = title_prefix
        self._widgets: Dict[str, QWidget] = {}
        self._reference_widgets: Dict[str, Dict[str, QWidget]] = {}
        self._data_changed = False

        self.setWindowTitle(
            f"{self.title_prefix} - {'編集' if initial_data else '新規作成'}"
        )
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self.resize(600, 500)

        self.main_layout = QVBoxLayout(self)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.main_layout.addWidget(self.scroll_area)
        self.form_widget = QWidget()
        self.scroll_area.setWidget(self.form_widget)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._save_and_accept)
        self.button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(self.button_box)

        self.save_button = self.button_box.button(QDialogButtonBox.StandardButton.Save)
        if self.save_button:
            self.save_button.setEnabled(False)

        self._populate_fields()
        self._connect_change_signals()

    def setup_form_layout(self) -> QFormLayout:
        layout = QFormLayout(self.form_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        return layout

    def _populate_fields(self):
        raise NotImplementedError("サブクラスで _populate_fields を実装してください。")

    def _connect_change_signals(self):
        for widget in self._widgets.values():
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._mark_data_changed)
            elif isinstance(widget, QTextEdit):
                widget.textChanged.connect(self._mark_data_changed)
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._mark_data_changed)
            elif isinstance(widget, QSpinBox):
                widget.valueChanged.connect(self._mark_data_changed)
            elif isinstance(widget, QDoubleSpinBox):
                widget.valueChanged.connect(self._mark_data_changed)
        for ref_info in self._reference_widgets.values():
            combo_widget = ref_info.get("combo")
            if isinstance(combo_widget, QComboBox):
                combo_widget.currentIndexChanged.connect(self._mark_data_changed)

    @Slot()
    def _mark_data_changed(self):
        if not self._data_changed:
            self._data_changed = True
            if self.save_button:
                self.save_button.setEnabled(True)

    def get_data(self) -> Optional[Any]:
        raise NotImplementedError("サブクラスで get_data を実装してください。")

    @Slot()
    def _save_and_accept(self):
        try:
            saved_data = self.get_data()
            if saved_data:
                self.dataSaved.emit(self.db_key, saved_data, self.original_data)
                self.accept()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"保存処理中にエラーが発生しました: {e}")
            traceback.print_exc()

    def _get_widget_value(self, key: str) -> Optional[Any]:
        if key in self._widgets:
            widget = self._widgets[key]
            if isinstance(widget, QLineEdit): return widget.text().strip()
            if isinstance(widget, QTextEdit): return widget.toPlainText().strip()
            if isinstance(widget, QComboBox): return widget.currentData() or widget.currentText()
            if isinstance(widget, QSpinBox): return widget.value()
            if isinstance(widget, QDoubleSpinBox): return widget.value()
        elif key in self._reference_widgets:
            combo = self._reference_widgets[key].get("combo")
            if isinstance(combo, QComboBox): return combo.currentData()
        return None

    def _update_object_from_widgets(self, obj: Any) -> bool:
        try:
            for key, widget in self._widgets.items():
                if not hasattr(obj, key): continue
                value = None
                if isinstance(widget, QLineEdit):
                    value = widget.text().strip()
                    if key == "tags": value = [t.strip() for t in value.split(",") if t.strip()]
                elif isinstance(widget, QTextEdit): value = widget.toPlainText().strip()
                elif isinstance(widget, QComboBox): value = widget.currentData() if widget.currentData() is not None else widget.currentText()
                elif isinstance(widget, QSpinBox): value = widget.value()
                elif isinstance(widget, QDoubleSpinBox): value = widget.value()
                if value is not None: setattr(obj, key, value)
            return True
        except Exception as e:
            QMessageBox.critical(self, "更新エラー", f"データの更新中にエラーが発生しました: {e}")
            traceback.print_exc()
            return False

    def _create_reference_editor_widget(self, field_name: str, current_id: Optional[str], reference_db_key: str, reference_modal_type: str, allow_none: bool = False, none_text: str = "(なし)", display_attr: str = "name") -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        combo = QComboBox()
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        layout.addWidget(combo, 1)

        self._reference_widgets[field_name] = {
            "combo": combo, "db_key": reference_db_key, "modal_type": reference_modal_type,
            "allow_none": allow_none, "none_text": none_text, "display_attr": display_attr,
        }
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

        combo.currentIndexChanged.connect(lambda index, btn=edit_btn, f_name=field_name: self._toggle_edit_button(index, btn, f_name))
        return widget

    def _update_reference_combo(self, field_name: str, select_id: Optional[str]):
        ref_info = self._reference_widgets.get(field_name)
        if not ref_info or not isinstance(ref_info.get("combo"), QComboBox): return
        combo: QComboBox = ref_info["combo"]
        db_key, allow_none, none_text, display_attr = ref_info["db_key"], ref_info["allow_none"], ref_info["none_text"], ref_info["display_attr"]
        items_dict = self.db_dict.get(db_key, {})

        combo.blockSignals(True)
        combo.clear()
        current_index = -1
        if allow_none:
            combo.addItem(none_text, None)
            if select_id is None: current_index = 0
        
        items_to_display = sorted(
            items_dict.values(),
            key=lambda item: getattr(item, "created_at", 0) or 0,
            reverse=True,
        )
        for i, item in enumerate(items_to_display):
            item_id = getattr(item, "id", None)
            display_name = getattr(item, display_attr, item_id or "(No Name/ID)")
            combo.addItem(f"{display_name} ({item_id})", item_id)
            if item_id and item_id == select_id: current_index = i + (1 if allow_none else 0)
        combo.setCurrentIndex(current_index)
        combo.blockSignals(False)
        if edit_btn := ref_info.get("edit_btn"): edit_btn.setEnabled(bool(combo.currentData()))

    @Slot()
    def _edit_reference(self, field_name: str):
        ref_info = self._reference_widgets.get(field_name)
        if not ref_info or not isinstance(ref_info.get("combo"), QComboBox): return
        combo: QComboBox = ref_info["combo"]
        selected_id, db_key, modal_type = combo.currentData(), ref_info["db_key"], ref_info["modal_type"]
        if selected_id and (item_data := self.db_dict.get(db_key, {}).get(selected_id)):
            self.request_open_editor.emit(modal_type, item_data)
        elif selected_id:
            QMessageBox.warning(self, "エラー", f"ID '{selected_id}' のデータが見つかりません。")

    @Slot()
    def _add_reference(self, field_name: str):
        if ref_info := self._reference_widgets.get(field_name):
            self.request_open_editor.emit(ref_info["modal_type"], None)

    @Slot(int, QPushButton, str)
    def _toggle_edit_button(self, index: int, button: QPushButton, field_name: str):
        if ref_info := self._reference_widgets.get(field_name):
            if combo := ref_info.get("combo"):
                button.setEnabled(bool(combo.currentData()))

    def handle_external_data_update(self, db_key: str, updated_item: Any, is_new: bool):
        for field_name, ref_info in self._reference_widgets.items():
            if ref_info.get("db_key") == db_key:
                combo = ref_info.get("combo")
                if isinstance(combo, QComboBox):
                    current_selection = combo.currentData()
                    select_id = getattr(updated_item, 'id', None) if is_new else current_selection
                    self._update_reference_combo(field_name, select_id)
