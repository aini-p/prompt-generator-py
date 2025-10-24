# src/panels/library_panel.py
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QGroupBox,
)
from PySide6.QtCore import Qt, Signal, Slot
from typing import Dict, List, Tuple, Optional, Any
from ..models import DatabaseKey, Work


class LibraryPanel(QWidget):
    # --- シグナル定義 ---
    # タイプが変更された (新しい DatabaseKey)
    libraryTypeChanged = Signal(str)
    # アイテムが選択された (DatabaseKey(str), item_id(str))
    itemSelected = Signal(str, str)  # ← 型 (str, str) を指定
    # アイテム選択が解除された
    itemSelectionCleared = Signal()
    addNewItemClicked = Signal(str, str)  # DatabaseKey -> str
    deleteItemClicked = Signal(str, str)  # DatabaseKey -> str

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._db_data_ref: Dict[str, Dict[str, Any]] = {}  # MainWindow.db_data への参照
        self._sd_params_ref: Optional[Any] = None  # MainWindow.sd_params への参照
        self._current_db_key: Optional[DatabaseKey] = None
        self._init_ui()

    def set_data_reference(self, db_data: Dict[str, Dict[str, Any]], sd_params: Any):
        """MainWindow からデータ辞書とSDパラメータへの参照を設定します。"""
        self._db_data_ref = db_data
        self._sd_params_ref = sd_params
        # 参照が設定されたらリストを初期表示
        self._update_library_list()

    def _init_ui(self):
        """UI要素を初期化します。"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # マージンを削除

        library_group = QGroupBox("Library Editing")
        library_layout = QVBoxLayout(library_group)

        # オブジェクトタイプ選択
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self.library_type_combo = QComboBox()
        self.library_types: List[Tuple[str, DatabaseKey]] = [
            ("Works", "works"),
            ("Characters", "characters"),
            ("Scenes", "scenes"),
            ("Actors", "actors"),
            ("Directions", "directions"),
            ("Costumes", "costumes"),
            ("Poses", "poses"),
            ("Expressions", "expressions"),
            ("Backgrounds", "backgrounds"),
            ("Lighting", "lighting"),
            ("Compositions", "compositions"),
            ("Styles", "styles"),
            ("SD Params", "sdParams"),
        ]
        self.library_type_combo.addItems([name for name, key in self.library_types])
        self.library_type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_layout.addWidget(self.library_type_combo)
        library_layout.addLayout(type_layout)

        # 検索バー
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.library_search_edit = QLineEdit()
        self.library_search_edit.setPlaceholderText("Filter by name...")
        self.library_search_edit.textChanged.connect(self.filter_list)
        search_layout.addWidget(self.library_search_edit)
        library_layout.addLayout(search_layout)

        # オブジェクトリスト
        self.library_list_widget = QListWidget()
        self.library_list_widget.currentItemChanged.connect(
            self._on_item_selection_changed
        )
        library_layout.addWidget(self.library_list_widget)

        # 操作ボタン
        btn_layout = QHBoxLayout()
        self.library_add_btn = QPushButton("＋ Add New")
        self.library_add_btn.clicked.connect(self._on_add_new_clicked)
        self.library_delete_btn = QPushButton("🗑️ Delete Selected")
        self.library_delete_btn.clicked.connect(self._on_delete_clicked)
        btn_layout.addWidget(self.library_add_btn)
        btn_layout.addWidget(self.library_delete_btn)
        library_layout.addLayout(btn_layout)

        main_layout.addWidget(library_group)

    @Slot(int)
    def _on_type_changed(self, index: int):
        """タイプコンボボックスの選択が変更されたときの処理。"""
        if 0 <= index < len(self.library_types):
            modal_title, db_key = self.library_types[index]
            self._current_db_key = db_key
            self.library_search_edit.clear()
            self._update_library_list()
            self.libraryTypeChanged.emit(db_key)  # シグナル発行

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_item_selection_changed(
        self, current: QListWidgetItem, previous: QListWidgetItem
    ):
        """リストの選択が変更されたときの処理。"""
        if current and self._current_db_key:
            item_id = current.data(Qt.ItemDataRole.UserRole)
            if item_id:
                self.itemSelected.emit(self._current_db_key, item_id)  # シグナル発行
        else:
            self.itemSelectionCleared.emit()  # シグナル発行

    @Slot()
    def _on_add_new_clicked(self):
        """新規追加ボタンがクリックされたときの処理。"""
        index = self.library_type_combo.currentIndex()
        if self._current_db_key and 0 <= index < len(self.library_types):
            modal_title, db_key = self.library_types[index]
            if db_key != "sdParams":  # SD Params は追加不可
                self.addNewItemClicked.emit(db_key, modal_title)  # シグナル発行

    @Slot()
    def _on_delete_clicked(self):
        """削除ボタンがクリックされたときの処理。"""
        selected_items = self.library_list_widget.selectedItems()
        if (
            selected_items
            and self._current_db_key
            and self._current_db_key != "sdParams"
        ):
            item_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
            item_text = selected_items[0].text()
            # 確認ダイアログは MainWindow 側で表示する想定
            self.deleteItemClicked.emit(self._current_db_key, item_id)  # シグナル発行

    def update_list(self):
        """リストの内容を強制的に更新します (MainWindow から呼ばれる想定)。"""
        self._update_library_list()

    def _update_library_list(self):
        """内部的なリスト更新処理。"""
        if self._current_db_key is None:  # まだタイプが選択されていない場合
            # 最初のタイプを選択状態にする
            initial_index = 0
            if 0 <= initial_index < len(self.library_types):
                self.library_type_combo.setCurrentIndex(initial_index)
                # _on_type_changed が呼ばれ、リストが更新されるはず
            return

        db_key = self._current_db_key
        self.library_list_widget.blockSignals(True)
        self.library_list_widget.clear()

        items_dict = self._db_data_ref.get(db_key)

        if db_key == "sdParams":
            if self._sd_params_ref:
                list_item = QListWidgetItem("Stable Diffusion Parameters")
                list_item.setData(Qt.ItemDataRole.UserRole, "sdParams_instance")
                self.library_list_widget.addItem(list_item)
            is_add_enabled = False
            is_delete_enabled = False
            is_search_enabled = False
        elif isinstance(items_dict, dict):

            def get_display_name(item: Any) -> str:
                """Workならtitle_jp、それ以外ならnameを取得するローカル関数"""
                if isinstance(item, Work):
                    return getattr(item, "title_jp", "")
                else:
                    return getattr(item, "name", "")

            sorted_items = sorted(
                items_dict.values(), key=lambda item: getattr(item, "name", "").lower()
            )
            for item_obj in sorted_items:
                item_name = get_display_name(item_obj) or "Unnamed"
                item_id = getattr(item_obj, "id", None)
                if item_id:
                    list_item = QListWidgetItem(f"{item_name} ({item_id})")
                    list_item.setData(Qt.ItemDataRole.UserRole, item_id)
                    self.library_list_widget.addItem(list_item)
            is_add_enabled = True
            is_delete_enabled = True
            is_search_enabled = True
        else:
            is_add_enabled = False
            is_delete_enabled = False
            is_search_enabled = False

        self.library_add_btn.setEnabled(is_add_enabled)
        self.library_delete_btn.setEnabled(is_delete_enabled)
        self.library_search_edit.setEnabled(is_search_enabled)

        self.library_list_widget.blockSignals(False)
        self.filter_list()  # フィルタ適用

    @Slot()
    def filter_list(self):
        """検索バーのテキストに基づいてリスト項目をフィルタリングします。"""
        search_text = self.library_search_edit.text().lower()
        for i in range(self.library_list_widget.count()):
            item = self.library_list_widget.item(i)
            item_text = item.text().lower()
            item.setHidden(search_text not in item_text)

    def select_item_by_id(self, item_id: Optional[str]):
        """指定されたIDのアイテムを選択状態にします。"""
        self.library_list_widget.blockSignals(True)
        found_item = None
        if item_id:
            for i in range(self.library_list_widget.count()):
                item = self.library_list_widget.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == item_id:
                    found_item = item
                    break
        self.library_list_widget.setCurrentItem(found_item)  # 見つからなければ選択解除
        self.library_list_widget.blockSignals(False)
        # 選択状態が変わったので、手動でシグナルハンドラ（インスペクター更新）を呼ぶ必要がある場合がある
        # しかし、update_ui_after_data_change から呼ばれることを想定し、ここでは呼ばない
