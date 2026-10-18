@echo off
rem Runs the bot forever: if it ever exits, wait 30 seconds and start it again.
cd /d "%~dp0..\.."
set PYTHONUTF8=1
:loop
".venv\Scripts\python.exe" -m wordle_bot
rem ping as a sleep: "timeout" fails when there is no console window
ping -n 31 127.0.0.1 >nul
goto loop
