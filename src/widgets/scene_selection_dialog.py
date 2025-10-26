# src/widgets/scene_selection_dialog.py
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

from ..models import Scene  # Scene モデルをインポート


class SceneSelectionDialog(QDialog):
    def __init__(self, all_scenes_data: Dict[str, Scene], parent=None):
        super().__init__(parent)
        self.all_scenes = all_scenes_data
        self.selected_scene_id: Optional[str] = None
        self.setWindowTitle("Select Scene to Add")

        layout = QVBoxLayout(self)

        # 検索フィルター
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter by name or ID...")
        self.search_edit.textChanged.connect(self._filter_list)
        filter_layout.addWidget(self.search_edit)
        layout.addLayout(filter_layout)

        # シーンリスト
        self.scene_list_widget = QListWidget()
        self.scene_list_widget.itemDoubleClicked.connect(
            self._accept_selection
        )  # ダブルクリックでも追加
        layout.addWidget(self.scene_list_widget)
        self._populate_list()  # 初期リスト表示

        # ボタン
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._accept_selection)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _populate_list(self):
        """リストウィジェットに全シーンを表示します。"""
        self.scene_list_widget.clear()
        # 名前順でソート
        sorted_scenes = sorted(
            self.all_scenes.values(), key=lambda s: getattr(s, "name", "").lower()
        )
        for scene in sorted_scenes:
            item = QListWidgetItem(f"{scene.name} ({scene.id})")
            item.setData(Qt.ItemDataRole.UserRole, scene.id)
            self.scene_list_widget.addItem(item)

    @Slot(str)
    def _filter_list(self, text: str):
        """入力されたテキストでリストをフィルタリングします。"""
        search_term = text.lower()
        for i in range(self.scene_list_widget.count()):
            item = self.scene_list_widget.item(i)
            item_text = item.text().lower()
            item.setHidden(search_term not in item_text)

    @Slot()
    def _accept_selection(self):
        """選択されたアイテムのIDをセットしてダイアログを閉じます。"""
        selected_items = self.scene_list_widget.selectedItems()
        if selected_items:
            self.selected_scene_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
            self.accept()  # QDialog.DialogCode.Accepted で閉じる
        else:
            # 何も選択されていない場合は何もしないか、警告を出す
            pass

    def get_selected_scene_id(self) -> Optional[str]:
        """選択されたシーンIDを返します。"""
        return self.selected_scene_id
