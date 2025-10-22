# src/batch_runner.py
import subprocess
import os
import json
from typing import List
import tempfile  # Use tempfile for intermediate JSON
from .models import ImageGenerationTask

# Assume StableDiffusionClient path relative to project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CLIENT_DIR = os.path.join(_PROJECT_ROOT, "StableDiffusionClient")
_BAT_PATH = os.path.join(_CLIENT_DIR, "start_all.bat")


def run_stable_diffusion(tasks: List[ImageGenerationTask]) -> tuple[bool, str]:
    """
    Generates tasks.json in a temporary file and executes start_all.bat.
    Returns (success_status, message).
    """
    if not os.path.exists(_BAT_PATH):
        return False, f"Error: Batch file not found at {_BAT_PATH}"
    if not os.path.isdir(_CLIENT_DIR):
        return False, f"Error: Client directory not found at {_CLIENT_DIR}"

    # Use tempfile for secure and automatic cleanup
    try:
        # Create a temporary file that is deleted automatically on close
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as temp_f:
            json_path = temp_f.name
            # Convert list of dataclasses to list of dicts for json.dump
            tasks_dict_list = [task.__dict__ for task in tasks]
            json.dump(tasks_dict_list, temp_f, indent=2)

        print(f"Temporary tasks file created at: {json_path}")  # Log temp file path

        command = [_BAT_PATH, "--taskSourceType", "json", "--localTaskFile", json_path]

        # Execute the batch file
        # Use Popen for non-blocking execution or run for blocking with output capture
        process = subprocess.Popen(
            command, cwd=_CLIENT_DIR, shell=True
        )  # Use shell=True if needed on Windows
        # Optional: Wait for completion and check return code if needed
        # stdout, stderr = process.communicate()
        # return_code = process.returncode
        # if return_code != 0:
        #    return False, f"Batch execution failed with code {return_code}. Error: {stderr.decode() if stderr else 'N/A'}"

        # Assuming Popen starts it successfully in the background
        return (
            True,
            f"Batch process started successfully. Tasks file: {os.path.basename(json_path)}",
        )

    except Exception as e:
        return False, f"Error during batch execution: {e}"
    # No finally block needed for deleting temp_f if delete=True was used correctly with 'with'
