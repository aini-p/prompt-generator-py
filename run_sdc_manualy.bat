@echo off
setlocal
title Run SD Client with tasks.json

echo "==================================="
echo " StableDiffusionClient 起動 (tasks.json)"
echo "==================================="
echo.

REM --- 1. パスの設定 ---
REM %~dp0 はこのバッチファイルがあるディレクトリのパス (末尾に \ が付く)
set "BASE_DIR=%~dp0"
set "CLIENT_DIR=%BASE_DIR%StableDiffusionClient"
set "BAT_PATH=%CLIENT_DIR%\start_all.bat"
set "JSON_PATH=%BASE_DIR%data\tasks.json"

REM --- 2. ファイルの存在確認 ---
if not exist "%BAT_PATH%" (
    echo "[エラー] start_all.bat が見つかりません。"
    echo "パス: %BAT_PATH%"
    goto :error_no_popd
)
if not exist "%JSON_PATH%" (
    echo "[エラー] tasks.json が見つかりません。"
    echo "パス: %JSON_PATH%"
    echo "先に main.py のGUIから [Execute Image Generation] または [Run Batch] を実行して"
    echo "tasks.json を生成してください。"
    goto :error_no_popd
)

REM --- 3. クライアントの実行 ---
echo "StableDiffusionClient を起動します..."
echo "作業ディレクトリ: %CLIENT_DIR%"
echo "タスクファイル: %JSON_PATH%"
echo.

REM pushd で作業ディレクトリを StableDiffusionClient に移動
pushd "%CLIENT_DIR%"
if %errorlevel% neq 0 (
    echo "[エラー] クライアントディレクトリへの移動に失敗しました。"
    echo "パス: %CLIENT_DIR%"
    goto :error_no_popd
)

REM start_all.bat を実行
call "%BAT_PATH%" --taskSourceType json --localTaskFile "%JSON_PATH%"

REM popd で元のディレクトリに戻る
popd

echo.
echo "クライアントの起動処理が完了しました。"
goto :eof

:error_no_popd
echo.
echo "エラーが発生しました。"
pause
endlocal
exit /b 1

:eof
endlocal