# src/inspectors/sd_params_inspector.py
from PySide6.QtWidgets import QLabel, QLineEdit, QSpinBox, QDoubleSpinBox
from typing import Optional, Any
from .base_inspector import BaseInspector
from ..models import StableDiffusionParams  # 対応するデータモデル


class SDParamsInspector(BaseInspector):
    """StableDiffusionParams オブジェクト用インスペクター。"""

    def _populate_fields(self):
        super()._clear_widget()
        item_data: Optional[StableDiffusionParams] = self._current_item_data

        if not item_data:
            return

        # フィールド情報 (ウィジェットクラスとオプション)
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

        # フィールド情報に基づいてウィジェットを作成し配置
        for field_name, (widget_class, kwargs) in fields_info.items():
            widget = widget_class(**kwargs)
            current_value = getattr(item_data, field_name, None)

            # ウィジェットタイプに応じて値を設定
            if isinstance(widget, QLineEdit):
                widget.setText(str(current_value) if current_value is not None else "")
            elif isinstance(widget, QSpinBox):
                # QSpinBox は整数のみ受け入れる
                widget.setValue(
                    int(current_value)
                    if isinstance(current_value, (int, float, str))
                    and str(current_value).lstrip("-").isdigit()
                    else 0
                )
            elif isinstance(widget, QDoubleSpinBox):
                # QDoubleSpinBox は浮動小数点数を受け入れる
                try:
                    widget.setValue(
                        float(current_value) if current_value is not None else 0.0
                    )
                except (ValueError, TypeError):
                    widget.setValue(0.0)  # 変換できない場合は 0.0

            # フォームレイアウトに行を追加
            self.layout.addRow(f"{field_name.replace('_', ' ').capitalize()}:", widget)
            # ウィジェットを辞書に保存
            self._widgets[field_name] = widget
