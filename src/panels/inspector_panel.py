# src/panels/inspector_panel.py
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QPushButton,
    QGroupBox,
)
from PySide6.QtCore import Qt, Signal, Slot
from typing import Dict, Optional, Any, List
from ..models import (  # 必要なモデルとDatabaseKeyをインポート
    Actor,
    Scene,
    Direction,
    StableDiffusionParams,
    DatabaseKey,
    SceneRole,
)


class InspectorPanel(QWidget):
    # --- シグナル定義 ---
    # 変更が保存された (DatabaseKey, item_id, updated_object)
    changesSaved = Signal(str, str, object)  # DatabaseKey -> str

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._db_data_ref: Dict[str, Dict[str, Any]] = {}  # MainWindow.db_data への参照
        self._sd_params_ref: Optional[StableDiffusionParams] = (
            None  # MainWindow.sd_params への参照
        )
        self._current_db_key: Optional[DatabaseKey] = None
        self._current_item_id: Optional[str] = None
        self._widgets: Dict[str, QWidget] = {}  # 入力ウィジェットを保持
        self._init_ui()

    def set_data_reference(
        self, db_data: Dict[str, Dict[str, Any]], sd_params: StableDiffusionParams
    ):
        """MainWindow からデータ辞書とSDパラメータへの参照を設定します。"""
        self._db_data_ref = db_data
        self._sd_params_ref = sd_params

    def _init_ui(self):
        """UI要素を初期化します。"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.group_box = QGroupBox("Inspector")
        outer_layout = QVBoxLayout(self.group_box)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.content_widget = QWidget()  # スクロールエリア内に入れるウィジェット
        self.form_layout_container = QVBoxLayout(
            self.content_widget
        )  # フォームレイアウトを保持するレイアウト
        self.form_layout_container.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(self.content_widget)
        outer_layout.addWidget(scroll_area)
        main_layout.addWidget(self.group_box)

        self.clear_inspector()  # 初期状態はクリア

    def clear_inspector(self):
        """インスペクターの内容をクリアします。"""
        self._current_db_key = None
        self._current_item_id = None
        self._widgets = {}

        # 既存のウィジェット/レイアウトを削除
        while self.form_layout_container.count():
            item = self.form_layout_container.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            else:
                layout_item = item.layout()
                if layout_item:
                    # ネストされたレイアウトもクリア
                    while layout_item.count():
                        nested = layout_item.takeAt(0)
                        nested_widget = nested.widget()
                        if nested_widget:
                            nested_widget.deleteLater()
                    layout_item.deleteLater()

        self.group_box.setTitle("Inspector")
        placeholder_label = QLabel("Select an item from the list to inspect and edit.")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_label.setWordWrap(True)
        self.form_layout_container.addWidget(placeholder_label)

    def update_inspector(self, db_key: DatabaseKey, item_id: str):
        """指定されたアイテムでインスペクターを更新します。"""
        if self._current_db_key == db_key and self._current_item_id == item_id:
            return  # 同じアイテムなら更新しない

        self.clear_inspector()
        self._current_db_key = db_key
        self._current_item_id = item_id
        self._widgets = {}

        form_layout = QFormLayout()
        form_layout.setContentsMargins(5, 5, 5, 5)

        item_data: Optional[Any] = None
        item_name = item_id

        if db_key == "sdParams":
            item_data = self._sd_params_ref
            item_name = "Stable Diffusion Parameters"
            self.group_box.setTitle(f"Editing: {item_name}")
            if item_data:
                fields_info = {
                    "steps": (QSpinBox, {"minimum": 1, "maximum": 200}),
                    "sampler_name": (QLineEdit, {}),
                    "cfg_scale": (
                        QDoubleSpinBox,
                        {"minimum": 1.0, "maximum": 30.0, "singleStep": 0.5},
                    ),
                    "seed": (QSpinBox, {"minimum": -1, "maximum": 2**31 - 1}),
                    "width": (
                        QSpinBox,
                        {"minimum": 64, "maximum": 4096, "singleStep": 64},
                    ),
                    "height": (
                        QSpinBox,
                        {"minimum": 64, "maximum": 4096, "singleStep": 64},
                    ),
                    "denoising_strength": (
                        QDoubleSpinBox,
                        {"minimum": 0.0, "maximum": 1.0, "singleStep": 0.05},
                    ),
                }
                for field_name, (widget_class, kwargs) in fields_info.items():
                    widget = widget_class(**kwargs)
                    current_value = getattr(item_data, field_name, None)
                    if isinstance(widget, QLineEdit):
                        widget.setText(
                            str(current_value) if current_value is not None else ""
                        )
                    elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                        if isinstance(current_value, (int, float)):
                            widget.setValue(current_value)
                    form_layout.addRow(
                        f"{field_name.replace('_', ' ').capitalize()}:", widget
                    )
                    self._widgets[field_name] = widget
            else:
                item_data = None  # データがない場合は None に

        elif db_key in self._db_data_ref:
            item_data = self._db_data_ref.get(db_key, {}).get(item_id)
            if item_data:
                item_name = getattr(item_data, "name", item_id)
                self.group_box.setTitle(f"Editing: {item_name} ({item_id})")

                common_fields = ["name", "tags", "prompt", "negative_prompt"]
                for field_name in common_fields:
                    if hasattr(item_data, field_name):
                        current_value = getattr(item_data, field_name)
                        if field_name == "tags":
                            widget = QLineEdit(
                                ", ".join(current_value)
                                if isinstance(current_value, list)
                                else ""
                            )
                        elif field_name in ["prompt", "negative_prompt"]:
                            widget = QTextEdit(
                                current_value if current_value is not None else ""
                            )
                            widget.setFixedHeight(60)
                        else:
                            widget = QLineEdit(
                                current_value if current_value is not None else ""
                            )
                        form_layout.addRow(f"{field_name.capitalize()}:", widget)
                        self._widgets[field_name] = widget

                if isinstance(item_data, Actor):
                    self._add_actor_fields(form_layout, item_data)
                elif isinstance(item_data, Direction):
                    self._add_direction_fields(form_layout, item_data)
                elif isinstance(item_data, Scene):
                    self._add_scene_fields(form_layout, item_data)
            else:
                item_data = None  # データがない場合は None に

        if item_data is None:  # データが見つからなかった場合
            self.clear_inspector()  # クリアしてプレースホルダー表示
            error_label = QLabel(f"Item '{item_id}' not found in '{db_key}'.")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.form_layout_container.addWidget(error_label)
            return

        # フォームレイアウトと保存ボタンを追加
        self.form_layout_container.addLayout(form_layout)
        save_button = QPushButton("💾 Save Changes")
        save_button.clicked.connect(self._on_save_clicked)
        self.form_layout_container.addWidget(save_button)
        self._widgets["_save_button"] = save_button
        self.form_layout_container.addStretch()

    def _add_actor_fields(self, layout: QFormLayout, item_data: Actor):
        """Actor固有のフィールドをインスペクターに追加します。"""
        actor_fields = [
            "base_costume_id",
            "base_pose_id",
            "base_expression_id",
            "work_title",
            "character_name",
        ]
        combo_map = {
            "base_costume_id": ("costumes", self._db_data_ref.get("costumes", {})),
            "base_pose_id": ("poses", self._db_data_ref.get("poses", {})),
            "base_expression_id": (
                "expressions",
                self._db_data_ref.get("expressions", {}),
            ),
        }
        for field_name in actor_fields:
            current_value = getattr(item_data, field_name, "")
            if field_name in combo_map:
                widget = self._create_combo_box(
                    current_value, combo_map[field_name][1], allow_none=True
                )
            else:
                widget = QLineEdit(current_value)
            layout.addRow(f"{field_name.replace('_', ' ').capitalize()}:", widget)
            self._widgets[field_name] = widget

    def _add_direction_fields(self, layout: QFormLayout, item_data: Direction):
        """Direction固有のフィールドをインスペクターに追加します。"""
        dir_fields = ["costume_id", "pose_id", "expression_id"]
        combo_map = {
            "costume_id": ("costumes", self._db_data_ref.get("costumes", {})),
            "pose_id": ("poses", self._db_data_ref.get("poses", {})),
            "expression_id": ("expressions", self._db_data_ref.get("expressions", {})),
        }
        for field_name in dir_fields:
            current_value = getattr(item_data, field_name, None)
            widget = self._create_combo_box(
                current_value,
                combo_map[field_name][1],
                allow_none=True,
                none_text="(None / Inherit)",
            )
            layout.addRow(f"{field_name.replace('_', ' ').capitalize()}:", widget)
            self._widgets[field_name] = widget

    def _add_scene_fields(self, layout: QFormLayout, item_data: Scene):
        """Scene固有のフィールドをインスペクターに追加します。"""
        scene_fields = [
            "background_id",
            "lighting_id",
            "composition_id",
            "reference_image_path",
            "image_mode",
            "prompt_template",
            "negative_template",
        ]
        combo_map = {
            "background_id": ("backgrounds", self._db_data_ref.get("backgrounds", {})),
            "lighting_id": ("lighting", self._db_data_ref.get("lighting", {})),
            "composition_id": (
                "compositions",
                self._db_data_ref.get("compositions", {}),
            ),
        }
        mode_options = ["txt2img", "img2img", "img2img_polish"]
        for field_name in scene_fields:
            current_value = getattr(item_data, field_name, "")
            if field_name in combo_map:
                widget = self._create_combo_box(
                    current_value, combo_map[field_name][1], allow_none=True
                )
            elif field_name == "image_mode":
                widget = QComboBox()
                widget.addItems(mode_options)
                try:
                    widget.setCurrentIndex(
                        mode_options.index(current_value)
                        if current_value in mode_options
                        else 0
                    )
                except ValueError:
                    widget.setCurrentIndex(0)
            elif field_name in ["prompt_template", "negative_template"]:
                widget = QTextEdit(current_value)
                widget.setFixedHeight(80)
            else:
                widget = QLineEdit(current_value)
            layout.addRow(f"{field_name.replace('_', ' ').capitalize()}:", widget)
            self._widgets[field_name] = widget
        # Roles は表示のみ
        roles_text = "Roles: (Edit via 'Add New' with same ID or dedicated button)"
        if item_data.roles:
            roles_text = "Roles: " + ", ".join(
                [f"{r.name_in_scene} [{r.id}]" for r in item_data.roles]
            )
        roles_label = QLabel(roles_text)
        roles_label.setWordWrap(True)
        layout.addRow(roles_label)

    def _create_combo_box(
        self,
        current_id: Optional[str],
        items_dict: Dict[str, Any],
        allow_none: bool = True,
        none_text: str = "(None)",
    ) -> QComboBox:
        """参照ID選択用のコンボボックスを作成します。"""
        widget = QComboBox()
        ids = []
        display_names = []
        if allow_none:
            widget.addItem(none_text, None)  # itemData に None を設定
            ids.append(None)
            display_names.append(none_text)

        # 項目を名前でソートして追加
        sorted_items = sorted(
            items_dict.values(), key=lambda item: getattr(item, "name", "").lower()
        )
        for item_obj in sorted_items:
            item_obj_id = getattr(item_obj, "id", None)
            item_obj_name = getattr(item_obj, "name", item_obj_id)
            if item_obj_id:
                widget.addItem(
                    f"{item_obj_name} ({item_obj_id})", item_obj_id
                )  # itemData に ID を設定
                ids.append(item_obj_id)
                display_names.append(item_obj_name)

        # 現在の値を選択
        try:
            index = ids.index(current_id) if current_id in ids else 0
            widget.setCurrentIndex(index)
        except ValueError:
            widget.setCurrentIndex(0)  # 見つからなければ最初の項目 (None)

        return widget

    @Slot()
    def _on_save_clicked(self):
        """保存ボタンがクリックされたときの処理。"""
        if self._current_db_key is None or self._current_item_id is None:
            QMessageBox.warning(
                self.parentWidget(), "Save Error", "No item selected to save."
            )
            return

        db_key = self._current_db_key
        item_id = self._current_item_id
        updated_data = {}
        original_item = None
        is_sd_params = db_key == "sdParams"

        print(f"[DEBUG] Inspector saving changes for {db_key} - {item_id}")

        try:
            if is_sd_params:
                original_item = self._sd_params_ref
            elif db_key in self._db_data_ref:
                original_item = self._db_data_ref.get(db_key, {}).get(item_id)
            else:
                QMessageBox.warning(
                    self.parentWidget(), "Save Error", f"Invalid data type: {db_key}"
                )
                return

            if not original_item:
                QMessageBox.warning(
                    self.parentWidget(), "Save Error", "Original item not found."
                )
                return

            # ウィジェットから値を取得し、型変換
            for field_name, widget in self._widgets.items():
                if field_name == "_save_button":
                    continue
                target_type = type(getattr(original_item, field_name, ""))
                value = None
                if isinstance(widget, QLineEdit):
                    value = widget.text().strip()
                elif isinstance(widget, QTextEdit):
                    value = widget.toPlainText().strip()
                elif isinstance(widget, QSpinBox):
                    value = widget.value()
                elif isinstance(widget, QDoubleSpinBox):
                    value = widget.value()
                elif isinstance(widget, QComboBox):
                    value = widget.currentData()  # itemData (ID または None) を取得
                    # Note: "" vs None の扱い。ここでは ComboBox の itemData に従う

                # 型変換と値の格納
                try:
                    processed_value = value
                    if value is not None:
                        if field_name == "tags" and isinstance(value, str):
                            processed_value = [
                                tag.strip() for tag in value.split(",") if tag.strip()
                            ]
                        elif target_type == int and not isinstance(value, int):
                            processed_value = int(value)
                        elif target_type == float and not isinstance(value, float):
                            processed_value = float(value)
                    updated_data[field_name] = processed_value
                except (ValueError, TypeError) as e:
                    print(
                        f"[DEBUG] Type conversion error for field '{field_name}': {e}. Value: '{value}'"
                    )
                    QMessageBox.warning(
                        self.parentWidget(),
                        "Save Error",
                        f"Invalid value for {field_name}: '{value}'",
                    )
                    return

            # オブジェクトの属性を更新
            name_changed = False
            for field_name, value in updated_data.items():
                if hasattr(original_item, field_name):
                    if (
                        field_name == "name"
                        and getattr(original_item, field_name) != value
                    ):
                        name_changed = True
                    setattr(original_item, field_name, value)
                else:
                    print(
                        f"[DEBUG] Warning: Attribute '{field_name}' not found on item, skipping update."
                    )

            print(f"[DEBUG] Updated item data for {item_id}: {original_item}")

            # 変更保存シグナルを発行
            self.changesSaved.emit(db_key, item_id, original_item)

            QMessageBox.information(
                self.parentWidget(),
                "Saved",
                f"Changes for '{item_name}' saved in memory.\nPress 'Save to DB' to make changes persistent.",
            )

            # 名前が変わった場合、リストの表示も更新する必要がある (MainWindow側で対応)

        except Exception as e:
            QMessageBox.critical(
                self.parentWidget(),
                "Save Error",
                f"An unexpected error occurred while saving: {e}",
            )
            print(f"[DEBUG] Error saving inspector changes: {e}")
            traceback.print_exc()
