@echo off
title AURX WEAR Website Server
echo ========================================================
echo         STARTING AURX WEAR CLOTHING WEBSITE
echo ========================================================
echo.
echo Opening website in your browser...
timeout /t 2 /nobreak >nul
start http://localhost:8000
echo.
echo [OK] Storefront: http://localhost:8000
echo [OK] Admin Panel: http://localhost:8000/admin
echo.
echo Press Ctrl+C to stop the server anytime.
echo ========================================================
python -m uvicorn app:app --host 127.0.0.1 --port 8000
pause
