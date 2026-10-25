@echo off
setlocal
cd /d "%~dp0"
title 3 - Rekonsiliasi e-wallet
echo.
echo   Cocokkan "Top Up ShopeePay" di rekening dengan daftar belanja.
echo.
set /p "TRX=File transaksi.csv  : "
set /p "BEL=File belanja.csv    : "
if "%TRX%"=="" goto selesai
if "%BEL%"=="" goto selesai
py -3 "tools\3_rekonsiliasi.py" "%TRX%" "%BEL%"
echo.
:selesai
pause
