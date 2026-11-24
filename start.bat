@echo off
cd /d "%~dp0"
title AURX WEAR Website Server
echo ========================================================
echo         STARTING AURX WEAR CLOTHING WEBSITE
echo ========================================================
echo.
echo [1] Storefront URL:  http://localhost:8000
echo [2] Admin Panel URL: http://localhost:8000/admin
echo     Admin Password:  dheeraj@123
echo.
echo Opening website in your browser in 2 seconds...
echo.
timeout /t 2 /nobreak >nul
start http://localhost:8000
echo ========================================================
echo Server is running! Press Ctrl+C to stop anytime.
echo ========================================================
python -m uvicorn app:app --host 127.0.0.1 --port 8000
pause
