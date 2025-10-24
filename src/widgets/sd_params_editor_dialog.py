# src/widgets/sd_params_editor_dialog.py
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
        # db_dict は使わないが基底クラスのインターフェースに合わせる
        # initial_data は必須とする (None は想定しない)
        if initial_data is None:
            # 万が一 None で呼び出された場合、デフォルト値で作成
            initial_data = StableDiffusionParams()
            print(
                "[WARN] SDParamsEditorDialog called with None initial_data. Using defaults."
            )

        super().__init__(initial_data, db_dict, "SD Parameters", parent)
        # UI構築

    def _populate_fields(self):
        """UI要素を作成し、配置します。"""
        self.form_layout = self.setup_form_layout()
        if not self.form_layout:
            return

        # sd_params_inspector.py のロジックを流用
        fields_info = {
            "steps": (QSpinBox, {"minimum": 1, "maximum": 200}),
            "sampler_name": (QLineEdit, {}),  # QComboBox に変更も可
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

        for field_name, (widget_class, kwargs) in fields_info.items():
            widget = widget_class(**kwargs)
            current_value = getattr(self.initial_data, field_name, None)

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

            # フォームレイアウトに行を追加
            self.form_layout.addRow(
                f"{field_name.replace('_', ' ').capitalize()}:", widget
            )
            # ウィジェットを辞書に保存
            self._widgets[field_name] = widget

    def get_data(self) -> Optional[StableDiffusionParams]:
        """UIからデータを取得し、initial_data オブジェクトを更新して返します。"""
        if not self.initial_data:  # 基本的にここには来ないはず
            QMessageBox.critical(
                self, "Error", "Cannot save SD Params without initial data."
            )
            return None

        updated_params = self.initial_data  # 元のオブジェクトを更新
        if self._update_object_from_widgets(updated_params):
            print("[DEBUG] SD Params updated from dialog.")
            return updated_params
        else:
            # _update_object_from_widgets 内でエラーメッセージ表示済みのはず
            print("[DEBUG] Failed to update SD Params from dialog.")
            return None  # 更新失敗
