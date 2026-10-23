@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Instalador DJI Virtual Flight (PC)

set "SIM_EXE=1661500931886-DJI Virtual Flight.exe"
set "DJI_PAGE=https://www.dji.com/br/downloads/products/dji-virtual-flight#other_software"

:: Verifica se o arquivo .exe existe e se tem mais de 100 MB (evita arquivo corrompido de 1 KB)
if exist "%SIM_EXE%" (
    for %%A in ("%SIM_EXE%") do (
        if %%~zA GTR 100000000 (
            echo Iniciando instalador local do DJI Virtual Flight...
            start "" "%SIM_EXE%"
            exit /b
        ) else (
            echo Removendo arquivo incompleto/corrompido de 1 KB...
            del /f /q "%SIM_EXE%" >nul 2>&1
        )
    )
)

echo Abrindo a pagina oficial da DJI para baixar o DJI Virtual Flight (Windows)...
echo Na pagina que abrir, clique em "Download" ao lado de "DJI Virtual Flight (Windows)".
echo.
start "" "%DJI_PAGE%"
pause
