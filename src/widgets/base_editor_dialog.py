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
    QHBoxLayout,
    QPushButton,
)
from PySide6.QtCore import Slot, Signal
from typing import Optional, Any, Dict, List, TypeVar, Type

# 型ヒント用
T = TypeVar("T")


class BaseEditorDialog(QDialog):
    """
    新規作成・編集用ダイアログの基底クラス。
    """

    # 他の編集ダイアログを開くリクエスト (modal_type, initial_data, 更新対象コンボボックス)
    request_open_editor = Signal(str, object, QComboBox)

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
        self._reference_widgets: Dict[str, Dict[str, QWidget]] = {}

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

    def _get_widget_value(self, field_name: str) -> Any:
        """ウィジェット名から値を取得 (通常ウィジェット or 参照ウィジェット)"""
        if field_name in self._widgets:
            widget = self._widgets[field_name]
            if isinstance(widget, QLineEdit):
                return widget.text().strip()
            elif isinstance(widget, QTextEdit):
                return widget.toPlainText().strip()
            elif isinstance(widget, QSpinBox):
                return widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                return widget.value()
            elif isinstance(widget, QComboBox):
                return widget.currentData()  # 通常のComboBox
        elif field_name in self._reference_widgets:
            # 参照ウィジェットの場合、内部の QComboBox から値を取得
            ref_widget_dict = self._reference_widgets[field_name]
            combo_box = ref_widget_dict.get("combo")
            if isinstance(combo_box, QComboBox):
                return combo_box.currentData()
        return None

    def _update_object_from_widgets(self, obj: Any) -> bool:
        """self._widgets と self._reference_widgets の値を使ってオブジェクト属性を更新"""
        updated = False
        all_field_names = list(self._widgets.keys()) + list(
            self._reference_widgets.keys()
        )

        try:
            for field_name in all_field_names:
                if field_name.startswith("_"):
                    continue

                original_value = getattr(obj, field_name, None)
                target_type = (
                    type(original_value) if original_value is not None else str
                )  # None の場合は str と仮定
                # Optional[str] のような複合型への対応はここでは省略

                value = self._get_widget_value(field_name)  # 修正したメソッドを使用
                processed_value = value

                # --- 型変換処理 (変更なし、必要なら target_type の Optional 対応を追加) ---
                if value is not None:
                    if field_name == "tags" and isinstance(value, str):
                        processed_value = [
                            tag.strip() for tag in value.split(",") if tag.strip()
                        ]
                    elif original_value is None and target_type is str and value == "":
                        processed_value = None
                    elif not isinstance(value, target_type) and target_type not in [
                        Any,
                        Optional,
                    ]:
                        try:
                            if target_type == int:
                                processed_value = int(value)
                            elif target_type == float:
                                processed_value = float(value)
                        except (ValueError, TypeError) as e:
                            raise ValueError(
                                f"Invalid value for {field_name}: '{value}' (expected {target_type.__name__})"
                            ) from e
                # --- 型変換ここまで ---

                if processed_value != original_value:
                    setattr(obj, field_name, processed_value)
                    updated = True
            return updated
        except ValueError as ve:
            QMessageBox.warning(self, "Validation Error", str(ve))
            return False
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Error processing field {field_name}: {e}"
            )
            import traceback

            traceback.print_exc()
            return False

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

    # --- ▼▼▼ 新しいヘルパーメソッドを追加 ▼▼▼ ---
    def _create_reference_editor_widget(
        self,
        field_name: str,  # 対応するモデル属性名 (例: "base_costume_id")
        current_id: Optional[str],
        reference_db_key: str,  # 参照先データの db_key (例: "costumes")
        reference_modal_type: str,  # 参照先を開く modal_type (例: "COSTUME")
        allow_none: bool = True,
        none_text: str = "(None)",
        display_attr: str = "name",
    ) -> QWidget:
        """ComboBox と 新規作成/編集ボタン を持つウィジェットを作成します。"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)  # ボタン間のスペース

        # 1. ComboBox を作成
        items_dict = self.db_dict.get(reference_db_key, {})
        combo_box = self._create_combo_box(
            current_id, items_dict, allow_none, none_text, display_attr
        )
        layout.addWidget(combo_box, 1)  # 伸縮比率を 1 に設定

        # 2. 新規作成ボタン (+)
        add_button = QPushButton("＋")
        add_button.setToolTip(f"Add new {reference_modal_type.lower()}")
        add_button.clicked.connect(
            lambda: self._handle_add_new_reference(reference_modal_type, combo_box)
        )
        layout.addWidget(add_button)

        # 3. 編集ボタン (✎)
        edit_button = QPushButton("✎")
        edit_button.setToolTip(f"Edit selected {reference_modal_type.lower()}")
        edit_button.clicked.connect(
            lambda: self._handle_edit_reference(
                reference_modal_type, combo_box, reference_db_key
            )
        )
        layout.addWidget(edit_button)

        # 4. ComboBox の選択状態に応じて編集ボタンを有効/無効化
        combo_box.currentIndexChanged.connect(
            lambda index: edit_button.setEnabled(combo_box.currentData() is not None)
        )
        # 初期状態を設定
        edit_button.setEnabled(combo_box.currentData() is not None)

        # 内部管理用にウィジェットを保存
        self._reference_widgets[field_name] = {
            "combo": combo_box,
            "add_btn": add_button,
            "edit_btn": edit_button,
            "container": container,  # レイアウトの親ウィジェット
            "ref_db_key": reference_db_key,  # 更新用
            "display_attr": display_attr,  # 更新用
            "allow_none": allow_none,  # 更新用
            "none_text": none_text,  # 更新用
        }

        return container

    @Slot(str, QComboBox)
    def _handle_add_new_reference(self, modal_type: str, target_combo_box: QComboBox):
        """「＋」ボタンが押されたら、新規作成ダイアログを開くリクエストを送信"""
        print(f"[DEBUG] Requesting editor for new {modal_type}")
        # initial_data は None, target_combo_box を渡す
        self.request_open_editor.emit(modal_type, None, target_combo_box)

    @Slot(str, QComboBox, str)
    def _handle_edit_reference(
        self, modal_type: str, target_combo_box: QComboBox, db_key: str
    ):
        """「✎」ボタンが押されたら、編集ダイアログを開くリクエストを送信"""
        selected_id = target_combo_box.currentData()
        if selected_id:
            item_data = self.db_dict.get(db_key, {}).get(selected_id)
            if item_data:
                print(
                    f"[DEBUG] Requesting editor for existing {modal_type}: {selected_id}"
                )
                # initial_data と target_combo_box を渡す
                self.request_open_editor.emit(modal_type, item_data, target_combo_box)
            else:
                QMessageBox.warning(
                    self, "Error", f"Could not find data for ID: {selected_id}"
                )
        else:
            print("[DEBUG] Edit button clicked but no item selected.")

    # --- ▼▼▼ ComboBox 更新用メソッドを追加 ▼▼▼ ---
    @Slot(QComboBox, str, str)  # シグナルから呼ばれる想定
    def update_combo_box_after_edit(
        self, combo_box: QComboBox, db_key: str, select_id: Optional[str]
    ):
        """
        ネストしたダイアログでの編集/追加後に ComboBox を更新し、
        指定された ID を選択状態にします。
        """
        print(f"[DEBUG] Updating ComboBox for {db_key}, selecting {select_id}")
        # 対応する参照ウィジェット情報を取得
        ref_widget_info = None
        for info in self._reference_widgets.values():
            if info.get("combo") == combo_box:
                ref_widget_info = info
                break

        if not ref_widget_info:
            print("[ERROR] Could not find reference widget info for the ComboBox.")
            return

        # 必要な情報を取得
        items_dict = self.db_dict.get(db_key, {})  # 最新の db_dict を参照
        allow_none = ref_widget_info.get("allow_none", True)
        none_text = ref_widget_info.get("none_text", "(None)")
        display_attr = ref_widget_info.get("display_attr", "name")
        is_work = (
            any(isinstance(item, Work) for item in items_dict.values())
            if items_dict
            else False
        )

        # ComboBox をクリアして再構築
        combo_box.blockSignals(True)
        combo_box.clear()
        ids = []

        if allow_none:
            combo_box.addItem(none_text, None)
            ids.append(None)

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
                combo_box.addItem(f"{item_obj_name} ({item_obj_id})", item_obj_id)
                ids.append(item_obj_id)

        # 指定されたIDを選択
        try:
            index = (
                ids.index(select_id) if select_id in ids else (0 if allow_none else -1)
            )
            if index >= 0:
                combo_box.setCurrentIndex(index)
            else:
                # IDが見つからない場合（削除されたなど）は None を選択
                if allow_none:
                    combo_box.setCurrentIndex(0)
        except ValueError:
            if allow_none:
                combo_box.setCurrentIndex(0)

        combo_box.blockSignals(False)
        # 編集ボタンの状態も更新
        edit_button = ref_widget_info.get("edit_btn")
        if isinstance(edit_button, QPushButton):
            edit_button.setEnabled(combo_box.currentData() is not None)


# --- 他のモデルをインポート ---
from ..models import Work  # _create_combo_box で Work かどうか判定するため
