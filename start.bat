@echo off
REM ===================================================================
REM  MANJUEL — the estate.  One launcher, no windows.
REM
REM  Wakes the whole stack HIDDEN (pythonw = no console window) and opens
REM  the console in your browser. Order matters: Steward first, because he
REM  seals and awakens Manjuel beneath him and needs a moment to do it;
REM  then the Forge; then the Board — the front door you actually use.
REM
REM  To stop it later: run stop.bat.
REM ===================================================================
cd /d "%~dp0"

REM  pythonw runs Python with NO console window. If it is somehow missing,
REM  fall back to python (windows WILL show) so the estate still wakes.
set "PYW=pythonw"
where pythonw >nul 2>nul || set "PYW=python"

start "" %PYW% "%~dp0steward.py"
REM  Steward seals + awakens Manjuel (grows his weights on the first run).
timeout /t 9 /nobreak >nul

start "" %PYW% "%~dp0forge_server.py"
start "" %PYW% "%~dp0board_server.py"
timeout /t 3 /nobreak >nul

start "" "http://127.0.0.1:7376/"
exit
