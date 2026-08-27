@echo off
cd /d "%~dp0"

echo.
echo UA Arena Discord bot
echo.

where py >nul 2>&1
if %errorlevel%==0 (
  set PY=py
) else (
  set PY=python
)

echo Installing discord.py ...
%PY% -m pip install -r requirements-bot.txt
if errorlevel 1 (
  echo.
  echo Python was not found. Install Python from https://www.python.org/downloads/
  echo Check "Add python.exe to PATH" then try again.
  pause
  exit /b 1
)

echo.
set /p DISCORD_TOKEN=Paste your Discord bot token and press Enter: 
if "%DISCORD_TOKEN%"=="" (
  echo No token pasted.
  pause
  exit /b 1
)

echo.
echo Starting bot. Leave this window open.
echo When the bot is online in Discord, type /setup
echo.
%PY% scripts\discord_bot.py --live
echo.
echo Bot stopped.
pause
