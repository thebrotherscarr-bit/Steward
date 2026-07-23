@echo off
REM ===================================================================
REM  MANJUEL — bring the estate down.
REM  The servers run hidden (no windows), so this is how you stop them.
REM  It ends the windowless Python processes; the ledger holds, as always.
REM  Note: this stops ALL pythonw processes. If you run other pythonw
REM  apps, close this estate by rebooting or by Task Manager instead.
REM ===================================================================
taskkill /F /IM pythonw.exe >nul 2>nul
echo The estate is down. The ledger holds.
timeout /t 2 /nobreak >nul
