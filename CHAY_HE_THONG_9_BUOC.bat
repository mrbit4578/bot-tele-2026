@echo off
chcp 65001 >nul
title HE THONG AUTO TAO BOT TELEGRAM 9 BUOC
echo ============================================================================
echo    HE THONG AUTO TAO BOT TELEGRAM THEO CAU TRUC 9 BUOC
echo ============================================================================
echo.
echo [1] Kiem tra trang thai 9 buoc tren Terminal...
python auto_wizard_cli.py
echo.
echo [2] Dang khoi dong Giao Dien Web 9 Buoc tai: http://127.0.0.1:5000/dashboard
start "" "http://127.0.0.1:5000/dashboard"
python main.py
pause
