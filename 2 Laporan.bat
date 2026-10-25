@echo off
setlocal
cd /d "%~dp0"
title 2 - Buat laporan
if "%~1"=="" goto tanya
set "TARGET=%~1"
goto jalan
:tanya
echo.
echo   Tarik file transaksi.csv ke jendela ini, lalu Enter.
echo.
set /p "TARGET=Path: "
:jalan
if "%TARGET%"=="" goto selesai
py -3 "tools\2_analisa.py" "%TARGET%"
echo.
echo   Buka laporan.html di folder yang sama dengan CSV tadi.
echo.
:selesai
pause
