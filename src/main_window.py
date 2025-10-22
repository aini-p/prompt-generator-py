# src/main_window.py
import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QScrollArea, QGroupBox, QListWidget,
    QListWidgetItem, QTextEdit, QFileDialog, QMessageBox, QSplitter,
    QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox # For SD Params
)
from PySide6.QtCore import Qt, Slot # Import Slot
from . import database as db
from .models import Scene, Actor, Direction, PromptPartBase, StableDiffusionParams # Import models
from .prompt_generator import generate_batch_prompts, create_image_generation_tasks
from .batch_runner import run_stable_diffusion

# Placeholder for Edit Forms (You'd create separate QDialog classes for these)
# from .edit_forms import EditActorDialog, EditSceneDialog, ...

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Object-Oriented Prompt Builder")
        self.setGeometry(100, 100, 1200, 800) # x, y, width, height

        # --- Data Loading ---
        self.db_data = self._load_all_data() # Load everything into memory for simplicity
        self.sd_params = self.db_data.get('sdParams', StableDiffusionParams()) # Get SD params

        # --- State ---
        self.current_scene_id = next(iter(self.db_data.get('scenes', {})), None) # First scene ID or None
        self.actor_assignments: Dict[str, str] = {} # role_id -> actor_id
        self.generated_prompts = [] # Store GeneratedPrompt dicts

        # --- Main Layout ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget) # Horizontal split

        # Use QSplitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # --- Left Panel ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(400) # Set a minimum width
        left_panel.setMaximumWidth(600) # Optional: Set a maximum width
        splitter.addWidget(left_panel)

        # 1. Data Management Section
        self._setup_data_management_ui(left_layout)

        # 2. Prompt Generation Section
        self._setup_prompt_generation_ui(left_layout)

        # 3. Library Editing Section (Scrollable)
        library_scroll = QScrollArea()
        library_scroll.setWidgetResizable(True)
        library_widget = QWidget()
        self.library_layout = QVBoxLayout(library_widget) # Store layout to update later
        library_widget.setLayout(self.library_layout)
        library_scroll.setWidget(library_widget)
        left_layout.addWidget(library_scroll)

        self._setup_library_ui() # Populate library section

        left_layout.addStretch() # Push content to the top

        # --- Right Panel ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        splitter.addWidget(right_panel)

        right_layout.addWidget(QLabel("Generated Prompts (Batch)"))
        self.prompt_display_area = QTextEdit() # Use QTextEdit for easier text handling
        self.prompt_display_area.setReadOnly(True)
        right_layout.addWidget(self.prompt_display_area)

        # Adjust initial sizes of splitter panels
        splitter.setSizes([450, 750]) # Initial widths for left and right

    def _load_all_data(self):
        """Load all data from DB into a dictionary."""
        # This is simple but might be slow for huge DBs.
        # Consider loading only necessary data on demand later.
        data = {
            'actors': db.load_actors(),
            'scenes': db.load_scenes(),
            'directions': db.load_directions(),
            'costumes': db.load_costumes(),
            'poses': db.load_poses(),
            'expressions': db.load_expressions(),
            'backgrounds': db.load_backgrounds(),
            'lighting': db.load_lighting(),
            'compositions': db.load_compositions(),
            'sdParams': db.load_sd_params(),
        }
        # Filter out potential None values if load functions might return them
        return {k: v for k, v in data.items() if v is not None}


    def _setup_data_management_ui(self, parent_layout):
        group = QGroupBox("Data Management")
        layout = QHBoxLayout()
        group.setLayout(layout)

        save_btn = QPushButton("💾 Save to DB")
        save_btn.clicked.connect(self.save_all_data) # Connect signal to slot
        export_btn = QPushButton("📤 Export JSON")
        export_btn.clicked.connect(self.export_data)
        import_btn = QPushButton("📥 Import JSON")
        import_btn.clicked.connect(self.import_data)

        layout.addWidget(save_btn)
        layout.addWidget(export_btn)
        layout.addWidget(import_btn)
        parent_layout.addWidget(group)

    def _setup_prompt_generation_ui(self, parent_layout):
        group = QGroupBox("Prompt Generation")
        self.prompt_gen_layout = QVBoxLayout() # Store layout to rebuild assignment UI
        group.setLayout(self.prompt_gen_layout)

        # Scene Selection
        scene_layout = QHBoxLayout()
        scene_layout.addWidget(QLabel("1. Select Scene:"))
        self.scene_combo = QComboBox()
        self.scene_combo.addItems([s.name for s in self.db_data.get('scenes', {}).values()])
        # Find index of current_scene_id to set initial selection
        current_scene_index = 0
        scene_list = list(self.db_data.get('scenes', {}).values())
        if self.current_scene_id:
            try:
                 current_scene_index = [s.id for s in scene_list].index(self.current_scene_id)
            except ValueError:
                 current_scene_index = 0 # Default to first if ID not found
                 if scene_list: self.current_scene_id = scene_list[0].id # Update state

        self.scene_combo.setCurrentIndex(current_scene_index)
        self.scene_combo.currentIndexChanged.connect(self.on_scene_changed) # Connect signal
        scene_layout.addWidget(self.scene_combo)
        self.prompt_gen_layout.addLayout(scene_layout)

        # Role Assignment Area (will be built dynamically)
        self.role_assignment_widget = QWidget() # Placeholder widget
        self.prompt_gen_layout.addWidget(self.role_assignment_widget)
        self.build_role_assignment_ui() # Initial build

        # Generate Buttons
        generate_preview_btn = QPushButton("🔄 Generate Prompt Preview")
        generate_preview_btn.setStyleSheet("background-color: #ffc107;")
        generate_preview_btn.clicked.connect(self.generate_prompts)

        execute_btn = QPushButton("🚀 Execute Image Generation (Run Batch)")
        execute_btn.setStyleSheet("background-color: #28a745; color: white;")
        execute_btn.clicked.connect(self.execute_generation)

        self.prompt_gen_layout.addWidget(generate_preview_btn)
        self.prompt_gen_layout.addWidget(execute_btn)
        parent_layout.addWidget(group)


    def build_role_assignment_ui(self):
         """Dynamically builds the UI for assigning actors to roles based on the selected scene."""
         # Clear previous widgets if they exist
         if self.role_assignment_widget.layout():
             # Properly remove and delete old widgets
             old_layout = self.role_assignment_widget.layout()
             while old_layout.count():
                 item = old_layout.takeAt(0)
                 widget = item.widget()
                 if widget:
                     widget.deleteLater()
             del old_layout # Delete the layout itself

         new_layout = QVBoxLayout(self.role_assignment_widget) # Assign new layout
         new_layout.addWidget(QLabel("2. Assign Actors to Roles:"))

         current_scene = self.db_data.get('scenes', {}).get(self.current_scene_id)
         if not current_scene:
             new_layout.addWidget(QLabel("No scene selected or scene not found."))
             return # Exit if no valid scene

         actor_list = list(self.db_data.get('actors', {}).values())
         actor_names = ["-- Select Actor --"] + [a.name for a in actor_list]
         actor_ids = [""] + [a.id for a in actor_list] # ID list matching names

         for role in current_scene.roles:
             role_layout = QHBoxLayout()
             label_text = f"{role.name_in_scene} ([{role.id.upper()}])"
             role_layout.addWidget(QLabel(label_text))

             combo = QComboBox()
             combo.addItems(actor_names)

             # Set current selection if exists in assignments
             assigned_actor_id = self.actor_assignments.get(role.id)
             current_index = 0
             if assigned_actor_id and assigned_actor_id in actor_ids:
                 current_index = actor_ids.index(assigned_actor_id)
             combo.setCurrentIndex(current_index)

             # Use lambda to pass role.id to the slot
             combo.currentIndexChanged.connect(
                 lambda index, r_id=role.id, id_list=actor_ids: self.on_actor_assigned(r_id, id_list[index])
             )

             role_layout.addWidget(combo)
             new_layout.addLayout(role_layout)


    def _setup_library_ui(self):
         """Populates the library editing section with collapsible groups."""
         # Clear existing widgets first
         while self.library_layout.count():
              item = self.library_layout.takeAt(0)
              widget = item.widget()
              if widget: widget.deleteLater()

         library_group = QGroupBox("Library Editing")
         library_group_layout = QVBoxLayout()
         library_group.setLayout(library_group_layout)
         self.library_layout.addWidget(library_group) # Add to the main library layout

         # --- SD Params Editor ---
         sd_group = QGroupBox("Stable Diffusion Parameters")
         sd_layout = QFormLayout() # Use QFormLayout for label-input pairs
         sd_group.setLayout(sd_layout)
         library_group_layout.addWidget(sd_group)

         # Create SpinBox/LineEdit widgets for each parameter
         self.sd_steps_spin = QSpinBox(minimum=1, maximum=200, value=self.sd_params.steps)
         self.sd_sampler_edit = QLineEdit(self.sd_params.sampler_name)
         self.sd_cfg_spin = QDoubleSpinBox(minimum=1.0, maximum=30.0, singleStep=0.5, value=self.sd_params.cfg_scale)
         self.sd_seed_spin = QSpinBox(minimum=-1, maximum=2**32 -1, value=self.sd_params.seed)
         self.sd_width_spin = QSpinBox(minimum=64, maximum=4096, singleStep=64, value=self.sd_params.width)
         self.sd_height_spin = QSpinBox(minimum=64, maximum=4096, singleStep=64, value=self.sd_params.height)
         self.sd_denoising_spin = QDoubleSpinBox(minimum=0.0, maximum=1.0, singleStep=0.05, value=self.sd_params.denoising_strength)

         # Connect signals to update internal state
         self.sd_steps_spin.valueChanged.connect(lambda v: setattr(self.sd_params, 'steps', v))
         self.sd_sampler_edit.textChanged.connect(lambda t: setattr(self.sd_params, 'sampler_name', t))
         self.sd_cfg_spin.valueChanged.connect(lambda v: setattr(self.sd_params, 'cfg_scale', v))
         self.sd_seed_spin.valueChanged.connect(lambda v: setattr(self.sd_params, 'seed', v))
         self.sd_width_spin.valueChanged.connect(lambda v: setattr(self.sd_params, 'width', v))
         self.sd_height_spin.valueChanged.connect(lambda v: setattr(self.sd_params, 'height', v))
         self.sd_denoising_spin.valueChanged.connect(lambda v: setattr(self.sd_params, 'denoising_strength', v))


         # Add widgets to layout
         sd_layout.addRow("Steps:", self.sd_steps_spin)
         sd_layout.addRow("Sampler Name:", self.sd_sampler_edit)
         sd_layout.addRow("CFG Scale:", self.sd_cfg_spin)
         sd_layout.addRow("Seed (-1 Random):", self.sd_seed_spin)
         sd_layout.addRow("Width:", self.sd_width_spin)
         sd_layout.addRow("Height:", self.sd_height_spin)
         sd_layout.addRow("Denoising (img2img):", self.sd_denoising_spin)


         # --- Collapsible Library Sections ---
         # Define items to display in library
         library_items = [
             ("Scenes", "scenes", "SCENE"),
             ("Actors", "actors", "ACTOR"),
             ("Directions", "directions", "DIRECTION"),
             ("Costumes", "costumes", "COSTUME"),
             ("Poses", "poses", "POSE"),
             ("Expressions", "expressions", "EXPRESSION"),
             ("Backgrounds", "backgrounds", "BACKGROUND"),
             ("Lighting", "lighting", "LIGHTING"),
             ("Compositions", "compositions", "COMPOSITION"),
         ]

         for title, db_key, modal_type in library_items:
             group = QGroupBox(title)
             group.setCheckable(True) # Make it collapsible
             group.setChecked(False) # Start collapsed
             layout = QVBoxLayout()
             group.setLayout(layout)

             # Add Button
             add_btn = QPushButton(f"＋ Add New {title[:-1]}") # Remove 's'
             add_btn.clicked.connect(lambda checked=False, mt=modal_type: self.open_edit_dialog(mt, None)) # Use lambda capture
             layout.addWidget(add_btn)

             # List Widget
             list_widget = QListWidget()
             list_widget.setMaximumHeight(150) # Limit height
             items = self.db_data.get(db_key, {})
             for item_id, item_obj in items.items():
                 list_item = QListWidgetItem(f"{item_obj.name} ({item_id})")
                 list_item.setData(Qt.ItemDataRole.UserRole, item_id) # Store ID in item data
                 list_widget.addItem(list_item)
             layout.addWidget(list_widget)

             # Edit/Delete Buttons
             btn_layout = QHBoxLayout()
             edit_btn = QPushButton("✏️ Edit Selected")
             delete_btn = QPushButton("🗑️ Delete Selected")
             edit_btn.clicked.connect(lambda checked=False, lw=list_widget, mt=modal_type, dk=db_key: self.edit_selected_item(lw, mt, dk))
             delete_btn.clicked.connect(lambda checked=False, lw=list_widget, dk=db_key: self.delete_selected_item(lw, dk))
             btn_layout.addWidget(edit_btn)
             btn_layout.addWidget(delete_btn)
             layout.addLayout(btn_layout)

             library_group_layout.addWidget(group)


    # --- Slots (Event Handlers) ---

    @Slot()
    def save_all_data(self):
        """Saves current data (including SD params) back to SQLite."""
        try:
            db.save_sd_params(self.sd_params)
            for db_key, items in self.db_data.items():
                 if db_key == 'sdParams': continue # Handled above
                 # Find the correct save function based on db_key
                 save_func_name = f"save_{db_key[:-1]}" # e.g., save_actor, save_scene
                 save_func = getattr(db, save_func_name, None)
                 if save_func and callable(save_func):
                     # Need to delete old items not present anymore first - COMPLEX
                     # Simplification: Assume we only add/update for now
                     # A more robust way would load current DB state, diff, then save.
                     print(f"Saving {db_key}...")
                     current_ids_in_db = set(getattr(db, f"load_{db_key}")().keys())
                     current_ids_in_memory = set(items.keys())

                     # Delete items removed from memory
                     ids_to_delete = current_ids_in_db - current_ids_in_memory
                     delete_func_name = f"delete_{db_key[:-1]}"
                     delete_func = getattr(db, delete_func_name, None)
                     if delete_func:
                         for item_id in ids_to_delete:
                             delete_func(item_id)
                             print(f"Deleted {db_key[:-1]} {item_id}")

                     # Save current items
                     for item_obj in items.values():
                         save_func(item_obj) # Call db.save_actor(actor_obj), etc.

                 else:
                     print(f"Warning: No save function found for {db_key}")

            QMessageBox.information(self, "Save", "All data saved to database.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save data: {e}")
            print(f"Save error: {e}")

    @Slot()
    def export_data(self):
        """Exports the current in-memory DB state to a JSON file."""
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Data as JSON", "", "JSON Files (*.json)")
        if not file_path: return

        try:
            data_to_export = {}
            for key, items in self.db_data.items():
                if key == 'sdParams':
                    data_to_export[key] = self.sd_params.__dict__
                else:
                    # Convert dataclasses to dicts
                    data_to_export[key] = {item_id: item_obj.__dict__ for item_id, item_obj in items.items()}

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_export, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "Export", f"Data exported successfully to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export data: {e}")


    @Slot()
    def import_data(self):
        """Imports data from a JSON file, replacing in-memory data."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Data from JSON", "", "JSON Files (*.json)")
        if not file_path: return

        if not QMessageBox.warning(self, "Import Confirmation",
                                   "This will replace all current data. Are you sure?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_json_data = json.load(f)

            # Validate basic structure and convert back to dataclasses
            new_db_data = {}
            model_map = { # Map keys to their dataclass types
                 'actors': Actor, 'scenes': Scene, 'directions': Direction,
                 'costumes': Costume, 'poses': Pose, 'expressions': Expression,
                 'backgrounds': Background, 'lighting': Lighting, 'compositions': Composition,
                 'sdParams': StableDiffusionParams
            }

            all_keys = set(model_map.keys())
            if not all_keys.issubset(imported_json_data.keys()):
                 raise ValueError("Imported JSON is missing required keys.")

            for key, class_type in model_map.items():
                 raw_items = imported_json_data[key]
                 if key == 'sdParams':
                     # Handle SD Params separately
                     new_db_data[key] = StableDiffusionParams(**raw_items)
                 else:
                     loaded_items = {}
                     for item_id, item_dict in raw_items.items():
                         # Handle list fields (tags, roles, etc.) specifically for Scene if needed
                         if class_type == Scene:
                              item_dict['roles'] = [SceneRole(**r) for r in item_dict.get('roles', [])]
                              item_dict['role_directions'] = [RoleDirection(**rd) for rd in item_dict.get('role_directions', [])]
                         if hasattr(class_type, 'tags') and isinstance(item_dict.get('tags'), str): # Handle if tags were saved as string
                              try: item_dict['tags'] = json.loads(item_dict['tags'])
                              except: item_dict['tags'] = []


                         try:
                              loaded_items[item_id] = class_type(**item_dict)
                         except TypeError as te:
                             print(f"Error creating {class_type.__name__} for id {item_id}: {te} \nData: {item_dict}")
                             raise te # Re-raise to signal import failure
                     new_db_data[key] = loaded_items


            # Update state
            self.db_data = new_db_data
            self.sd_params = new_db_data['sdParams']
            # Reset UI elements
            self.current_scene_id = next(iter(self.db_data.get('scenes', {})), None)
            self.actor_assignments = {}
            self.generated_prompts = []
            self.update_ui_after_data_change() # Refresh UI components

            QMessageBox.information(self, "Import", f"Data imported successfully from {file_path}. Consider saving to DB.")

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import data: {e}")
            print(f"Import error: {e}")


    @Slot(int) # Process index change signal
    def on_scene_changed(self, index):
         """Called when the scene dropdown selection changes."""
         scene_list = list(self.db_data.get('scenes', {}).values())
         if 0 <= index < len(scene_list):
             self.current_scene_id = scene_list[index].id
             self.actor_assignments = {} # Reset assignments
             self.generated_prompts = [] # Reset generated prompts
             self.build_role_assignment_ui() # Rebuild role UI
             self.update_prompt_display() # Clear prompt display
         else:
             self.current_scene_id = None # Handle invalid index if necessary
             print("Invalid scene index selected.")


    @Slot(str, str) # role_id, actor_id
    def on_actor_assigned(self, role_id, actor_id):
        """Called when an actor is assigned to a role via dropdown."""
        if actor_id: # Non-empty means a valid actor was selected
             self.actor_assignments[role_id] = actor_id
        else: # Empty string means "-- Select Actor --" was chosen
            if role_id in self.actor_assignments:
                 del self.actor_assignments[role_id] # Remove assignment
        print(f"Assignments updated: {self.actor_assignments}")
        self.generated_prompts = [] # Clear prompts on assignment change
        self.update_prompt_display()


    @Slot()
    def generate_prompts(self):
        """Generates the prompt previews based on current selections."""
        if not self.current_scene_id:
            QMessageBox.warning(self, "Generate", "Please select a scene first.")
            return

        current_scene = self.db_data['scenes'].get(self.current_scene_id)
        if not current_scene:
             QMessageBox.warning(self, "Generate", "Selected scene data not found.")
             return

        # Check assignments
        missing_roles = [r.name_in_scene for r in current_scene.roles if r.id not in self.actor_assignments]
        if missing_roles:
             QMessageBox.warning(self, "Generate", f"Please assign actors to all roles: {', '.join(missing_roles)}")
             return

        # Call the generator logic
        try:
             # Pass the full db_data dictionary
             self.generated_prompts = generate_batch_prompts(self.current_scene_id, self.actor_assignments, self.db_data)
             self.update_prompt_display()
        except Exception as e:
             QMessageBox.critical(self, "Generation Error", f"Error generating prompts: {e}")
             print(f"Prompt generation error: {e}")

    @Slot()
    def execute_generation(self):
        """Creates tasks.json and attempts to run the batch file."""
        if not self.generated_prompts:
            QMessageBox.warning(self, "Execute", "Please generate prompt previews first using the 'Generate Prompt Preview' button.")
            return

        current_scene = self.db_data['scenes'].get(self.current_scene_id)
        if not current_scene:
             QMessageBox.warning(self, "Execute", "Cannot execute without a selected scene.")
             return

        try:
            # Create the tasks structure
            tasks = create_image_generation_tasks(self.generated_prompts, self.sd_params, current_scene)
            if not tasks:
                 QMessageBox.warning(self, "Execute", "No tasks were generated.")
                 return

            # Run the batch file (using the helper function)
            success, message = run_stable_diffusion(tasks)

            if success:
                QMessageBox.information(self, "Execute", message)
            else:
                QMessageBox.critical(self, "Execution Error", message)

        except Exception as e:
            QMessageBox.critical(self, "Execution Error", f"An unexpected error occurred: {e}")
            print(f"Execution error: {e}")


    def update_prompt_display(self):
         """Updates the right panel's text area with generated prompts."""
         if not self.generated_prompts:
             self.prompt_display_area.setPlainText("Press 'Generate Prompt Preview' to see results.")
             return

         display_text = ""
         for p in self.generated_prompts:
             display_text += f"--- {p['name']} ---\n" # Use dict access
             display_text += f"Positive:\n{p['positive']}\n\n"
             display_text += f"Negative:\n{p['negative']}\n"
             display_text += "------------------------------------\n\n"
         self.prompt_display_area.setPlainText(display_text)

    def update_ui_after_data_change(self):
        """Refreshes UI elements that depend on db_data after import or major changes."""
        # Update scene combo box
        self.scene_combo.clear()
        self.scene_combo.addItems([s.name for s in self.db_data.get('scenes', {}).values()])
        # Try to re-select the current scene or default to first
        scene_list = list(self.db_data.get('scenes', {}).values())
        current_scene_index = 0
        if self.current_scene_id:
             try: current_scene_index = [s.id for s in scene_list].index(self.current_scene_id)
             except ValueError: self.current_scene_id = scene_list[0].id if scene_list else None; current_scene_index = 0
        else:
             self.current_scene_id = scene_list[0].id if scene_list else None
        if self.current_scene_id: self.scene_combo.setCurrentIndex(current_scene_index)

        # Rebuild library UI
        self._setup_library_ui()
        # Rebuild role assignment UI for the potentially new scene
        self.build_role_assignment_ui()
        # Update SD param UI elements
        self.sd_steps_spin.setValue(self.sd_params.steps)
        self.sd_sampler_edit.setText(self.sd_params.sampler_name)
        # ... update other SD param widgets ...
        # Clear generated prompts display
        self.generated_prompts = []
        self.update_prompt_display()


    # --- Methods for opening edit dialogs ---
    def open_edit_dialog(self, modal_type: str, item_data: Optional[Any]):
         """Opens the appropriate dialog for editing/adding an item."""
         dialog = None
         # Instantiate the correct dialog based on modal_type
         if modal_type == "ACTOR":
             # Placeholder: Replace with actual dialog class instance
             # dialog = EditActorDialog(item_data, self.db_data, self)
             print(f"TODO: Open EditActorDialog for data: {item_data}")
             pass
         elif modal_type == "SCENE":
              # dialog = EditSceneDialog(item_data, self.db_data, self)
              print(f"TODO: Open EditSceneDialog for data: {item_data}")
              pass
         # ... Add elif for DIRECTION, COSTUME, etc. using respective dialogs ...

         if dialog:
              if dialog.exec(): # Show dialog modally and check if accepted (saved)
                   saved_data = dialog.get_data() # Dialog needs a method to return saved data
                   # Find correct db_key based on modal_type
                   db_key_map = {"ACTOR": "actors", "SCENE": "scenes", "DIRECTION": "directions", ...}
                   db_key = db_key_map.get(modal_type)
                   if db_key and saved_data:
                        self.handleSavePart(db_key, saved_data) # Call generic save
                        self.update_ui_after_data_change() # Refresh lists etc.


    # --- Methods for handling list widget edit/delete ---
    def edit_selected_item(self, list_widget: QListWidget, modal_type: str, db_key: str):
         """Opens the edit dialog for the item selected in the list widget."""
         selected_items = list_widget.selectedItems()
         if not selected_items:
             QMessageBox.warning(self, "Edit", "Please select an item from the list to edit.")
             return
         item_id = selected_items[0].data(Qt.ItemDataRole.UserRole) # Get ID stored in item
         item_data = self.db_data.get(db_key, {}).get(item_id)
         if item_data:
             self.open_edit_dialog(modal_type, item_data)
         else:
             QMessageBox.warning(self, "Edit", "Selected item data not found.")

    def delete_selected_item(self, list_widget: QListWidget, db_key: str):
         """Deletes the item selected in the list widget."""
         selected_items = list_widget.selectedItems()
         if not selected_items:
             QMessageBox.warning(self, "Delete", "Please select an item from the list to delete.")
             return
         item_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
         # Call the generic delete function
         self.handleDeletePart(db_key, item_id)
         # Refresh the UI (specifically the list widget and potentially dependent UI)
         # A simple way is to reload all data and refresh UI, or just update the specific list
         # self.db_data = self._load_all_data() # Reload all might be easiest for now
         # self.update_ui_after_data_change()
         # OR more efficiently: just remove item from list_widget
         list_widget.takeItem(list_widget.row(selected_items[0]))


# --- Main Application Execution ---
# (This part goes into main.py)
# if __name__ == '__main__':
#     app = QApplication(sys.argv)
#     # Optional: Set Fusion style for a more modern look across platforms
#     # app.setStyle('Fusion')
#     db.initialize_db() # Ensure DB exists before loading
#     window = MainWindow()
#     window.show()
#     sys.exit(app.exec())