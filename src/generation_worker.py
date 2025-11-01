# src/generation_worker.py
import subprocess
import os
import json
import re
import requests
import time
import traceback
from typing import List, Optional
from PySide6.QtCore import QObject, Signal, Slot
from dataclasses import asdict
from .models import ImageGenerationTask

# --- 1. パス設定 (プロジェクト構造に基づき) ---
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CLIENT_DIR = os.path.join(_PROJECT_ROOT, "StableDiffusionClient")
_FORGE_VENV_PYTHON = os.path.join(
    _CLIENT_DIR, "stable-diffusion-webui-forge", "venv", "Scripts", "python.exe"
)
_GENIMAGE_PY = os.path.join(_CLIENT_DIR, "GenImage.py")
_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")
_OUTPUT_JSON_PATH = os.path.join(_DATA_DIR, "tasks.json")

# --- Forge起動関連のパス ---
_CONFIG_FILE = os.path.join(_CLIENT_DIR, "config.json")
_LAUNCH_FORGE_BAT = os.path.join(_CLIENT_DIR, "_launch_forge_if_needed.bat")
_FORGE_DIR_PATH = os.path.join(_CLIENT_DIR, "stable-diffusion-webui-forge")


class GenerationWorker(QObject):
    """
    GenImage.py を別スレッドで実行し、進捗をシグナルで送信するワーカー
    """

    # --- 2. シグナル定義 ---
    progress_updated = Signal(int, int, str)
    finished = Signal(bool, str)
    log_message = Signal(str)

    def __init__(self):
        super().__init__()
        self.process: Optional[subprocess.Popen] = None
        self.api_url: str = ""

    def _write_tasks_json(self, tasks: List[ImageGenerationTask]) -> bool:
        """
        tasks.json (固定パス) にタスクリストを書き込む。
        """
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            with open(_OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
                tasks_dict_list = [asdict(task) for task in tasks]
                json.dump(tasks_dict_list, f, indent=2, ensure_ascii=False)
            self.log_message.emit(f"tasks.json を出力しました: {_OUTPUT_JSON_PATH}")
            return True
        except Exception as e:
            self.log_message.emit(f"エラー: tasks.json の書き込みに失敗しました: {e}")
            return False

    def _check_api_ready(self) -> bool:
        """config.jsonからURLを読み込み、APIが応答するか確認する"""
        if not self.api_url:
            self.log_message.emit("API URLが未設定です。config.jsonを確認します。")
            try:
                if not os.path.exists(_CONFIG_FILE):
                    self.log_message.emit(
                        f"エラー: config.json が見つかりません。\n{_CONFIG_FILE}"
                    )
                    return False
                with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                self.api_url = config.get("stableDiffusionURL")
                if not self.api_url:
                    self.log_message.emit(
                        "エラー: config.json に stableDiffusionURL が設定されていません。"
                    )
                    return False
            except Exception as e:
                self.log_message.emit(
                    f"エラー: config.json の読み込みに失敗しました: {e}"
                )
                return False

        try:
            self.log_message.emit(f"Checking API status at: {self.api_url}")
            response = requests.get(f"{self.api_url}/", timeout=3)
            if response.status_code == 200 or response.status_code == 404:
                self.log_message.emit(
                    f"Forge API 接続成功 (Status: {response.status_code}): {self.api_url}"
                )
                return True
            else:
                self.log_message.emit(
                    f"Forge API 接続失敗 (Status: {response.status_code}): {self.api_url}"
                )
                return False
        except requests.exceptions.ConnectionError:
            self.log_message.emit(
                f"Forge API に接続できません (ConnectionError): {self.api_url}"
            )
            return False
        except requests.exceptions.Timeout:
            self.log_message.emit(f"Forge API がタイムアウトしました: {self.api_url}")
            return False
        except Exception as e:
            self.log_message.emit(f"Forge API 確認中にエラー: {e}")
            return False

    def _launch_forge(self) -> bool:
        """
        _launch_forge_if_needed.bat を実行してForgeを起動する。
        バッチファイルの終了（＝API準備完了）を待つ。
        """
        if not os.path.exists(_LAUNCH_FORGE_BAT):
            self.log_message.emit(
                f"エラー: 起動バッチファイルが見つかりません。\n{_LAUNCH_FORGE_BAT}"
            )
            return False

        self.log_message.emit("Forge (Stable Diffusion) の起動を開始します...")

        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)

            if not self.api_url:
                self.api_url = config.get("stableDiffusionURL")
                if not self.api_url:
                    self.log_message.emit(
                        "エラー: config.json に stableDiffusionURL がありません。"
                    )
                    return False

            launch_args = config.get("launchArgs", {})
            launch_options_list = []
            for k, v in launch_args.items():
                if isinstance(v, bool) and v:
                    launch_options_list.append(f"--{k}")
                elif isinstance(v, str) and v:
                    launch_options_list.append(f'--{k} "{v}"')

            launch_options_str = " ".join(launch_options_list)

        except Exception as e:
            self.log_message.emit(
                f"Forge 起動エラー: config.json の読み込みに失敗: {e}"
            )
            return False

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["API_URL"] = self.api_url
        env["FORGE_DIR"] = _FORGE_DIR_PATH
        env["FORGE_WINDOW_TITLE"] = "Stable Diffusion Forge"
        env["LAUNCH_OPTIONS"] = launch_options_str
        env["CHECK_TIMEOUT"] = "600"
        env["CHECK_INTERVAL"] = "5"

        self.log_message.emit(f"Setting ENV: API_URL={env['API_URL']}")
        self.log_message.emit(f"Setting ENV: FORGE_DIR={env['FORGE_DIR']}")
        self.log_message.emit(f"Setting ENV: LAUNCH_OPTIONS={env['LAUNCH_OPTIONS']}")
        self.log_message.emit(f"Setting ENV: CHECK_TIMEOUT={env['CHECK_TIMEOUT']}")
        self.log_message.emit(f"Setting ENV: CHECK_INTERVAL={env['CHECK_INTERVAL']}")

        try:
            self.process = subprocess.Popen(
                [_LAUNCH_FORGE_BAT],
                cwd=_CLIENT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
                bufsize=1,
                shell=True,
                env=env,
            )

            if self.process.stdout:
                for line in iter(self.process.stdout.readline, ""):
                    if not line:
                        break
                    line = line.strip()
                    if line:
                        self.log_message.emit(f"[Forge Launcher] {line}")

            self.process.stdout.close()
            return_code = self.process.wait()

            if return_code == 0:
                self.log_message.emit(
                    "Forge 起動バッチが正常に終了しました。APIを再確認します。"
                )
                time.sleep(5)
                return self._check_api_ready()
            else:
                self.log_message.emit(
                    f"エラー: Forge 起動バッチが異常終了しました (コード: {return_code})。"
                )
                return False

        except Exception as e:
            self.log_message.emit(f"Forge起動プロセス実行中にエラー: {e}")
            return False
        finally:
            self.process = None

    # --- ▼▼▼ _run_genimage を修正 (base_dir を引数に追加し、command に反映) ▼▼▼ ---
    def _run_genimage(self, tasks: List[ImageGenerationTask], base_dir: str) -> bool:
        """
        GenImage.py を実行し、進捗を監視する。
        """
        if not os.path.exists(_FORGE_VENV_PYTHON):
            self.log_message.emit(
                f"エラー: ForgeのPython実行ファイルが見つかりません。\n{_FORGE_VENV_PYTHON}"
            )
            return False
        if not os.path.exists(_GENIMAGE_PY):
            self.log_message.emit(
                f"エラー: GenImage.py が見つかりません。\n{_GENIMAGE_PY}"
            )
            return False

        # --- コマンド構築 ---
        command = [
            _FORGE_VENV_PYTHON,
            _GENIMAGE_PY,
            "--taskSourceType",
            "json",
            "--localTaskFile",
            _OUTPUT_JSON_PATH,
            "--jpeg_metadata_only",  # ★ jpeg_metadata_only を True で渡す
        ]

        # ★ base_dir が指定されている場合のみ --output_base_dir を追加
        if base_dir:
            # config.json のパスはプロジェクトルートからの相対パス
            # GenImage.py (in StableDiffusionClient) から見ても正しく解決できるよう
            # プロジェクトルートからの相対パスとして渡す
            # (GenImage.py側で os.path.abspath を使って解決する想定)

            # _PROJECT_ROOT (srcの親) からの相対パスを渡す
            # (os.path.join(_PROJECT_ROOT, base_dir) で絶対パスにしても良い)
            command.extend(["--output_base_dir", base_dir])

        self.log_message.emit(f"GenImage.py 実行: {' '.join(command)}")

        total_tasks = len(tasks)
        self.progress_updated.emit(total_tasks, 0, "Image Generation Started...")

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        try:
            self.process = subprocess.Popen(
                command,
                cwd=_CLIENT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
                bufsize=1,
                shell=False,
                env=env,
            )

            if self.process.stdout:
                for line in iter(self.process.stdout.readline, ""):
                    if not line:
                        break
                    line = line.strip()
                    if line:
                        self.log_message.emit(line)

                        match = re.search(r"--- タスク (\d+)/(\d+) を処理中 ---", line)
                        if match:
                            current = int(match.group(1))
                            total = int(match.group(2))
                            self.progress_updated.emit(
                                total,
                                current - 1,
                                f"Processing Task {current}/{total}...",
                            )

                        match_progress = re.search(r"\[進捗: (\d+)/(\d+)", line)
                        if match_progress:
                            current = int(match_progress.group(1))
                            total = int(match_progress.group(2))
                            self.progress_updated.emit(
                                total, current, f"Completed Task {current}/{total}"
                            )

            self.process.stdout.close()
            return_code = self.process.wait()

            if return_code == 0:
                self.progress_updated.emit(
                    total_tasks, total_tasks, "Generation Complete."
                )
                self.log_message.emit("GenImage.py が正常に完了しました。")
                return True
            elif return_code == 5:
                self.log_message.emit("エラー: GenImage.py がタイムアウトしました。")
                return False
            else:
                self.log_message.emit(
                    f"エラー: GenImage.py が異常終了しました (コード: {return_code})。"
                )
                return False

        except Exception as e:
            self.log_message.emit(f"GenImage.py 実行中にエラー: {e}")
            traceback.print_exc()
            return False
        finally:
            self.process = None

    # --- ▲▲▲ 修正ここまで ▲▲▲ ---

    # --- ▼▼▼ start_generation を修正 (Slotの引数を変更し、_run_genimage に base_dir を渡す) ▼▼▼ ---
    @Slot(list, str)
    def start_generation(self, tasks: List[ImageGenerationTask], base_dir: str):
        """
        スレッド開始時に呼び出されるメインの実行関数
        1. Forge API確認
        2. (必要なら) Forge起動
        3. tasks.json 書き込み
        4. GenImage.py 実行
        """
        if not tasks:
            self.finished.emit(False, "生成するタスクがありません。")
            return

        try:
            # 1. Forge API確認
            self.log_message.emit("Checking Forge API status...")
            if not self._check_api_ready():
                self.log_message.emit(
                    "Forge API not responding. Attempting to launch..."
                )
                # 2. Forge起動
                if not self._launch_forge():
                    self.finished.emit(False, "Forgeの起動に失敗しました。")
                    return
                self.log_message.emit("Forge launch successful.")

            # 3. tasks.json 書き込み
            if not self._write_tasks_json(tasks):
                self.finished.emit(False, "tasks.json の書き込みに失敗しました。")
                return

            # 4. GenImage.py 実行
            if self._run_genimage(tasks, base_dir):  # ★ base_dir を渡す
                self.finished.emit(True, "バッチ処理が正常に完了しました。")
            else:
                self.finished.emit(False, "画像生成プロセスでエラーが発生しました。")

        except Exception as e:
            self.log_message.emit(f"ワーカー実行中に致命的なエラーが発生しました: {e}")
            traceback.print_exc()
            self.finished.emit(False, f"ワーカー実行エラー: {e}")

    # --- ▲▲▲ 修正ここまで ▲▲▲ ---
