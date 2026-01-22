import subprocess
import os
import json
import time
import traceback
import threading
from typing import List, Optional
from PySide6.QtCore import QObject, Signal, Slot, QThread

from dataclasses import asdict
from .models import ImageGenerationTask

# --- Paths based on project structure ---
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CLIENT_DIR = os.path.join(_PROJECT_ROOT, "StableDiffusionClient")
_TASK_QUEUE_DIR = os.path.join(_CLIENT_DIR, "data", "tasks_queue")
_START_ALL_BAT = os.path.join(_CLIENT_DIR, "start_all.bat")


class LogReader(QObject):
    """Reads lines from a stream and emits them as signals."""

    new_log_line = Signal(str)

    def __init__(self, stream):
        super().__init__()
        self.stream = stream
        self._is_running = True

    @Slot()
    def run(self):
        """Monitors the stream and emits lines."""
        while self._is_running and self.stream and not self.stream.closed:
            try:
                line = self.stream.readline()
                if line:
                    self.new_log_line.emit(line.strip())
                else:
                    break
            except Exception as e:
                # Log the error and stop
                self.new_log_line.emit(f"LogReader Error: {e}")
                break
        print("LogReader finished.")

    def stop(self):
        self._is_running = False


class BackendManager(QObject):
    """A worker to start/stop and monitor the backend process."""

    log_message = Signal(str)
    finished = Signal(bool, str)

    def __init__(self):
        super().__init__()
        self.process: Optional[subprocess.Popen] = None
        self.log_reader_thread: Optional[QThread] = None
        self.log_reader: Optional[LogReader] = None

    @Slot(str)
    def start_backend(self, output_dir: str):
        if self.process and self.process.poll() is None:
            self.log_message.emit("Backend is already running.")
            self.finished.emit(True, "Already running.")
            return

        try:
            self.log_message.emit("Starting backend process...")

            command = [_START_ALL_BAT]
            if output_dir:
                abs_output_dir = os.path.abspath(output_dir)
                command.extend(["--output_base_dir", abs_output_dir])
                self.log_message.emit(f"  - Using output directory: {abs_output_dir}")

            self.process = subprocess.Popen(
                command,
                cwd=_CLIENT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Redirect stderr to stdout
                text=True,  # Decode stdout/stderr as text
                encoding="utf-8",
                errors="replace",
                shell=False,  # Important for security and argument handling
                creationflags=subprocess.CREATE_NO_WINDOW,  # No new console
            )

            # --- Setup log reader thread ---
            self.log_reader_thread = QThread()
            # Pass the process's stdout to the reader
            self.log_reader = LogReader(self.process.stdout)
            self.log_reader.moveToThread(self.log_reader_thread)

            # Connect signals: reader -> main thread -> GUI
            self.log_reader.new_log_line.connect(self.log_message)
            self.log_reader_thread.started.connect(self.log_reader.run)
            self.log_reader_thread.finished.connect(self.log_reader_thread.deleteLater)

            self.log_reader_thread.start()

            self.log_message.emit(
                f"Backend process started with PID: {self.process.pid}"
            )
            self.finished.emit(True, "Backend process started.")

        except Exception as e:
            error_msg = f"Failed to start backend: {e}"
            self.log_message.emit(error_msg)
            traceback.print_exc()
            self.finished.emit(False, error_msg)

    def stop_backend(self):
        """Stops the log reader and terminates the backend process."""
        if self.log_reader:
            self.log_reader.stop()
        if self.log_reader_thread and self.log_reader_thread.isRunning():
            self.log_reader_thread.quit()
            self.log_reader_thread.wait(2000)

        if self.process and self.process.poll() is None:
            self.log_message.emit("Terminating backend process...")
            try:
                # Terminate the entire process tree (more robust)
                subprocess.run(
                    f"taskkill /F /T /PID {self.process.pid}",
                    check=True,
                    shell=True,
                    capture_output=True,
                )
                self.log_message.emit("Backend process terminated.")
            except Exception as e:
                self.log_message.emit(f"Could not terminate process gracefully: {e}")
                self.process.kill()  # Force kill as a fallback
            self.process = None


class TaskSubmitter(QObject):
    """
    A worker that submits tasks to the queue directory for the dispatcher to pick up.
    """

    log_message = Signal(str)
    finished = Signal(
        bool, str
    )  # Signals once all tasks in the batch are submitted

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

            self.finished.emit(
                True, f"Successfully submitted {num_submitted} tasks to the queue."
            )

        except Exception as e:
            error_msg = f"Error: Failed to submit tasks: {e}"
            self.log_message.emit(error_msg)
            traceback.print_exc()
            self.finished.emit(False, error_msg)


