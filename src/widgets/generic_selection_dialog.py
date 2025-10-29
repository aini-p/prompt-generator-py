# src/widgets/generic_selection_dialog.py
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, Slot
from typing import Dict, Any, Optional, Callable, List, Tuple


class GenericSelectionDialog(QDialog):
    """
    汎用的なアイテム選択ダイアログ。
    表示するアイテムの辞書と、リストでの表示方法を定義する関数を受け取る。
    """

    def __init__(
        self,
        items_data: Dict[str, Any],  # 表示するアイテムの辞書 (ID: オブジェクト)
        display_func: Callable[
            [Any], str
        ],  # オブジェクトを受け取り、リスト表示用の文字列を返す関数
        window_title: str = "Select Item",
        filter_placeholder: str = "Filter...",
        sort_key_func: Optional[
            Callable[[Tuple[str, Any]], Any]
        ] = None,  # ソート用のキーを返す関数 (オプション)
        parent=None,
    ):
        super().__init__(parent)
        self.items_data = items_data
        self.display_func = display_func
        self.selected_item_id: Optional[str] = None
        self.setWindowTitle(window_title)

        layout = QVBoxLayout(self)

        # 検索フィルター
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(filter_placeholder)
        self.search_edit.textChanged.connect(self._filter_list)
        filter_layout.addWidget(self.search_edit)
        layout.addLayout(filter_layout)

        # アイテムリスト
        self.item_list_widget = QListWidget()
        self.item_list_widget.itemDoubleClicked.connect(self._accept_selection)
        layout.addWidget(self.item_list_widget)
        self._populate_list(sort_key_func)  # ソート関数を渡す

        # ボタン
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._accept_selection)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _populate_list(
        self, sort_key_func: Optional[Callable[[Tuple[str, Any]], Any]] = None
    ):
        """リストウィジェットにアイテムを表示します。"""
        self.item_list_widget.clear()

        # ソート処理
        items_to_display: List[Tuple[str, Any]] = list(self.items_data.items())
        if sort_key_func:
            try:
                items_to_display.sort(key=sort_key_func)
            except Exception as e:
                print(f"[WARN] Failed to sort items in GenericSelectionDialog: {e}")
                # ソート失敗時は元の順序で表示
        else:
            # デフォルトソート (表示名でソートを試みる)
            try:
                items_to_display.sort(
                    key=lambda item: self.display_func(item[1]).lower()
                )
            except Exception:
                pass  # ソート失敗時は元の順序

        for item_id, item_obj in items_to_display:
            display_text = self.display_func(item_obj)  # 表示用関数を使用
            list_item = QListWidgetItem(display_text)
            list_item.setData(
                Qt.ItemDataRole.UserRole, item_id
            )  # UserRole に ID を設定
            self.item_list_widget.addItem(list_item)

    @Slot(str)
    def _filter_list(self, text: str):
        """入力されたテキストでリストをフィルタリングします。"""
        search_term = text.lower()
        for i in range(self.item_list_widget.count()):
            item = self.item_list_widget.item(i)
            item_text = item.text().lower()
            # 表示テキスト全体でフィルタリング
            item.setHidden(search_term not in item_text)

    @Slot()
    def _accept_selection(self):
        """選択されたアイテムのIDをセットしてダイアログを閉じます。"""
        selected_items = self.item_list_widget.selectedItems()
        if selected_items:
            self.selected_item_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
            self.accept()
        else:
            # 何も選択されていない場合は何もしない
            pass

    def get_selected_item_id(self) -> Optional[str]:
        """選択されたアイテムのIDを返します。"""
        return self.selected_item_id
