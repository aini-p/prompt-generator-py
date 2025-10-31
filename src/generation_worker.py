# src/generation_worker.py
import subprocess
import os
import json
import re
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
_OUTPUT_JSON_PATH = os.path.join(_DATA_DIR, "tasks.json")  # 固定パス


class GenerationWorker(QObject):
    """
    GenImage.py を別スレッドで実行し、進捗をシグナルで送信するワーカー
    """

    # --- 2. シグナル定義 ---
    # (最大値, 現在値, テキスト)
    progress_updated = Signal(int, int, str)
    # (成功フラグ, メッセージ)
    finished = Signal(bool, str)
    # (デバッグ用の生ログ)
    log_message = Signal(str)

    def __init__(self):
        super().__init__()
        self.process: Optional[subprocess.Popen] = None

    def _write_tasks_json(self, tasks: List[ImageGenerationTask]) -> bool:
        """
        tasks.json (固定パス) にタスクリストを書き込む。
        (batch_runner.py のロジックを移植)
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

    @Slot(list)
    def start_generation(self, tasks: List[ImageGenerationTask]):
        """
        スレッド開始時に呼び出されるメインの実行関数
        """
        if not tasks:
            self.finished.emit(False, "生成するタスクがありません。")
            return

        # --- 3. tasks.json の書き込み ---
        if not self._write_tasks_json(tasks):
            self.finished.emit(False, "tasks.json の書き込みに失敗しました。")
            return

        # --- 4. 実行コマンドの構築 ---
        # GenImage.py が StableDiffusionClient フォルダにあることを前提
        if not os.path.exists(_FORGE_VENV_PYTHON):
            self.finished.emit(
                False,
                f"エラー: ForgeのPython実行ファイルが見つかりません。\n{_FORGE_VENV_PYTHON}",
            )
            return
        if not os.path.exists(_GENIMAGE_PY):
            self.finished.emit(
                False, f"エラー: GenImage.py が見つかりません。\n{_GENIMAGE_PY}"
            )
            return

        command = [
            _FORGE_VENV_PYTHON,
            _GENIMAGE_PY,
            "--taskSourceType",
            "json",
            "--localTaskFile",
            _OUTPUT_JSON_PATH,
        ]

        self.log_message.emit(f"コマンド実行: {' '.join(command)}")
        self.log_message.emit(f"作業ディレクトリ: {_CLIENT_DIR}")

        total_tasks = len(tasks)
        self.progress_updated.emit(total_tasks, 0, "Generation Started...")

        try:
            # --- 5. サブプロセスの実行 ---
            self.process = subprocess.Popen(
                command,
                cwd=_CLIENT_DIR,  # GenImage.py のカレントディレクトリ
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # エラーも標準出力にマージ
                text=True,
                encoding="utf-8",
                errors="ignore",  # エンコーディングエラーを無視
                bufsize=1,  # ラインバッファリング
                shell=False,  # venv の python を直接呼ぶので shell=False でOK
            )

            # --- 6. 標準出力のリアルタイム監視 ---
            if self.process.stdout:
                for line in iter(self.process.stdout.readline, ""):
                    if not line:
                        break
                    line = line.strip()
                    if line:
                        self.log_message.emit(line)  # 生ログを送信

                        # 進捗をパースしてシグナルを送信
                        # GenImage.py の出力 "--- タスク X/Y を処理中 ---" を探す
                        match = re.search(r"--- タスク (\d+)/(\d+) を処理中 ---", line)
                        if match:
                            current = int(match.group(1))
                            total = int(match.group(2))
                            # 処理 *開始* 時点なので、(current - 1) が完了済み
                            self.progress_updated.emit(
                                total,
                                current - 1,
                                f"Processing Task {current}/{total}...",
                            )

                        # GenImage.py の出力 "[進捗: X/Y | ... | 予想残り時間: ...]" を探す
                        match_progress = re.search(r"\[進捗: (\d+)/(\d+)", line)
                        if match_progress:
                            current = int(match_progress.group(1))
                            total = int(match_progress.group(2))
                            self.progress_updated.emit(
                                total, current, f"Completed Task {current}/{total}"
                            )

            self.process.stdout.close()
            return_code = self.process.wait()

            # --- 7. 終了処理 ---
            if return_code == 0:
                self.progress_updated.emit(
                    total_tasks, total_tasks, "Generation Complete."
                )
                self.finished.emit(True, "バッチ処理が正常に完了しました。")
            elif return_code == 5:
                # GenImage.py のタイムアウトエラー
                self.finished.emit(
                    False,
                    "エラー: APIリクエストがタイムアウトしました。Forgeの再起動が必要かもしれません。",
                )
            else:
                self.finished.emit(
                    False,
                    f"エラー: GenImage.py が異常終了しました (コード: {return_code})。",
                )

        except Exception as e:
            self.log_message.emit(f"ワーカー実行中に致命的なエラーが発生しました: {e}")
            traceback.print_exc()
            self.finished.emit(False, f"ワーカー実行エラー: {e}")
        finally:
            self.process = None
