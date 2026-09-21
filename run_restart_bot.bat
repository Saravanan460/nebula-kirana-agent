@echo off
title PythonAnywhere Telegram Bot Restarter
echo Starting PythonAnywhere Bot Restarter...
python -c "import requests" 2>nul || pip install requests
python "%~dp0restart_pa_bot.py"
echo.
pause
