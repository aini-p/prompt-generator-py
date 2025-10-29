# src/widgets/state_selection_dialog.py
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
from typing import Dict, Any, Optional, List

from ..models import State  # ★ State モデルをインポート


class StateSelectionDialog(QDialog):
    def __init__(
        self, all_states_data: Dict[str, State], parent=None
    ):  # ★ 型ヒントを State に変更
        super().__init__(parent)
        self.all_states = all_states_data  # ★ 変数名を変更
        self.selected_state_id: Optional[str] = None  # ★ 変数名を変更
        self.setWindowTitle("Select State to Add")  # ★ ウィンドウタイトルを変更

        layout = QVBoxLayout(self)

        # 検索フィルター
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Filter by name, category, or ID..."
        )  # ★ プレースホルダー変更
        self.search_edit.textChanged.connect(self._filter_list)
        filter_layout.addWidget(self.search_edit)
        layout.addLayout(filter_layout)

        # Stateリスト
        self.state_list_widget = QListWidget()  # ★ 変数名を変更
        self.state_list_widget.itemDoubleClicked.connect(self._accept_selection)
        layout.addWidget(self.state_list_widget)
        self._populate_list()

        # ボタン
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._accept_selection)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _populate_list(self):
        """リストウィジェットに全 State を表示します。"""
        self.state_list_widget.clear()
        # カテゴリ > 名前順でソート
        sorted_states = sorted(
            self.all_states.values(),
            key=lambda s: (
                getattr(s, "category", "").lower(),
                getattr(s, "name", "").lower(),
            ),
        )
        for state in sorted_states:  # ★ 変数名を変更
            # ★ 表示テキストにカテゴリも追加
            item_text = f"{getattr(state, 'name', 'N/A')} [{getattr(state, 'category', 'N/A')}] ({getattr(state, 'id', 'N/A')})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, state.id)
            self.state_list_widget.addItem(item)

    @Slot(str)
    def _filter_list(self, text: str):
        """入力されたテキストでリストをフィルタリングします。"""
        search_term = text.lower()
        for i in range(self.state_list_widget.count()):
            item = self.state_list_widget.item(i)
            item_text = item.text().lower()
            # ★ 名前、カテゴリ、ID のいずれかにマッチすれば表示
            item.setHidden(search_term not in item_text)

    @Slot()
    def _accept_selection(self):
        """選択されたアイテムのIDをセットしてダイアログを閉じます。"""
        selected_items = self.state_list_widget.selectedItems()
        if selected_items:
            self.selected_state_id = selected_items[0].data(
                Qt.ItemDataRole.UserRole
            )  # ★ 変数名を変更
            self.accept()
        else:
            pass

    def get_selected_state_id(self) -> Optional[str]:  # ★ メソッド名を変更
        """選択された State ID を返します。"""
        return self.selected_state_id
