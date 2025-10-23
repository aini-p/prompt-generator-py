# src/inspectors/base_inspector.py
# ★ QComboBox をインポートに追加
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QMessageBox, QComboBox
from typing import Optional, Any, Dict


class BaseInspector(QWidget):
    """インスペクターウィジェットの基底クラス。"""

    def __init__(
        self, db_data_ref: Dict[str, Dict[str, Any]], parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._db_data_ref = db_data_ref  # 全データへの参照（ComboBox用）
        self._current_item_data: Optional[Any] = None
        self._widgets: Dict[str, QWidget] = {}  # 各フィールドの入力ウィジェットを保持

        # メインレイアウト（多くのインスペクターは QFormLayout を使う）
        self.layout = QFormLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        # self.setLayout(self.layout) # QFormLayout は直接 setできない場合がある？

    def set_item(self, item_data: Any):
        """表示・編集対象のアイテムデータを設定し、UIに反映します。"""
        self._current_item_data = item_data
        self._populate_fields()

    def get_data(self) -> Optional[Any]:
        """UIから編集後のデータを取得し、元のデータオブジェクトに反映して返します。"""
        if not self._current_item_data:
            return None

        updated = False
        try:
            for field_name, widget in self._widgets.items():
                if field_name.startswith("_"):
                    continue  # 内部用はスキップ

                original_value = getattr(self._current_item_data, field_name, None)
                target_type = (
                    type(original_value) if original_value is not None else str
                )  # 元の型を取得（Noneの場合はstr想定）
                value = None

                # ウィジェットタイプに応じて値を取得
                from PySide6.QtWidgets import (
                    QLineEdit,
                    QTextEdit,
                    QSpinBox,
                    QDoubleSpinBox,
                )  # ローカルインポートに変更

                if isinstance(widget, QLineEdit):
                    value = widget.text().strip()
                elif isinstance(widget, QTextEdit):
                    value = widget.toPlainText().strip()
                elif isinstance(widget, QSpinBox):
                    value = widget.value()
                elif isinstance(widget, QDoubleSpinBox):
                    value = widget.value()
                elif isinstance(widget, QComboBox):
                    value = widget.currentData()  # itemData を取得

                # 型変換と値の格納
                processed_value = value
                if value is not None:
                    if field_name == "tags" and isinstance(value, str):
                        processed_value = [
                            tag.strip() for tag in value.split(",") if tag.strip()
                        ]
                    # 元の型が Optional[str] で value が空文字列の場合、None にする
                    elif original_value is None and target_type is str and value == "":
                        processed_value = None
                    # 型が異なり、変換可能な場合は変換
                    elif not isinstance(value, target_type):
                        try:
                            if target_type == int:
                                processed_value = int(value)
                            elif target_type == float:
                                processed_value = float(value)
                            # bool など他の型が必要な場合はここに追加
                        except (ValueError, TypeError):
                            # 型変換エラー時は元の値を使うか、エラーを出す
                            raise ValueError(
                                f"Invalid value for {field_name}: '{value}' (expected {target_type.__name__})"
                            )
                            # processed_value = original_value # または元の値に戻す

                # 値が変更されたかチェック
                if processed_value != original_value:
                    setattr(self._current_item_data, field_name, processed_value)
                    updated = True

            print(
                f"[DEBUG] Inspector get_data successful for {getattr(self._current_item_data, 'id', 'item')}"
            )
            return self._current_item_data  # 更新されたオブジェクトを返す

        except ValueError as ve:  # 型変換エラーなどをキャッチ
            QMessageBox.warning(self, "Validation Error", str(ve))
            print(f"[DEBUG] Validation Error in inspector: {ve}")
            return None  # エラー時は None を返す
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Error getting data from inspector: {e}"
            )
            print(f"[DEBUG] Error in inspector get_data: {e}")
            import traceback

            traceback.print_exc()
            return None

    def _populate_fields(self):
        # サブクラスでフィールドを追加する処理を実装
        raise NotImplementedError("Subclasses must implement _populate_fields")

    def _clear_widget(self):
        """アイテムデータに基づいてUIフィールドを具体的に構築・設定します（サブクラスで実装）。"""
        # 既存のウィジェットをクリア
        self._widgets = {}
        # QFormLayout の行をクリア
        while self.layout.rowCount() > 0:
            self.layout.removeRow(0)

    # ★ QComboBox を使用するメソッド
    def _create_combo_box(
        self,
        current_id: Optional[str],
        items_dict: Dict[str, Any],
        allow_none: bool = True,
        none_text: str = "(None)",
        display_attr: str = "name",
    ) -> QComboBox:
        """参照ID選択用のコンボボックスを作成（共通ヘルパー）。"""
        # from PySide6.QtWidgets import QComboBox # ローカルインポートは不要になった
        widget = QComboBox()  # QComboBoxがインポートされているので直接使える
        ids = []
        if allow_none:
            widget.addItem(none_text, None)  # itemData に None
            ids.append(None)

        get_display_name = (
            lambda item: getattr(item, display_attr, "")
            or getattr(item, "name", "")
            or getattr(item, "id", "Unnamed")
        )
        sorted_items = sorted(
            items_dict.values(), key=lambda item: get_display_name(item).lower()
        )

        for item_obj in sorted_items:
            item_obj_id = getattr(item_obj, "id", None)
            item_obj_name = get_display_name(item_obj)
            if item_obj_id:
                widget.addItem(
                    f"{item_obj_name} ({item_obj_id})", item_obj_id
                )  # itemData に ID
                ids.append(item_obj_id)

        try:
            # current_id が None の場合も正しく処理
            index = (
                ids.index(current_id)
                if current_id in ids
                else (0 if allow_none or not ids else -1)
            )
            if index >= 0:
                widget.setCurrentIndex(index)
        except ValueError:
            if allow_none:
                widget.setCurrentIndex(0)

        return widget
