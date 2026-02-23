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

# --- ▼▼▼ Cut, Work, StableDiffusionParams をインポート ▼▼▼ ---
from ..models import DatabaseKey, Work, StableDiffusionParams, Cut
# --- ▲▲▲ 修正ここまで ▲▲▲ ---


class LibraryPanel(QWidget):
    # --- シグナル定義 ---
    # タイプが変更された (新しい DatabaseKey)
    libraryTypeChanged = Signal(str)
    addNewItemClicked = Signal(str, str)  # DatabaseKey -> str
    copyItemClicked = Signal(str, object)
    deleteItemClicked = Signal(str, str)  # DatabaseKey -> str

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._db_data_ref: Dict[str, Dict[str, Any]] = {}  # MainWindow.db_data への参照
        self._current_db_key: Optional[DatabaseKey] = None
        self._init_ui()

    def set_data_reference(self, db_data: Dict[str, Dict[str, Any]]):
        """MainWindow からデータ辞書への参照を設定します。"""
        self._db_data_ref = db_data
        self._update_library_list()  # データをセットしたらリストを更新

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
        # --- ▼▼▼ library_types に SD Params を追加 ▼▼▼ ---
        self.library_types: List[Tuple[str, DatabaseKey]] = [
            ("Works", "works"),
            ("Characters", "characters"),
            ("Scenes", "scenes"),
            ("Cuts", "cuts"),
            ("Actors", "actors"),
            ("Costumes", "costumes"),
            ("Poses", "poses"),
            ("Expressions", "expressions"),
            ("Backgrounds", "backgrounds"),
            ("Lighting", "lighting"),
            ("Compositions", "compositions"),
            ("States", "states"),
            ("Additional Prompts", "additional_prompts"),
            ("Styles", "styles"),
            ("SD Params", "sdParams"),
            ("Sequences", "sequences"),
        ]
        # --- ▲▲▲ 修正ここまで ▲▲▲ ---
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
        self.library_list_widget.currentItemChanged.connect(self._on_selection_changed)
        # itemDoubleClicked は MainWindow で接続
        library_layout.addWidget(self.library_list_widget)

        # 操作ボタン-
        btn_layout_1 = QHBoxLayout()  # 1行目
        self.library_add_btn = QPushButton("＋ Add New")
        self.library_add_btn.clicked.connect(self._on_add_new_clicked)
        # ▼▼▼ コピーボタンを追加 ▼▼▼
        self.library_copy_btn = QPushButton("📄 Copy Selected")
        self.library_copy_btn.clicked.connect(self._emit_copy_item)
        self.library_copy_btn.setEnabled(False)  # 初期状態は無効
        # ▲▲▲ 追加ここまで ▲▲▲
        btn_layout_1.addWidget(self.library_add_btn)
        btn_layout_1.addWidget(self.library_copy_btn)  # コピーボタンを追加

        btn_layout_2 = QHBoxLayout()  # 2行目 (削除ボタン用)
        self.library_delete_btn = QPushButton("🗑️ Delete Selected")
        self.library_delete_btn.clicked.connect(self._on_delete_clicked)
        self.library_delete_btn.setEnabled(False)  # 初期状態は無効
        btn_layout_2.addWidget(self.library_delete_btn)
        btn_layout_2.addStretch()  # 右寄せにする

        library_layout.addLayout(btn_layout_1)
        library_layout.addLayout(btn_layout_2)  # 2行目のレイアウトを追加

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
            self._on_selection_changed(None)

    @Slot()
    def _on_add_new_clicked(self):
        """新規追加ボタンがクリックされたときの処理。"""
        index = self.library_type_combo.currentIndex()
        if self._current_db_key and 0 <= index < len(self.library_types):
            modal_title, db_key = self.library_types[index]
            # if db_key != "sdParams": # ← 削除
            self.addNewItemClicked.emit(db_key, modal_title)  # シグナル発行

    @Slot()
    def _emit_copy_item(self):
        """コピーボタンが押されたら選択中のアイテムデータをシグナルで送る"""
        selected_items = self.library_list_widget.selectedItems()
        if selected_items and self._current_db_key:
            item_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
            item_data = self._db_data_ref.get(self._current_db_key, {}).get(item_id)
            if item_data:
                self.copyItemClicked.emit(self._current_db_key, item_data)
            else:
                QMessageBox.warning(
                    self,
                    "Copy Error",
                    f"Could not find data for {item_id} in {self._current_db_key}.",
                )

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_selection_changed(
        self,
        current: Optional[QListWidgetItem],
        previous: Optional[QListWidgetItem] = None,
    ):
        """リストの選択状態が変わったらボタンの有効/無効を切り替える"""
        is_selected = current is not None
        can_copy_delete = is_selected and self._current_db_key is not None
        self.library_copy_btn.setEnabled(can_copy_delete)
        self.library_delete_btn.setEnabled(can_copy_delete)

    @Slot()
    def _on_delete_clicked(self):
        """削除ボタンがクリックされたときの処理。"""
        selected_items = self.library_list_widget.selectedItems()
        if (
            selected_items and self._current_db_key
            # and self._current_db_key != "sdParams" # ← 削除
        ):
            item_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
            # item_text = selected_items[0].text() # 確認ダイアログは MainWindow 側
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

        # --- ▼▼▼ フラグ変数をここで初期化 ▼▼▼ ---
        is_add_enabled = False
        is_delete_enabled = False
        is_search_enabled = False
        # --- ▲▲▲ 修正ここまで ▲▲▲ ---

        self.library_list_widget.blockSignals(True)
        self.library_list_widget.clear()
        self._on_selection_changed(None)  # ボタンを無効化

        if isinstance(items_dict, dict):  # works, characters, cuts, sdParams など
            is_add_enabled = True
            is_delete_enabled = True
            is_search_enabled = True

            def get_display_name(item: Any) -> str:
                if isinstance(item, Work):
                    return getattr(item, "title_jp", "")
                elif isinstance(item, Cut):
                    return getattr(item, "name", "") or getattr(item, "id", "Unnamed")
                # --- ▼▼▼ SDParams の name を取得 ▼▼▼ ---
                elif isinstance(item, StableDiffusionParams):
                    return getattr(item, "name", "") or getattr(item, "id", "Unnamed")
                # --- ▲▲▲ 追加ここまで ▲▲▲ ---
                else:
                    return getattr(item, "name", "") or getattr(item, "id", "Unnamed")

            items_to_display = list(items_dict.values())

            for item_obj in items_to_display:
                item_name = get_display_name(item_obj) or "Unnamed"
                item_id = getattr(item_obj, "id", None)
                if item_id:
                    list_item = QListWidgetItem(f"{item_name} ({item_id})")
                    list_item.setData(Qt.ItemDataRole.UserRole, item_id)
                    self.library_list_widget.addItem(list_item)
        else:
            print(
                f"[WARN] No data found or unexpected data format ({type(items_dict)}) for key: {db_key}"
            )

        self.library_add_btn.setEnabled(is_add_enabled)

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
