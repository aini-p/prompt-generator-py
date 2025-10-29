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
import traceback

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
        db_dict: Dict[str, Dict],
        title_prefix: str,
        parent=None,
    ):
        super().__init__(parent)
        self.initial_data = initial_data
        self.db_dict = db_dict  # 他のデータの参照用
        self.title_prefix = title_prefix
        self.saved_data: Optional[Any] = None  # 保存されたデータを保持
        self._widgets: Dict[str, QWidget] = {}  # UIウィジェットを保持 (get_dataで使用)
        self._reference_widgets: Dict[
            str, Dict[str, QWidget]
        ] = {}  # 参照ウィジェット用
        self._data_changed = False  # データが変更されたかのフラグ
        self._nested_editors: Dict[
            QWidget, BaseEditorDialog
        ] = {}  # ネストされたエディタ

        self.setWindowTitle(
            f"{self.title_prefix} - {'編集' if initial_data else '新規作成'}"
        )
        self.setMinimumWidth(500)

        # Main Layout
        self.main_layout = QVBoxLayout(self)
        # フォームレイアウト用のウィジェット（サブクラスで中身を追加）
        self.form_widget = QWidget()
        self.main_layout.addWidget(self.form_widget)

        # Save/Cancel Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._save_and_accept)
        self.button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(self.button_box)

        # Save ボタンを最初は無効化 (変更があったら有効化)
        self.save_button = self.button_box.button(QDialogButtonBox.StandardButton.Save)
        if self.save_button:
            self.save_button.setEnabled(False)

        # サブクラスでフィールドを構築
        self._populate_fields()

        # ウィジェット変更時にフラグを立てるシグナル接続
        self._connect_change_signals()

    def setup_form_layout(self) -> QFormLayout:
        """QFormLayout をセットアップし、それを返します。"""
        layout = QFormLayout(self.form_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        return layout

    def _populate_fields(self):
        """サブクラスでUI要素を作成し配置する"""
        raise NotImplementedError("サブクラスで _populate_fields を実装してください。")

    def _connect_change_signals(self):
        """_widgets に登録されたウィジェットの変更シグナルを _mark_data_changed に接続"""
        for widget in self._widgets.values():
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._mark_data_changed)
            elif isinstance(widget, QTextEdit):
                # QTextEdit は変更のたびにシグナルが出るので注意
                widget.textChanged.connect(self._mark_data_changed)
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._mark_data_changed)
            # 他のウィジェットタイプ (QCheckBox, QSpinBox など) も必要に応じて追加

        # --- ▼▼▼ _reference_widgets 内の QComboBox も接続 ▼▼▼ ---
        for ref_info in self._reference_widgets.values():
            combo_widget = ref_info.get("combo")
            if isinstance(combo_widget, QComboBox):
                print(
                    f"[DEBUG] Connecting currentIndexChanged for reference combo: {ref_info}"
                )  # デバッグ用
                combo_widget.currentIndexChanged.connect(self._mark_data_changed)

    # --- ▼▼▼ _mark_data_changed メソッドを追加 ▼▼▼ ---
    @Slot()
    def _mark_data_changed(self):
        """データが変更されたことをマークし、Saveボタンを有効化"""
        if not self._data_changed:
            self._data_changed = True
            print("[DEBUG] Data changed, enabling Save button.")  # デバッグ用
            if self.save_button:
                self.save_button.setEnabled(True)

    # --- ▲▲▲ 追加 ▲▲▲ ---

    def get_data(self) -> Optional[Any]:
        """サブクラスでUIからデータを取得し、オブジェクトを返す"""
        raise NotImplementedError("サブクラスで get_data を実装してください。")

    @Slot()
    def _save_and_accept(self):
        """Saveボタンが押されたときの処理"""
        print("[DEBUG] Save button clicked.")  # デバッグ用
        try:
            data = self.get_data()
            if data:
                self.saved_data = data
                print(
                    f"[DEBUG] get_data returned valid data: {getattr(data, 'id', 'N/A')}"
                )  # デバッグ用
                super().accept()  # ダイアログを閉じる
            else:
                # get_data 内でバリデーションエラーメッセージが表示されているはず
                print(
                    "[DEBUG] get_data returned None (validation failed or error). Dialog remains open."
                )  # デバッグ用
        except Exception as e:
            QMessageBox.critical(
                self, "エラー", f"保存処理中にエラーが発生しました: {e}"
            )
            print(
                f"[ERROR] Exception during _save_and_accept -> get_data: {e}"
            )  # デバッグ用
            traceback.print_exc()

    def _get_widget_value(self, key: str) -> Optional[Any]:
        """_widgets または _reference_widgets から値を取得"""
        if key in self._widgets:
            widget = self._widgets[key]
            if isinstance(widget, QLineEdit):
                return widget.text().strip()
            elif isinstance(widget, QTextEdit):
                return widget.toPlainText().strip()
            elif isinstance(widget, QComboBox):
                return (
                    widget.currentData() or widget.currentText()
                )  # itemDataがあればそれを優先
            # 他のウィジェットタイプ
        elif key in self._reference_widgets:
            combo = self._reference_widgets[key].get("combo")
            if isinstance(combo, QComboBox):
                return combo.currentData()  # itemData (ID) を返す
        print(f"[WARN] Widget/Reference not found for key: {key}")
        return None

    def _update_object_from_widgets(self, obj: Any) -> bool:
        """_widgets の内容でオブジェクトの属性を更新"""
        try:
            for key, widget in self._widgets.items():
                if not hasattr(obj, key):
                    print(f"[WARN] Object has no attribute '{key}', skipping update.")
                    continue
                value = None
                if isinstance(widget, QLineEdit):
                    value = widget.text().strip()
                    # 特殊ケース: tags
                    if key == "tags":
                        value = [t.strip() for t in value.split(",") if t.strip()]
                elif isinstance(widget, QTextEdit):
                    value = widget.toPlainText().strip()
                elif isinstance(widget, QComboBox):
                    # itemData があればそれを、なければテキストを
                    value = (
                        widget.currentData()
                        if widget.currentData() is not None
                        else widget.currentText()
                    )
                # 他のウィジェットタイプも必要に応じて追加 (QSpinBox, QCheckBox など)

                if value is not None:
                    # 型チェックや変換が必要な場合があるかもしれない
                    setattr(obj, key, value)
            return True
        except Exception as e:
            QMessageBox.critical(
                self, "更新エラー", f"データの更新中にエラーが発生しました: {e}"
            )
            print(f"[ERROR] Exception during _update_object_from_widgets: {e}")
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
