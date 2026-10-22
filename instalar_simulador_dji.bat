@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Instalador DJI Virtual Flight (PC)

set "SIM_EXE=1661500931886-DJI Virtual Flight.exe"
set "SIM_URL=https://dl.djicdn.com/downloads/dji_virtual_flight/20220826/1661500931886-DJI%%20Virtual%%20Flight.exe"

if exist "%SIM_EXE%" (
    echo Iniciando instalador local do DJI Virtual Flight...
    start "" "%SIM_EXE%"
    exit /b
)

echo Baixando instalador oficial do DJI Virtual Flight (~3.0 GB) direto do servidor da DJI...
echo Isso pode levar alguns minutos dependendo da sua conexao.
echo.
curl.exe -L -o "%SIM_EXE%" "%SIM_URL%"
if exist "%SIM_EXE%" (
    echo Download concluido! Iniciando instalador...
    start "" "%SIM_EXE%"
) else (
    echo Falha ao baixar automaticamente. Abrindo link oficial no navegador...
    start "" "%SIM_URL%"
)
pause
