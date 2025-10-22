# main.py
import sys
from PySide6.QtWidgets import QApplication
from src.main_window import MainWindow
from src import database as db  # Import database module

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Optional: Apply a style for better cross-platform look
    # app.setStyle('Fusion')

    # --- Initialize Database ---
    # Ensure the DB file and tables exist before the main window tries to load data
    try:
        db.initialize_db()
    except Exception as e:
        print(f"FATAL: Could not initialize database: {e}")
        # Optionally show a critical error message box here
        sys.exit(1)  # Exit if DB initialization fails

    # --- Create and Show Main Window ---
    try:
        window = MainWindow()
        window.show()
    except Exception as e:
        print(f"FATAL: Could not create main window: {e}")
        # Optionally show a critical error message box here
        sys.exit(1)  # Exit if window creation fails

    # --- Start Event Loop ---
    sys.exit(app.exec())
