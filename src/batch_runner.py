# src/batch_runner.py
import subprocess
import os
import json
from typing import List
import tempfile  # Use tempfile for intermediate JSON
from .models import ImageGenerationTask
from dataclasses import asdict

# Assume StableDiffusionClient path relative to project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")  # data フォルダのパス
_OUTPUT_JSON_PATH = os.path.join(_DATA_DIR, "tasks.json")  # 固定ファイル名
_CLIENT_DIR = os.path.join(_PROJECT_ROOT, "StableDiffusionClient")
_BAT_PATH = os.path.join(_CLIENT_DIR, "start_all.bat")


def run_stable_diffusion(tasks: List[ImageGenerationTask]) -> tuple[bool, str]:
    """
    Generates tasks.json in the data/ folder (fixed name) and executes start_all.bat.
    Returns (success_status, message).
    """
    # --- 事前チェック ---
    if not os.path.exists(_BAT_PATH):
        return False, f"エラー: バッチファイルが見つかりません: {_BAT_PATH}"
    if not os.path.isdir(_CLIENT_DIR):
        return False, f"エラー: クライアントディレクトリが見つかりません: {_CLIENT_DIR}"

    # --- data ディレクトリが存在するか確認、なければ作成 ---
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        print(f"[DEBUG] data ディレクトリ確認/作成完了: {_DATA_DIR}")
    except OSError as e:
        return False, f"エラー: data ディレクトリの作成に失敗しました: {e}"

    # --- tasks.json を data フォルダに書き出す ---
    try:
        # with open でファイルを確実に閉じる
        with open(_OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
            # dataclass のリストを辞書のリストに変換して書き込み
            tasks_dict_list = [asdict(task) for task in tasks]
            json.dump(
                tasks_dict_list, f, indent=2, ensure_ascii=False
            )  # ensure_ascii=False で日本語をそのまま出力

        print(f"tasks.json を出力しました: {_OUTPUT_JSON_PATH}")

    except Exception as e:
        return False, f"エラー: tasks.json の書き込みに失敗しました: {e}"

    # --- バッチファイルを実行 ---
    # 固定パス (_OUTPUT_JSON_PATH) を引数に渡す
    command = [
        _BAT_PATH,
        "--taskSourceType",
        "json",
        "--localTaskFile",
        _OUTPUT_JSON_PATH,
    ]
    try:
        # Popen で非同期実行 (バッチがバックグラウンドで動く)
        process = subprocess.Popen(
            command, cwd=_CLIENT_DIR, shell=True
        )  # shell=True が Windows では必要になる場合がある
        print(f"[DEBUG] バッチ実行コマンド: {' '.join(command)}")
        # 必要であれば、 process.wait() でバッチ終了を待つことも可能

        return True, f"バッチ処理を開始しました。tasksファイル: {_OUTPUT_JSON_PATH}"

    except Exception as e:
        return False, f"エラー: バッチファイルの実行に失敗しました: {e}"
