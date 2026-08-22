@echo off
title Video Watermark Remover Pro v5.0 (Instant 1000 FPS)
cd /d "%~dp0"

:: 1. Auto-discover FFmpeg across all common Windows locations
if exist "%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin" (
    set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin;%PATH%"
)
if exist "C:\ffmpeg\bin" (
    set "PATH=C:\ffmpeg\bin;%PATH%"
)
if exist "C:\Program Files\ffmpeg\bin" (
    set "PATH=C:\Program Files\ffmpeg\bin;%PATH%"
)

:: 2. Auto-setup lightweight Virtual Environment if missing on a new/low-spec PC
if not exist "venv\Scripts\activate.bat" (
    echo ============================================================
    echo   First-time Setup: Creating lightweight environment...
    echo ============================================================
    python -m venv venv
    call "venv\Scripts\activate.bat"
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    echo Setup complete!
) else (
    call "venv\Scripts\activate.bat"
)

:: 3. Launch GUI
python "%~dp0gui_app.py" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with code %ERRORLEVEL%
    pause
)
