@echo off
chcp 65001 > nul
setlocal
title Prompt Generator App Launcher

REM --- Configuration ---
set VENV_DIR=.venv
set PYTHON_SCRIPT=main.py
set REQUIREMENTS_FILE=requirements.txt

echo "==================================="
echo " Prompt Generator - Python版 起動"
echo "==================================="
echo.

REM --- 0. Python コマンドの確認 ---
echo "Pythonコマンドを確認しています..."
call python --version > nul 2>nul
if %errorlevel% neq 0 (
    echo "[エラー] Pythonが見つかりません。"
    echo "Pythonをインストールし、PATH環境変数に追加してください。"
    goto :error
)
echo.

REM --- 1. 仮想環境 (venv) の確認と作成/再作成 ---
echo "仮想環境 (venv) を確認しています..."
set VENV_ACTIVATE_SCRIPT="%VENV_DIR%\Scripts\activate.bat"

if not exist %VENV_ACTIVATE_SCRIPT% (
    echo "venv が不完全か、存在しません。再作成します..."
    if exist "%VENV_DIR%" (
        echo "既存の venv フォルダを削除しています..."
        rd /s /q "%VENV_DIR%"
        if %errorlevel% neq 0 (
            echo "[警告] 既存の venv フォルダの削除に失敗しました。(手動で削除してみてください)"
            REM エラーにはせず、作成を試みる
        )
    )
    echo "新しい仮想環境を作成しています (python -m venv .venv)..."
    call python -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo "[エラー] 仮想環境の作成に失敗しました。"
        goto :error
    )
)

REM --- 2. 仮想環境のアクティベート ---
echo "仮想環境をアクティベートしています..."
call %VENV_ACTIVATE_SCRIPT%
if %errorlevel% neq 0 (
    echo "[エラー] 仮想環境のアクティベートに失敗しました。"
    echo "(バッチファイルの場所やvenvフォルダを確認してください)"
    goto :error
)
echo "アクティベート成功。"
echo.

REM --- 3. 依存関係のインストール ---
echo "必要なライブラリをインストールしています (pip install -r requirements.txt)..."
pip install -r %REQUIREMENTS_FILE%
if %errorlevel% neq 0 (
    echo "[エラー] ライブラリのインストールに失敗しました。"
    echo "(requirements.txt が正しいか、ネットワーク接続を確認してください)"
    goto :error
)
echo "ライブラリのインストール完了。"
echo.

REM --- 5. アプリケーションの起動 ---
echo "アプリケーションを起動します (python main.py)..."
python %PYTHON_SCRIPT%

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