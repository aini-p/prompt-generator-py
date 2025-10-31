# src/batch_runner.py
import subprocess
import os
import json
from typing import List
import tempfile
from .models import ImageGenerationTask  # ★ ImageGenerationBatch のインポートを削除
from dataclasses import asdict

# Assume StableDiffusionClient path relative to project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")  # data フォルダのパス
_OUTPUT_JSON_PATH = os.path.join(_DATA_DIR, "tasks.json")  # ★ 固定パス
_CLIENT_DIR = os.path.join(_PROJECT_ROOT, "StableDiffusionClient")
_BAT_PATH = os.path.join(_CLIENT_DIR, "start_all.bat")


# --- ▼▼▼ run_stable_diffusion 関数を置き換え ▼▼▼ ---
def run_stable_diffusion(tasks: List[ImageGenerationTask]) -> tuple[bool, str]:
    """
    Generates tasks.json (fixed name) in the data/ folder and executes start_all.bat.
    The root object of the JSON will be a list of tasks.
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

    # --- tasks.json を data フォルダに書き出す (固定パス) ---
    try:
        # with open でファイルを確実に閉じる
        with open(_OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
            # ★ dataclass のリストを辞書のリストに変換して書き込み
            # (asdictがネストされた metadata も辞書に変換します)
            tasks_dict_list = [asdict(task) for task in tasks]
            json.dump(
                tasks_dict_list, f, indent=2, ensure_ascii=False
            )  # ★ リストを直接ダンプ

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
        _OUTPUT_JSON_PATH,  # ★ 固定パス
    ]
    try:
        # Popen で非同期実行 (バッチがバックグラウンドで動く)
        process = subprocess.Popen(command, cwd=_CLIENT_DIR, shell=True)
        print(f"[DEBUG] バッチ実行コマンド: {' '.join(command)}")

        return True, f"バッチ処理を開始しました。tasksファイル: {_OUTPUT_JSON_PATH}"

    except Exception as e:
        return False, f"エラー: バッチファイルの実行に失敗しました: {e}"


# --- ▲▲▲ 置き換えここまで ▲▲▲ ---
