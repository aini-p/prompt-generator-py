@echo off
setlocal
title Prompt Generator App Launcher

echo ===================================
echo  Prompt Generator - Python版 起動
echo ===================================
echo.

REM --- 0. Python コマンドの確認 ---
echo Pythonコマンドを確認しています...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [エラー] Pythonが見つかりません。
    echo Pythonをインストールし、PATH環境変数に追加してください。
    goto :error
)
python --version
echo.

REM --- 1. 仮想環境 (venv) の確認と作成 ---
echo 仮想環境 (venv) を確認しています...
if not exist venv (
    echo venv が見つかりません。新規作成します...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [エラー] 仮想環境の作成に失敗しました。
        goto :error
    )
    echo 仮想環境を作成しました。
) else (
    echo 仮想環境 venv が存在します。
)
echo.

REM --- 2. 仮想環境のアクティベート ---
echo 仮想環境をアクティベートしています...
call .\venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [エラー] 仮想環境のアクティベートに失敗しました。
    echo (コマンドプロンプトやPowerShellの実行ポリシーを確認してください)
    goto :error
)
echo アクティベート成功。
echo.

REM --- 3. 依存関係のインストール ---
echo 必要なライブラリをインストールしています (pip install -r requirements.txt)...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [エラー] ライブラリのインストールに失敗しました。
    echo (requirements.txt が正しいか、ネットワーク接続を確認してください)
    goto :error
)
echo ライブラリのインストール完了。
echo.

REM --- 4. データベースの初期化確認 ---
echo データベースファイルを確認しています (data\prompt_data.db)...
REM src\database.py で定義されている相対パスに基づいて確認
set DB_FILE=data\prompt_data.db
if not exist %DB_FILE% (
    echo データベースファイルが見つかりません。初期化を実行します...
    REM database.py 内の initialize_db 関数を呼び出す
    python -c "import sys; sys.path.insert(0, '.'); from src.database import initialize_db; initialize_db()"
    if %errorlevel% neq 0 (
        echo [エラー] データベースの初期化に失敗しました。
        goto :error
    )
    if not exist %DB_FILE% (
        echo [エラー] 初期化後もデータベースファイルが見つかりません。
        goto :error
    )
    echo データベースを初期化しました。
) else (
    echo データベースファイルが存在します。
)
echo.

REM --- 5. アプリケーションの起動 ---
echo アプリケーションを起動します (python main.py)...
python main.py

echo.
echo アプリケーションが終了しました。
goto :eof

:error
echo.
echo 起動処理中にエラーが発生しました。
pause
endlocal
exit /b 1

:eof
endlocal