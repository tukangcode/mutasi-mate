@echo off
setlocal
cd /d "%~dp0"
title 1 - Ekstrak transaksi
if "%~1"=="" goto tanya
set "TARGET=%~1"
goto jalan
:tanya
echo.
echo   Tarik file PDF / gambar / folder ke jendela ini, lalu Enter.
echo   (atau ketik path-nya)
echo.
set /p "TARGET=Path: "
:jalan
if "%TARGET%"=="" goto selesai
py -3 "tools\1_ekstrak.py" "%TARGET%"
echo.
:selesai
pause
