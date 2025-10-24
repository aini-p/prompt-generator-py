# src/inspectors/costume_inspector.py
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
)
from typing import Optional, Any, Dict
import json
from .base_inspector import BaseInspector
from ..models import Costume, ColorPaletteItem, CharacterColorRef


class CostumeInspector(BaseInspector):
    """Costume オブジェクト用インスペクター。"""

    def _populate_fields(self):
        super()._clear_widget()
        item_data: Optional[Costume] = self._current_item_data
        if not item_data:
            return

        # --- Common fields ---
        name_edit = QLineEdit(getattr(item_data, "name", ""))
        tags_edit = QLineEdit(", ".join(getattr(item_data, "tags", [])))
        prompt_edit = QTextEdit(getattr(item_data, "prompt", ""))
        prompt_edit.setFixedHeight(60)
        neg_prompt_edit = QTextEdit(getattr(item_data, "negative_prompt", ""))
        neg_prompt_edit.setFixedHeight(60)

        self.layout.addRow("Name:", name_edit)
        self.layout.addRow("Tags:", tags_edit)
        self.layout.addRow("Prompt:", prompt_edit)
        self.layout.addRow("Negative Prompt:", neg_prompt_edit)

        self._widgets["name"] = name_edit
        self._widgets["tags"] = tags_edit
        self._widgets["prompt"] = prompt_edit
        self._widgets["negative_prompt"] = neg_prompt_edit

        # --- ★ Color Palette Editor ---
        self.layout.addRow(QLabel("--- Color Palette ---"))
        # color_palette リストの各項目を表示・編集するUIを動的に生成
        self.palette_widgets: List[Dict[str, QWidget]] = []  # 各行のウィジェットを保持
        self.palette_layout = QVBoxLayout()  # パレット項目用のレイアウト

        color_palette_list: List[ColorPaletteItem] = getattr(
            item_data, "color_palette", []
        )

        for index, item in enumerate(color_palette_list):
            self._add_palette_row_ui(item, index)

        add_palette_button = QPushButton("＋ Add Palette Item")
        add_palette_button.clicked.connect(self._add_new_palette_item_ui)

        # QFormLayout に QVBoxLayout を追加
        palette_container = QWidget()
        palette_container.setLayout(self.palette_layout)
        self.layout.addRow(palette_container)
        self.layout.addRow(add_palette_button)

    def _add_palette_row_ui(self, item: ColorPaletteItem, index: int):
        """カラーパレットの1行分のUIを作成してレイアウトに追加します。"""
        row_layout = QHBoxLayout()
        placeholder_edit = QLineEdit(item.placeholder)
        placeholder_edit.setPlaceholderText("[C1]")
        color_ref_combo = QComboBox()
        # Enum の表示名を取得してコンボボックスに追加
        ref_names = [
            CharacterColorRef.get_display_name(ref) for ref in CharacterColorRef
        ]
        color_ref_combo.addItems(ref_names)
        try:
            # 現在の Enum 値に対応する表示名を探して選択
            current_ref_name = CharacterColorRef.get_display_name(item.color_ref)
            combo_index = ref_names.index(current_ref_name)
            color_ref_combo.setCurrentIndex(combo_index)
        except ValueError:
            color_ref_combo.setCurrentIndex(0)  # 見つからなければ先頭

        remove_button = QPushButton("🗑️")
        # remove_button.clicked.connect(lambda checked=False, idx=index: self._remove_palette_item_ui(idx)) # インデックスで削除

        row_layout.addWidget(QLabel(f"{index + 1}:"))
        row_layout.addWidget(placeholder_edit)
        row_layout.addWidget(QLabel("uses"))
        row_layout.addWidget(color_ref_combo)
        row_layout.addWidget(remove_button)

        self.palette_layout.addLayout(row_layout)
        # ウィジェットをリストに保存 (インデックスも保持)
        row_widgets = {
            "index": index,  # この行の現在のインデックス
            "placeholder": placeholder_edit,
            "color_ref": color_ref_combo,
            "remove_button": remove_button,
            "layout": row_layout,  # レイアウト自体も保持
        }
        # 削除ボタンのクリックシグナルに、この行のウィジェット辞書を渡すラムダを接続
        remove_button.clicked.connect(
            lambda checked=False, widgets=row_widgets: self._remove_palette_item_ui(
                widgets
            )
        )
        self.palette_widgets.append(row_widgets)

    def _add_new_palette_item_ui(self):
        """新しいカラーパレット項目を追加するためのUI行を生成します。"""
        new_index = len(self.palette_widgets)
        # デフォルト値で新しい ColorPaletteItem を作成 (UI表示用)
        default_item = ColorPaletteItem(
            placeholder=f"[C{new_index + 1}]",
            color_ref=list(CharacterColorRef)[0],  # 最初の Enum 値
        )
        self._add_palette_row_ui(default_item, new_index)

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
        self.palette_widgets = [
            w for w in self.palette_widgets if w != widgets_to_remove
        ]

        # 残りの行のラベル番号などを更新 (オプション)
        self._update_palette_row_labels()

    def _update_palette_row_labels(self):
        """パレット行のインデックス表示を更新します。"""
        for i, row_widgets in enumerate(self.palette_widgets):
            layout = row_widgets.get("layout")
            if layout:
                # 最初のウィジェット (QLabel) のテキストを更新
                label_widget = layout.itemAt(0).widget()
                if isinstance(label_widget, QLabel):
                    label_widget.setText(f"{i + 1}:")
            row_widgets["index"] = i  # 内部インデックスも更新

    # --- get_data をオーバーライドして JSON を辞書に戻す ---
    def get_data(self) -> Optional[Any]:
        """UIからデータを取得し、Costumeオブジェクトを更新して返します。"""
        updated_item = super().get_data()  # PromptPartBase 部分を取得・更新
        if updated_item is None or not isinstance(updated_item, Costume):
            return None

        # --- ★ カラーパレット情報をUIから読み取り、リストを再構築 ---
        new_palette_list: List[ColorPaletteItem] = []
        try:
            for row_widgets in self.palette_widgets:
                placeholder_widget = row_widgets.get("placeholder")
                color_ref_widget = row_widgets.get("color_ref")

                if isinstance(placeholder_widget, QLineEdit) and isinstance(
                    color_ref_widget, QComboBox
                ):
                    placeholder = placeholder_widget.text().strip()
                    ref_name = color_ref_widget.currentText()
                    # 表示名から Enum 値を取得
                    color_ref_enum = CharacterColorRef.from_display_name(ref_name)

                    if not placeholder:
                        raise ValueError(
                            f"Placeholder cannot be empty (Row {row_widgets.get('index', '?') + 1})."
                        )
                    if not placeholder.startswith("[") or not placeholder.endswith("]"):
                        raise ValueError(
                            f"Placeholder must start with '[' and end with ']' (Row {row_widgets.get('index', '?') + 1})."
                        )
                    if color_ref_enum is None:
                        raise ValueError(
                            f"Invalid color reference selected (Row {row_widgets.get('index', '?') + 1})."
                        )

                    new_palette_list.append(
                        ColorPaletteItem(
                            placeholder=placeholder, color_ref=color_ref_enum
                        )
                    )
            # 更新されたリストをセット
            setattr(updated_item, "color_palette", new_palette_list)
        except ValueError as ve:
            QMessageBox.warning(
                self, "Validation Error", f"Invalid Color Palette input: {ve}"
            )
            return None  # エラー時は None
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error processing Color Palette: {e}")
            return None
        # --- ★ 修正ここまで ---

        return updated_item
