@echo off
chcp 65001 > nul
setlocal
title Prompt Generator App Launcher

echo "==================================="
echo " Prompt Generator - Python版 起動"
echo "==================================="
echo.

REM --- 0. Python コマンドの確認 ---
echo "Pythonコマンドを確認しています..."
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo "[エラー] Pythonが見つかりません。"
    echo "Pythonをインストールし、PATH環境変数に追加してください。"
    goto :error
)
python --version
echo.

REM --- 1. 仮想環境 (venv) の確認と作成/再作成 ---
echo "仮想環境 (venv) を確認しています..."
set VENV_ACTIVATE_SCRIPT=%~dp0venv\Scripts\activate.bat

if exist "%VENV_ACTIVATE_SCRIPT%" (
    echo "仮想環境 venv (activate.bat) が存在します。"
) else (
    echo "venv が不完全か、存在しません。再作成します..."
    if exist "%~dp0venv" (
        echo "既存の venv フォルダを削除しています..."
        rd /s /q "%~dp0venv"
        if %errorlevel% neq 0 (
            echo "[警告] 既存の venv フォルダの削除に失敗しました。(手動で削除してみてください)"
            REM エラーにはせず、作成を試みる
        )
    )
    echo "新しい仮想環境を作成しています (python -m venv venv)..."
    python -m venv venv
    if %errorlevel% neq 0 (
        echo "[エラー] 仮想環境の作成に失敗しました。"
        goto :error
    )
    if not exist "%VENV_ACTIVATE_SCRIPT%" (
         echo "[エラー] 仮想環境を作成しましたが、activate.bat が見つかりません。"
         goto :error
    )
    echo "仮想環境を再作成しました。"
)
echo.

REM --- 2. 仮想環境のアクティベート ---
echo "仮想環境をアクティベートしています..."
call "%VENV_ACTIVATE_SCRIPT%"
if %errorlevel% neq 0 (
    echo "[エラー] 仮想環境のアクティベートに失敗しました。"
    echo "(バッチファイルの場所やvenvフォルダを確認してください)"
    goto :error
)
echo "アクティベート成功。"
echo.

REM --- 3. 依存関係のインストール ---
echo "必要なライブラリをインストールしています (pip install -r requirements.txt)..."
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo "[エラー] ライブラリのインストールに失敗しました。"
    echo "(requirements.txt が正しいか、ネットワーク接続を確認してください)"
    goto :error
)
echo "ライブラリのインストール完了。"
echo.

REM --- 4. データベースの初期化確認 ---
echo "データベースファイルを確認しています (data\prompt_data.db)..."
set DB_FILE=%~dp0data\prompt_data.db
if not exist "%DB_FILE%" (
    echo "データベースファイルが見つかりません。初期化を実行します..."
    REM ★★★ PYTHONPATH を設定して実行 ★★★
    set "PYTHONPATH=%~dp0;%PYTHONPATH%"
    python -c "from src.database import initialize_db; initialize_db()"
    set "PYTHONPATH=" REM 一時的な設定を解除 (任意だが推奨)
    if %errorlevel% neq 0 (
        echo "[エラー] データベースの初期化に失敗しました。"
        echo "(src/database.py が存在するか確認してください)"
        goto :error
    )
    if not exist "%DB_FILE%" (
        echo "[エラー] 初期化後もデータベースファイルが見つかりません。"
        goto :error
    )
    echo "データベースを初期化しました。"
) else (
    echo "データベースファイルが存在します。"
)

REM --- 5. アプリケーションの起動 ---
echo "アプリケーションを起動します (python main.py)..."
python "%~dp0main.py"

echo.
echo "アプリケーションが終了しました。"
goto :eof

:error
echo.
echo "起動処理中にエラーが発生しました。"
pause
endlocal
exit /b 1

:eof
endlocal