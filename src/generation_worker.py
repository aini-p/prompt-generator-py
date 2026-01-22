import subprocess
import os
import json
import time
import traceback
from typing import List, Optional
from PySide6.QtCore import QObject, Signal, Slot
from dataclasses import asdict
from .models import ImageGenerationTask

# --- Paths based on project structure ---
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CLIENT_DIR = os.path.join(_PROJECT_ROOT, "StableDiffusionClient")
# The new task queue directory, as defined in GenImage.py
_TASK_QUEUE_DIR = os.path.join(_CLIENT_DIR, "data", "tasks_queue")
_START_ALL_BAT = os.path.join(_CLIENT_DIR, "start_all.bat")


class BackendManager(QObject):
    """A simple worker to start or stop the backend process."""
    log_message = Signal(str)
    finished = Signal(bool, str)

    def __init__(self):
        super().__init__()
        self.process: Optional[subprocess.Popen] = None

    @Slot(str)
    def start_backend(self, output_dir: str):
        if self.process and self.process.poll() is None:
            self.log_message.emit("Backend is already running.")
            self.finished.emit(True, "Already running.")
            return

        try:
            self.log_message.emit("Starting backend process (start_all.bat)...")

            command = [_START_ALL_BAT]
            if output_dir:
                # Ensure the path is absolute and correctly formatted for the shell.
                abs_output_dir = os.path.abspath(output_dir)
                command.extend(["--output_base_dir", abs_output_dir])
                self.log_message.emit(f"  - Using output directory: {abs_output_dir}")

            # We run start_all.bat which now contains the persistent dispatcher
            self.process = subprocess.Popen(
                command,
                cwd=_CLIENT_DIR,
                shell=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            self.log_message.emit(f"Backend process started with PID: {self.process.pid}")
            self.finished.emit(True, "Backend process started.")
        except Exception as e:
            error_msg = f"Failed to start backend: {e}"
            self.log_message.emit(error_msg)
            traceback.print_exc()
            self.finished.emit(False, error_msg)

    def stop_backend(self):
        # This is a bit more complex as it might require terminating a process tree.
        # For now, we leave it to the user to close the console window.
        if self.process:
            self.log_message.emit("Requesting backend termination (please close the console window).")
            # self.process.terminate() # This might not be enough
            self.process = None


class TaskSubmitter(QObject):
    """
    A worker that submits tasks to the queue directory for the dispatcher to pick up.
    """
    log_message = Signal(str)
    finished = Signal(bool, str) # Signals once all tasks in the batch are submitted

    @Slot(list)
    def submit_tasks(self, tasks: List[ImageGenerationTask]):
        """
        Takes a list of tasks and writes each one as a separate JSON file
        into the shared task queue directory.
        """
        if not tasks:
            self.finished.emit(False, "No tasks to submit.")
            return

        try:
            os.makedirs(_TASK_QUEUE_DIR, exist_ok=True)
            num_submitted = 0
            for task in tasks:
                task_dict = asdict(task)
                timestamp = int(time.time() * 1000)
                # Generate a unique filename
                filename = f"task_{timestamp}_{num_submitted}.json"
                filepath = os.path.join(_TASK_QUEUE_DIR, filename)
                
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(task_dict, f, indent=2, ensure_ascii=False)
                
                self.log_message.emit(f"Submitted task to queue: {filename}")
                num_submitted += 1
            
            self.finished.emit(True, f"Successfully submitted {num_submitted} tasks to the queue.")

        except Exception as e:
            error_msg = f"Error: Failed to submit tasks: {e}"
            self.log_message.emit(error_msg)
            traceback.print_exc()
            self.finished.emit(False, error_msg)

