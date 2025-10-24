# src/widgets/add_costume_form.py
import time
import json
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QDialogButtonBox,
    QMessageBox,
    QWidget,
    QHBoxLayout,
    QComboBox,
    QGroupBox,
)
from PySide6.QtCore import Slot
from typing import Optional, Dict, Any, List

# ★ Costume, ColorPaletteItem, CharacterColorRef をインポート
from ..models import Costume, ColorPaletteItem, CharacterColorRef


class AddCostumeForm(QDialog):
    def __init__(
        self, initial_data: Optional[Costume], db_dict: Dict[str, Dict], parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle(
            "衣装 (Costume) の編集" if initial_data else "新規 衣装 (Costume) の追加"
        )
        self.initial_data = initial_data
        self.saved_data: Optional[Costume] = None

        # --- 内部状態 ---
        self.current_palette_items: List[ColorPaletteItem] = []
        if initial_data and hasattr(initial_data, "color_palette"):
            # Deep copy
            self.current_palette_items = [
                ColorPaletteItem(**item.__dict__) for item in initial_data.color_palette
            ]

        # UI Elements
        self.name_edit = QLineEdit()
        self.tags_edit = QLineEdit()
        self.prompt_edit = QTextEdit()
        self.negative_prompt_edit = QTextEdit()

        # Layout
        layout = QVBoxLayout(self)
        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("Name:"))
        form_layout.addWidget(self.name_edit)
        form_layout.addWidget(QLabel("Tags (カンマ区切り):"))
        form_layout.addWidget(self.tags_edit)
        form_layout.addWidget(QLabel("プロンプト (Positive):"))
        form_layout.addWidget(self.prompt_edit)
        form_layout.addWidget(QLabel("ネガティブプロンプト (Negative):"))
        form_layout.addWidget(self.negative_prompt_edit)
        layout.addLayout(form_layout)

        # --- カラーパレット編集UI ---
        palette_group = QGroupBox("Color Palette")
        palette_main_layout = QVBoxLayout(palette_group)
        self.palette_rows_layout = QVBoxLayout()  # 各行をここに追加
        palette_main_layout.addLayout(self.palette_rows_layout)

        add_palette_button = QPushButton("＋ Add Palette Item")
        add_palette_button.clicked.connect(
            self._add_palette_row_ui_slot
        )  # スロットに接続
        palette_main_layout.addWidget(add_palette_button)
        layout.addWidget(palette_group)

        # --- ★★★ 修正箇所 ★★★ ---
        # button_box = QDialogButtonBox(...) # 省略 -> 削除
        # 正しい初期化方法を使用
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        # --- ★★★ 修正ここまで ★★★ ---
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # --- 初期データ設定 ---
        if initial_data:
            self.name_edit.setText(getattr(initial_data, "name", ""))
            self.tags_edit.setText(", ".join(getattr(initial_data, "tags", [])))
            self.prompt_edit.setPlainText(getattr(initial_data, "prompt", ""))
            self.negative_prompt_edit.setPlainText(
                getattr(initial_data, "negative_prompt", "")
            )
            # カラーパレットUIを初期データで構築 (current_palette_items は初期化済み)
            self._rebuild_palette_ui()
        else:
            # 新規の場合も空のUIを構築
            self._rebuild_palette_ui()

    def _rebuild_palette_ui(self):
        """カラーパレットUI全体を再構築します。"""
        # 古いUIをクリア
        while self.palette_rows_layout.count():
            item = self.palette_rows_layout.takeAt(0)
            layout_item = item.layout()  # 各行は QHBoxLayout
            if layout_item:
                while layout_item.count():
                    widget_item = layout_item.takeAt(0)
                    widget = widget_item.widget()
                    if widget:
                        widget.deleteLater()
                layout_item.deleteLater()

        # current_palette_items に基づいて行を追加
        for index, item in enumerate(self.current_palette_items):
            self._add_palette_row_ui(item, index)

    def _add_palette_row_ui(self, item: ColorPaletteItem, index: int):
        """カラーパレットの1行分のUIを作成してレイアウトに追加します。"""
        row_layout = QHBoxLayout()
        placeholder_edit = QLineEdit(item.placeholder)
        placeholder_edit.setPlaceholderText("[C1]")
        color_ref_combo = QComboBox()
        ref_names = [
            CharacterColorRef.get_display_name(ref) for ref in CharacterColorRef
        ]
        color_ref_combo.addItems(ref_names)
        try:
            current_ref_name = CharacterColorRef.get_display_name(item.color_ref)
            combo_index = ref_names.index(current_ref_name)
            color_ref_combo.setCurrentIndex(combo_index)
        except ValueError:
            color_ref_combo.setCurrentIndex(0)
        remove_button = QPushButton("🗑️")

        # 変更を内部状態に反映するラムダ
        placeholder_edit.textChanged.connect(
            lambda text, idx=index: self._update_palette_item(idx, placeholder=text)
        )
        color_ref_combo.currentIndexChanged.connect(
            lambda c_idx, idx=index: self._update_palette_item(idx, combo_index=c_idx)
        )
        remove_button.clicked.connect(
            lambda checked=False, idx=index: self._remove_palette_item_ui_slot(idx)
        )

        row_layout.addWidget(QLabel(f"{index + 1}:"))
        row_layout.addWidget(placeholder_edit)
        row_layout.addWidget(QLabel("uses"))
        row_layout.addWidget(color_ref_combo)
        row_layout.addWidget(remove_button)

        self.palette_rows_layout.addLayout(row_layout)

    @Slot()
    def _add_palette_row_ui_slot(self):
        """新しいパレット項目を内部状態に追加し、UIを再構築します。"""
        new_index = len(self.current_palette_items)
        default_item = ColorPaletteItem(
            placeholder=f"[C{new_index + 1}]", color_ref=list(CharacterColorRef)[0]
        )
        self.current_palette_items.append(default_item)
        self._rebuild_palette_ui()  # UI全体を再構築

    @Slot(int)
    def _remove_palette_item_ui_slot(self, index: int):
        """指定されたインデックスのパレット項目を内部状態から削除し、UIを再構築します。"""
        if 0 <= index < len(self.current_palette_items):
            self.current_palette_items.pop(index)
            self._rebuild_palette_ui()  # UI全体を再構築

    def _update_palette_item(
        self,
        index: int,
        placeholder: Optional[str] = None,
        combo_index: Optional[int] = None,
    ):
        """内部状態のパレット項目を更新します。"""
        if 0 <= index < len(self.current_palette_items):
            item = self.current_palette_items[index]
            if placeholder is not None:
                item.placeholder = placeholder.strip()
            if combo_index is not None:
                ref_names = [
                    CharacterColorRef.get_display_name(ref) for ref in CharacterColorRef
                ]
                if 0 <= combo_index < len(ref_names):
                    ref_enum = CharacterColorRef.from_display_name(
                        ref_names[combo_index]
                    )
                    if ref_enum:
                        item.color_ref = ref_enum

    @Slot()
    def accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "Name は必須です。")
            return

        # --- カラーパレットのバリデーション ---
        placeholders_seen = set()
        for index, item in enumerate(self.current_palette_items):
            if not item.placeholder:
                QMessageBox.warning(
                    self,
                    "入力エラー",
                    f"カラーパレット {index + 1} 行目のプレイスホルダーが空です。",
                )
                return
            if not item.placeholder.startswith("[") or not item.placeholder.endswith(
                "]"
            ):
                QMessageBox.warning(
                    self,
                    "入力エラー",
                    f"カラーパレット {index + 1} 行目のプレイスホルダー「{item.placeholder}」は角括弧 [...] で囲んでください。",
                )
                return
            if item.placeholder in placeholders_seen:
                QMessageBox.warning(
                    self,
                    "入力エラー",
                    f"カラーパレットのプレイスホルダー「{item.placeholder}」が重複しています。",
                )
                return
            placeholders_seen.add(item.placeholder)
        # --- バリデーションここまで ---

        self.saved_data = Costume(
            id=getattr(self.initial_data, "id", None) or f"costume_{int(time.time())}",
            name=name,
            tags=[t.strip() for t in self.tags_edit.text().split(",") if t.strip()],
            prompt=self.prompt_edit.toPlainText().strip(),
            negative_prompt=self.negative_prompt_edit.toPlainText().strip(),
            color_palette=self.current_palette_items,  # 編集後の内部状態を渡す
        )
        super().accept()

    def get_data(self) -> Optional[Costume]:
        return self.saved_data
