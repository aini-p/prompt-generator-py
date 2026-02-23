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
        db_dict: Dict,
        db_key: str,
        parent=None,
    ):
        super().__init__(initial_data, db_dict, db_key, "SD Params", parent)

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
            "model": (QLineEdit, {}),
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

        try:
            # 更新か新規作成かでオブジェクトを準備
            if self.initial_data:
                params = self.initial_data
                print("[DEBUG] Updating existing SD Params from dialog.")
            else:
                params = StableDiffusionParams(
                    id=f"sdp_{int(time.time())}", name="temp"
                )  # nameは後で上書き
                print("[DEBUG] Creating new SD Params from dialog.")

            # ウィジェットの値でオブジェクトを更新
            params.name = name
            params.steps = self._widgets["steps"].value()
            params.sampler_name = self._widgets["sampler_name"].text().strip()
            params.cfg_scale = self._widgets["cfg_scale"].value()
            params.seed = self._widgets["seed"].value()
            params.width = self._widgets["width"].value()
            params.height = self._widgets["height"].value()
            params.denoising_strength = self._widgets["denoising_strength"].value()

            model_text = self._widgets["model"].text().strip()
            params.model = model_text if model_text else None

            return params

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to get SD Params data: {e}")
            return None

    # --- ▲▲▲ 修正ここまで ▲▲▲ ---
