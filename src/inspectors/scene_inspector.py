# src/inspectors/scene_inspector.py
from PySide6.QtWidgets import QLabel, QLineEdit, QTextEdit, QComboBox
from .base_inspector import BaseInspector
from ..models import Scene
from typing import Optional, Any


class SceneInspector(BaseInspector):
    def _populate_fields(self):
        super()._clear_widget()
        item_data: Optional[Scene] = self._current_item_data
        if not item_data:
            return

        # Common fields
        name_edit = QLineEdit(getattr(item_data, "name", ""))
        tags_edit = QLineEdit(", ".join(getattr(item_data, "tags", [])))
        prompt_template_edit = QTextEdit(getattr(item_data, "prompt_template", ""))
        prompt_template_edit.setFixedHeight(80)
        neg_template_edit = QTextEdit(getattr(item_data, "negative_template", ""))
        neg_template_edit.setFixedHeight(80)

        self.layout.addRow("Name:", name_edit)
        self.layout.addRow("Tags:", tags_edit)
        self.layout.addRow("Prompt Template:", prompt_template_edit)
        self.layout.addRow("Negative Template:", neg_template_edit)

        self._widgets["name"] = name_edit
        self._widgets["tags"] = tags_edit
        self._widgets["prompt_template"] = prompt_template_edit
        self._widgets["negative_template"] = neg_template_edit

        # Scene specific fields
        scene_fields = [
            "background_id",
            "lighting_id",
            "composition_id",
            "reference_image_path",
            "image_mode",
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
            else:  # reference_image_path
                widget = QLineEdit(current_value)
            self.layout.addRow(f"{field_name.replace('_', ' ').capitalize()}:", widget)
            self._widgets[field_name] = widget

        # Roles (表示のみ)
        roles_text = "Roles: (Edit via 'Add New' or dedicated Scene editor)"
        if item_data.roles:
            roles_text = "Roles: " + ", ".join(
                [f"{r.name_in_scene} [{r.id}]" for r in item_data.roles]
            )
        roles_label = QLabel(roles_text)
        roles_label.setWordWrap(True)
        self.layout.addRow(roles_label)
