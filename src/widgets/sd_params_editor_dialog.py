# src/widgets/sd_params_editor_dialog.py
import time  # ★ time をインポート
from PySide6.QtWidgets import (
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
    QMessageBox,
    QFormLayout,
)
from typing import Optional, Dict, Any

from .base_editor_dialog import BaseEditorDialog
from ..models import StableDiffusionParams


class SDParamsEditorDialog(BaseEditorDialog):
    def __init__(
        self,
        initial_data: Optional[StableDiffusionParams],
        db_dict: Dict[str, Dict],
        parent=None,
    ):
        # ★ initial_data が None (新規作成) の場合も考慮
        super().__init__(initial_data, db_dict, "SD Parameters", parent)

    def _populate_fields(self):
        """UI要素を作成し、配置します。"""
        self.form_layout = self.setup_form_layout()
        if not self.form_layout:
            return

        # --- ▼▼▼ name フィールドを追加 ▼▼▼ ---
        self.name_edit = QLineEdit(getattr(self.initial_data, "name", "New SD Params"))
        self.form_layout.addRow("Name:", self.name_edit)
        self._widgets["name"] = self.name_edit  # _widgets に登録
        # --- ▲▲▲ 追加ここまで ▲▲▲ ---

        # sd_params_inspector.py のロジックを流用 (変更なし)
        fields_info = {
            "steps": (QSpinBox, {"minimum": 1, "maximum": 200}),
            "sampler_name": (QLineEdit, {}),
            "cfg_scale": (
                QDoubleSpinBox,
                {"minimum": 1.0, "maximum": 30.0, "singleStep": 0.5},
            ),
            "seed": (QSpinBox, {"minimum": -1, "maximum": 2**31 - 1}),
            "width": (QSpinBox, {"minimum": 64, "maximum": 4096, "singleStep": 64}),
            "height": (QSpinBox, {"minimum": 64, "maximum": 4096, "singleStep": 64}),
            "denoising_strength": (
                QDoubleSpinBox,
                {"minimum": 0.0, "maximum": 1.0, "singleStep": 0.05},
            ),
        }

        # initial_data が None の場合はデフォルト値を使う
        data_source = (
            self.initial_data
            if self.initial_data
            else StableDiffusionParams(id="", name="")
        )  # デフォルト値用

        for field_name, (widget_class, kwargs) in fields_info.items():
            widget = widget_class(**kwargs)
            current_value = getattr(data_source, field_name, None)  # data_source を参照

            # ... (widget への値設定ロジックは変更なし) ...
            if isinstance(widget, QLineEdit):
                widget.setText(str(current_value) if current_value is not None else "")
            elif isinstance(widget, QSpinBox):
                try:
                    widget.setValue(
                        int(current_value) if current_value is not None else 0
                    )
                except (ValueError, TypeError):
                    widget.setValue(0)
            elif isinstance(widget, QDoubleSpinBox):
                try:
                    widget.setValue(
                        float(current_value) if current_value is not None else 0.0
                    )
                except (ValueError, TypeError):
                    widget.setValue(0.0)

            self.form_layout.addRow(
                f"{field_name.replace('_', ' ').capitalize()}:", widget
            )
            self._widgets[field_name] = widget

    # --- ▼▼▼ get_data を修正 (新規作成・編集対応) ▼▼▼ ---
    def get_data(self) -> Optional[StableDiffusionParams]:
        """UIからデータを取得し、新規作成または更新されたオブジェクトを返します。"""

        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "Name は必須です。")
            return None

        if self.initial_data:  # 更新
            updated_params = self.initial_data
            if self._update_object_from_widgets(updated_params):
                print("[DEBUG] SD Params updated from dialog.")
                return updated_params
            else:
                print("[DEBUG] Failed to update SD Params from dialog.")
                return None  # 更新失敗
        else:  # 新規作成
            try:
                new_params = StableDiffusionParams(
                    id=f"sdp_{int(time.time())}",
                    name=name,
                    steps=self._widgets["steps"].value(),
                    sampler_name=self._widgets["sampler_name"].text().strip(),
                    cfg_scale=self._widgets["cfg_scale"].value(),
                    seed=self._widgets["seed"].value(),
                    width=self._widgets["width"].value(),
                    height=self._widgets["height"].value(),
                    denoising_strength=self._widgets["denoising_strength"].value(),
                )
                print("[DEBUG] New SD Params created from dialog.")
                return new_params
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create SD Params: {e}")
                return None

    # --- ▲▲▲ 修正ここまで ▲▲▲ ---
