@echo off
REM Nicos Weg A1 生词提取工具 启动脚本
chcp 65001 > nul
cd /d "%~dp0"

REM 优先使用 Microsoft Store 的 Python 3.11（带 tkinter）
set PY=py
where py >nul 2>&1
if errorlevel 1 set PY=python

REM 找到能用的 Python
%PY% -3.11 -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    %PY% -c "import tkinter" >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python with tkinter not found.
        echo Please install Python 3.11 or 3.12 with "tcl/tk and IDLE" option.
        pause
        exit /b 1
    ) else (
        %PY% wort_extractor.py
    )
) else (
    %PY% -3.11 wort_extractor.py
)
