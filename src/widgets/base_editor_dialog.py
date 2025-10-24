# src/widgets/base_editor_dialog.py
import time
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QDialogButtonBox,
    QMessageBox,
    QComboBox,
    QLineEdit,
    QTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QWidget,
)
from PySide6.QtCore import Slot
from typing import Optional, Any, Dict, List, TypeVar, Type

# 型ヒント用
T = TypeVar("T")


class BaseEditorDialog(QDialog):
    """
    新規作成・編集用ダイアログの基底クラス。
    """

    def __init__(
        self,
        initial_data: Optional[Any],
        db_dict: Dict[str, Dict[str, Any]],
        object_type_name: str,  # 例: "Scene", "Costume"
        parent=None,
    ):
        super().__init__(parent)
        self.initial_data = initial_data
        self.db_dict = db_dict  # ComboBox 生成用
        self.object_type_name = object_type_name
        self.saved_data: Optional[Any] = None
        self._widgets: Dict[str, QWidget] = {}  # 各フィールドの入力ウィジェットを保持

        self.setWindowTitle(
            f"{self.object_type_name} の編集"
            if initial_data
            else f"新規 {self.object_type_name} の追加"
        )

        # メインレイアウトとフォームレイアウト
        self.main_layout = QVBoxLayout(self)
        # フォーム部分を入れるコンテナウィジェット (サブクラスでレイアウトを設定)
        self.form_widget = QWidget()
        # QFormLayout を標準とするが、サブクラスで変更可能
        self.form_layout = QFormLayout(self.form_widget)
        self.form_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.addWidget(self.form_widget)

        # UIフィールドの構築 (サブクラスで実装)
        self._populate_fields()

        # OK/Cancelボタン
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(
            self._save_and_accept
        )  # 標準の accept の前に保存処理を挟む
        self.button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(self.button_box)

        # 初期データをUIに設定 (サブクラスの _populate_fields 内で行う方が良い場合もある)
        # self._set_initial_values() # 必要に応じてサブクラスで実装・呼び出し

    def _populate_fields(self):
        """
        UIフィールドを構築し、_widgets ディクショナリに登録します。
        サブクラスで必ず実装してください。
        """
        raise NotImplementedError("Subclasses must implement _populate_fields")

    @Slot()
    def _save_and_accept(self):
        """
        OKボタンが押されたときの処理。get_dataを呼び出し、
        成功すれば self.saved_data にセットして accept() する。
        """
        try:
            data = self.get_data()
            if data is not None:
                self.saved_data = data
                super().accept()  # データ取得・検証成功時にダイアログを閉じる
            # get_data 内でバリデーションエラー時に None が返る想定
        except Exception as e:
            # get_data 内で予期せぬエラーが発生した場合
            QMessageBox.critical(self, "Error", f"Failed to get data from form: {e}")
            import traceback

            traceback.print_exc()

    def get_data(self) -> Optional[Any]:
        """
        UIからデータを取得し、検証後、新規作成または更新されたモデルオブジェクトを返します。
        サブクラスで必ず実装してください。
        バリデーションエラー時は None を返してください。
        """
        raise NotImplementedError("Subclasses must implement get_data")

    # --- Helper Methods (BaseInspector から移植・調整) ---

    def _get_widget_value(self, widget: QWidget) -> Any:
        """ウィジェットタイプに応じて値を取得"""
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        elif isinstance(widget, QTextEdit):
            return widget.toPlainText().strip()
        elif isinstance(widget, QSpinBox):
            return widget.value()
        elif isinstance(widget, QDoubleSpinBox):
            return widget.value()
        elif isinstance(widget, QComboBox):
            return widget.currentData()
        return None

    def _update_object_from_widgets(self, obj: Any) -> bool:
        """self._widgets の値を使ってオブジェクトの属性を更新する汎用ロジック"""
        updated = False
        try:
            for field_name, widget in self._widgets.items():
                if field_name.startswith("_"):
                    continue  # 内部用スキップ

                original_value = getattr(obj, field_name, None)
                target_type = (
                    type(original_value) if original_value is not None else str
                )
                value = self._get_widget_value(widget)
                processed_value = value

                if value is not None:
                    if field_name == "tags" and isinstance(value, str):
                        processed_value = [
                            tag.strip() for tag in value.split(",") if tag.strip()
                        ]
                    elif original_value is None and target_type is str and value == "":
                        processed_value = None  # Optional[str] で "" を None に
                    elif not isinstance(value, target_type) and target_type not in [
                        Any,
                        Optional,
                    ]:  # Any, Optional は型チェックしない
                        # target_type が Optional[X] の場合、Xを取得する必要があるが、ここでは省略
                        try:
                            if target_type == int:
                                processed_value = int(value)
                            elif target_type == float:
                                processed_value = float(value)
                            # bool など他の型が必要な場合
                        except (ValueError, TypeError) as e:
                            raise ValueError(
                                f"Invalid value for {field_name}: '{value}' (expected {target_type.__name__})"
                            ) from e

                if processed_value != original_value:
                    setattr(obj, field_name, processed_value)
                    updated = True
            return updated  # 更新があったかどうか
        except ValueError as ve:
            QMessageBox.warning(self, "Validation Error", str(ve))
            return False  # 更新失敗
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Error processing field {field_name}: {e}"
            )
            import traceback

            traceback.print_exc()
            return False  # 更新失敗

    def _create_combo_box(
        self,
        current_id: Optional[str],
        items_dict: Dict[str, Any],
        allow_none: bool = True,
        none_text: str = "(None)",
        display_attr: str = "name",
    ) -> QComboBox:
        """参照ID選択用のコンボボックスを作成（共通ヘルパー）。"""
        widget = QComboBox()
        ids = []
        if allow_none:
            widget.addItem(none_text, None)
            ids.append(None)

        # Work 用の特別処理 (title_jp を使う)
        is_work = (
            any(isinstance(item, Work) for item in items_dict.values())
            if items_dict
            else False
        )

        get_display_name = (
            lambda item: getattr(item, "title_jp", "")
            if is_work
            else getattr(item, display_attr, "")
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
                widget.addItem(f"{item_obj_name} ({item_obj_id})", item_obj_id)
                ids.append(item_obj_id)

        try:
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


# --- 他のモデルをインポート ---
from ..models import Work  # _create_combo_box で Work かどうか判定するため
