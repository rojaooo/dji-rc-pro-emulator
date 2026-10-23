@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DJI RC Emulator - Plug and Play

:: 1. Localiza o Python (no PATH ou nas pastas padrao do Windows)
set "PY_EXE="
where python >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%i in ('where python') do (
        echo "%%i" | findstr /i "WindowsApps" >nul
        if errorlevel 1 if not defined PY_EXE set "PY_EXE=%%i"
    )
)
if not defined PY_EXE (
    for /d %%D in ("%LocalAppData%\Programs\Python\Python3*" "%ProgramFiles%\Python3*") do (
        if exist "%%~fD\python.exe" set "PY_EXE=%%~fD\python.exe"
    )
)

:: 2. Se for um PC novo sem Python, instala automaticamente na mesma execucao (sem precisar abrir 2 vezes!)
if not defined PY_EXE (
    echo [Plug and Play] Python nao encontrado neste PC. Instalando Python 3.12 automaticamente...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    for /d %%D in ("%LocalAppData%\Programs\Python\Python3*" "%ProgramFiles%\Python3*") do (
        if exist "%%~fD\python.exe" set "PY_EXE=%%~fD\python.exe"
    )
)

if not defined PY_EXE set "PY_EXE=python"

:: 3. Verifica se as bibliotecas ja estao instaladas; se nao estiverem, instala na hora e configura os drivers DJI + Xbox + DirectX
"%PY_EXE%" -c "import usb, libusb, serial; import importlib.util; assert importlib.util.find_spec('vgamepad')" >nul 2>&1
if %errorlevel% neq 0 (
    echo [Plug and Play] Primeiro uso neste PC! Instalando bibliotecas, DirectX e drivers automaticamente...
    "%PY_EXE%" -m pip install --upgrade vgamepad pyusb libusb pyserial
    "%PY_EXE%" -m src.auto_driver
) else (
    if not exist "%SystemRoot%\System32\xinput1_3.dll" (
        echo [Plug and Play] Instalando DLLs do DirectX Runtime para o DJI Virtual Flight...
        "%PY_EXE%" -m src.auto_driver
    )
)

echo Iniciando DJI RC Emulator (Plug and Play)...
"%PY_EXE%" tk_main.py
if errorlevel 1 (
    echo.
    echo Tentando reparar bibliotecas e drivers automaticamente...
    "%PY_EXE%" -m pip install --upgrade vgamepad pyusb libusb pyserial
    "%PY_EXE%" -m src.auto_driver
    "%PY_EXE%" tk_main.py
)
