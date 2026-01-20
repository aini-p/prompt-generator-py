
import subprocess
import os
import json
import re
import traceback
from typing import List, Optional
from PySide6.QtCore import QObject, Signal, Slot
from dataclasses import asdict
from .models import ImageGenerationTask

# --- Paths based on project structure ---
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CLIENT_DIR = os.path.join(_PROJECT_ROOT, "StableDiffusionClient")
_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")
_OUTPUT_JSON_PATH = os.path.join(_DATA_DIR, "tasks.json")
_START_ALL_BAT = os.path.join(_CLIENT_DIR, "start_all.bat")


class GenerationWorker(QObject):
    """
    A worker that runs the entire Stable Diffusion client process in a separate thread
    and reports progress via signals.
    """
    progress_updated = Signal(int, int, str)
    finished = Signal(bool, str)
    log_message = Signal(str)

    def __init__(self):
        super().__init__()
        self.process: Optional[subprocess.Popen] = None

    def _write_tasks_json(self, tasks: List[ImageGenerationTask]) -> bool:
        """Writes the list of tasks to the tasks.json file."""
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            tasks_dict_list = [asdict(task) for task in tasks]
            with open(_OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(tasks_dict_list, f, indent=2, ensure_ascii=False)
            self.log_message.emit(f"Successfully wrote tasks to: {_OUTPUT_JSON_PATH}")
            return True
        except Exception as e:
            self.log_message.emit(f"Error: Failed to write tasks.json: {e}")
            return False

    @Slot(list, str)
    def start_generation(self, tasks: List[ImageGenerationTask], base_dir: str):
        """
        The main execution function for the worker thread.
        It prepares the tasks and then runs the main `start_all.bat` script.
        """
        if not tasks:
            self.finished.emit(False, "No tasks to generate.")
            return

        try:
            # 1. Prepare the tasks.json file
            if not self._write_tasks_json(tasks):
                self.finished.emit(False, "Failed to write tasks.json.")
                return

            # 2. Prepare and execute the main batch script
            if not os.path.exists(_START_ALL_BAT):
                self.log_message.emit(f"Error: Main batch file not found at {_START_ALL_BAT}")
                self.finished.emit(False, "Main batch file not found.")
                return

            # Construct the command to run the batch script.
            # We pass the task source info so GenImage.py knows what to do.
            command = [
                _START_ALL_BAT,
                "--taskSourceType", "json",
                "--localTaskFile", _OUTPUT_JSON_PATH
            ]
            
            # This logic is now handled inside GenImage.py based on output_base_dir
            # if base_dir:
            #     abs_base_dir = os.path.abspath(os.path.join(_PROJECT_ROOT, base_dir))
            #     command.extend(["--output_base_dir", abs_base_dir])

            self.log_message.emit(f"Executing main process: {' '.join(command)}")

            total_tasks = len(tasks)
            self.progress_updated.emit(total_tasks, 0, "Image Generation Process Started...")

            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"

            self.process = subprocess.Popen(
                command,
                cwd=_CLIENT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
                bufsize=1,
                shell=True, # Batch files need shell=True
                env=env,
            )

            # Read output line by line and emit logs
            if self.process.stdout:
                for line in iter(self.process.stdout.readline, ""):
                    if not line:
                        break
                    line = line.strip()
                    if line:
                        self.log_message.emit(line)
                        
                        # --- Parse progress from GenImage.py output ---
                        match_task_start = re.search(r"--- Task (\d+)/(\d+) starting ---", line)
                        if match_task_start:
                            current = int(match_task_start.group(1))
                            total = int(match_task_start.group(2))
                            self.progress_updated.emit(total, current - 1, f"Processing Task {current}/{total}...")
                        
                        match_task_finish = re.search(r"--- Task (\d+) on .* finished successfully ---", line)
                        if match_task_finish:
                            current = int(match_task_finish.group(1))
                            self.progress_updated.emit(total_tasks, current, f"Completed Task {current}/{total_tasks}")


            self.process.stdout.close()
            return_code = self.process.wait()

            if return_code == 0:
                self.progress_updated.emit(total_tasks, total_tasks, "Generation Complete.")
                self.log_message.emit("Main process completed successfully.")
                self.finished.emit(True, "Batch process completed successfully.")
            elif return_code == 5:
                # This error code is used to signal a timeout from GenImage.py
                self.log_message.emit("Error: The generation process timed out and requires a restart.")
                self.finished.emit(False, "Process timed out. Please try again.")
            else:
                self.log_message.emit(f"Error: Main process exited with error code {return_code}.")
                self.finished.emit(False, f"Process failed with error code: {return_code}.")

        except Exception as e:
            self.log_message.emit(f"A critical error occurred in the worker: {e}")
            traceback.print_exc()
            self.finished.emit(False, f"Worker error: {e}")
        finally:
            self.process = None

