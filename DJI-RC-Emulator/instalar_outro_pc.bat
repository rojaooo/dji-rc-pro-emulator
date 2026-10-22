@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Instalador Plug and Play - DJI RC Emulator

:: Solicita permissao de Administrador automaticamente
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Solicitando permissao de Administrador...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================
echo   INSTALACAO PLUG AND PLAY (SEM ZADIG) - CONTROLES DJI
echo ============================================================
echo.

:: 1. Localiza ou instala o Python na mesma janela (sem precisar rodar 2 vezes!)
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
if not defined PY_EXE (
    echo [1/4] Instalando Python 3.12 automaticamente...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    for /d %%D in ("%LocalAppData%\Programs\Python\Python3*" "%ProgramFiles%\Python3*") do (
        if exist "%%~fD\python.exe" set "PY_EXE=%%~fD\python.exe"
    )
)
if not defined PY_EXE set "PY_EXE=python"
echo [1/4] Python pronto: "%PY_EXE%"

:: 2. Instala bibliotecas Python
echo.
echo [2/4] Instalando bibliotecas Python (vgamepad, pyusb, libusb, pyserial)...
"%PY_EXE%" -m pip install --upgrade vgamepad pyusb libusb pyserial

:: 3. Instala o driver ViGEmBus (Controle Xbox 360 Virtual)
echo.
echo [3/4] Instalando driver de Controle Virtual Xbox 360 (ViGEmBus)...
"%PY_EXE%" -c "import importlib.util, pathlib, subprocess; spec = importlib.util.find_spec('vgamepad'); msi = pathlib.Path(spec.origin).parent / 'win/vigem/install/x64/ViGEmBusSetup_x64.msi'; subprocess.run(['msiexec', '/i', str(msi), '/passive', '/norestart'], check=False)"

:: 4. Instala automaticamente os drivers USB assinados da DJI (WinUSB + VCOM) e corrige o Codigo 31 (SEM ZADIG!)
echo.
echo [4/4] Instalando drivers USB da DJI (RC Pro Enterprise / Air 2S RC-N1) sem Zadig...
"%PY_EXE%" -m src.auto_driver

echo.
echo ============================================================
echo   TUDO PRONTO! Iniciando o emulador automaticamente...
echo ============================================================
start "" "%~dp0start.bat"
