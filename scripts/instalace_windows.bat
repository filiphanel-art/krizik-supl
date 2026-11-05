@echo off
setlocal EnableExtensions
title Suplovani Viewer - instalace
cd /d "%~dp0"
set "DEST=C:\Krizik"
set "SCRIPT=%DEST%\windows_sync_agent.ps1"
set "B64=%DEST%\agent.b64"
set "LOG=%DEST%\install.log"
set "TASK=SuplovaniSync"

if not exist "%DEST%" mkdir "%DEST%"
if not exist "%DEST%" (
  echo CHYBA: nelze vytvorit slozku %DEST% - spustte tento soubor pravym tlacitkem "Spustit jako spravce".
  pause
  exit /b 1
)
echo Instalace %date% %time% > "%LOG%"

echo.
echo === Instalace Suplovani Viewer agenta ===
echo Vse je ve slozce: %DEST%
echo Sem davejte export: suplprehtrid.html
echo.

echo [1/4] Zapisuji agenta...
if exist "%B64%" del /f /q "%B64%"
>>"%B64%" echo 77u/IyBTdXBsb3ZhbmkgVmlld2VyIC0gV2luZG93cyBhZ2VudA0KIyBTbGVkdWpl
>>"%B64%" echo IHNsb3prdSBhIHBvIHptZW5lIHNvdWJvcnUgc3VwbHByZWh0cmlkLmh0bWwgaG8g
>>"%B64%" echo cG9zbGUgbmEgc2VydmVyIChIVFRQIFBPU1QpLg0KIyBTcHVzdGVuaTogcG93ZXJz
>>"%B64%" echo aGVsbCAtRXhlY3V0aW9uUG9saWN5IEJ5cGFzcyAtRmlsZSBDOlxLcml6aWtcd2lu
>>"%B64%" echo ZG93c19zeW5jX2FnZW50LnBzMQ0KDQpwYXJhbSgNCiAgICBbc3RyaW5nXSRXYXRj
>>"%B64%" echo aEZvbGRlciA9ICJDOlxLcml6aWsiLA0KICAgIFtzdHJpbmddJFNlcnZlclVybCA9
>>"%B64%" echo ICJodHRwOi8vMTAuMjAuMC44MTo4MDgwL2FwaS91cGxvYWQva3JpemlrLXN1cGwt
>>"%B64%" echo dGFqbnkta2xpYy0yMDI2IiwNCiAgICBbc3RyaW5nXSRUYXJnZXRGaWxlTmFtZSA9
>>"%B64%" echo ICJzdXBscHJlaHRyaWQuaHRtbCIsDQogICAgW2ludF0kSW50ZXJ2YWxTZWNvbmRz
>>"%B64%" echo ID0gMTUsDQogICAgW3N0cmluZ10kTG9nRmlsZSA9ICJDOlxLcml6aWtcc3luYy5s
>>"%B64%" echo b2ciDQopDQoNCiRFcnJvckFjdGlvblByZWZlcmVuY2UgPSAiQ29udGludWUiDQoN
>>"%B64%" echo CmZ1bmN0aW9uIFdyaXRlLUxvZyB7DQogICAgcGFyYW0oW3N0cmluZ10kTWVzc2Fn
>>"%B64%" echo ZSwgW3N0cmluZ10kQ29sb3IgPSAiR3JheSIpDQogICAgJGxpbmUgPSAiezB9ICB7
>>"%B64%" echo MX0iIC1mIChHZXQtRGF0ZSAtRm9ybWF0ICJ5eXl5LU1NLWRkIEhIOm1tOnNzIiks
>>"%B64%" echo ICRNZXNzYWdlDQogICAgV3JpdGUtSG9zdCAkbGluZSAtRm9yZWdyb3VuZENvbG9y
>>"%B64%" echo ICRDb2xvcg0KICAgIHRyeSB7DQogICAgICAgICRkaXIgPSBTcGxpdC1QYXRoICRM
>>"%B64%" echo b2dGaWxlIC1QYXJlbnQNCiAgICAgICAgaWYgKC1ub3QgKFRlc3QtUGF0aCAkZGly
>>"%B64%" echo KSkgeyBOZXctSXRlbSAtSXRlbVR5cGUgRGlyZWN0b3J5IC1QYXRoICRkaXIgLUZv
>>"%B64%" echo cmNlIHwgT3V0LU51bGwgfQ0KICAgICAgICAjIG9yZXphbmkgbG9ndSwgYWJ5IG5l
>>"%B64%" echo cm9zdGwgZG9uZWtvbmVjbmENCiAgICAgICAgaWYgKChUZXN0LVBhdGggJExvZ0Zp
>>"%B64%" echo bGUpIC1hbmQgKChHZXQtSXRlbSAkTG9nRmlsZSkuTGVuZ3RoIC1ndCA1MTJLQikp
>>"%B64%" echo IHsNCiAgICAgICAgICAgIEdldC1Db250ZW50ICRMb2dGaWxlIC1UYWlsIDIwMCB8
>>"%B64%" echo IFNldC1Db250ZW50ICRMb2dGaWxlDQogICAgICAgIH0NCiAgICAgICAgQWRkLUNv
>>"%B64%" echo bnRlbnQgLVBhdGggJExvZ0ZpbGUgLVZhbHVlICRsaW5lDQogICAgfSBjYXRjaCB7
>>"%B64%" echo IH0NCn0NCg0KZnVuY3Rpb24gVGVzdC1GaWxlUmVhZGFibGUgew0KICAgIHBhcmFt
>>"%B64%" echo KFtzdHJpbmddJFBhdGgpDQogICAgdHJ5IHsNCiAgICAgICAgJHMgPSBbU3lzdGVt
>>"%B64%" echo LklPLkZpbGVdOjpPcGVuKCRQYXRoLCBbU3lzdGVtLklPLkZpbGVNb2RlXTo6T3Bl
>>"%B64%" echo biwgW1N5c3RlbS5JTy5GaWxlQWNjZXNzXTo6UmVhZCwgW1N5c3RlbS5JTy5GaWxl
>>"%B64%" echo U2hhcmVdOjpSZWFkV3JpdGUpDQogICAgICAgICRzLkNsb3NlKCkNCiAgICAgICAg
>>"%B64%" echo cmV0dXJuICR0cnVlDQogICAgfSBjYXRjaCB7IHJldHVybiAkZmFsc2UgfQ0KfQ0K
>>"%B64%" echo DQpmdW5jdGlvbiBTZW5kLUZpbGUgew0KICAgIHBhcmFtKFtzdHJpbmddJFBhdGgp
>>"%B64%" echo DQogICAgdHJ5IHsNCiAgICAgICAgJHIgPSBJbnZva2UtUmVzdE1ldGhvZCAtVXJp
>>"%B64%" echo ICRTZXJ2ZXJVcmwgLU1ldGhvZCBQb3N0IC1JbkZpbGUgJFBhdGggYA0KICAgICAg
>>"%B64%" echo ICAgICAgLUNvbnRlbnRUeXBlICJ0ZXh0L2h0bWwiIC1IZWFkZXJzIEB7ICJYLUZp
>>"%B64%" echo bGVuYW1lIiA9ICRUYXJnZXRGaWxlTmFtZSB9IC1UaW1lb3V0U2VjIDYwDQogICAg
>>"%B64%" echo ICAgIFdyaXRlLUxvZyAoIk9ERVNMQU5PIE9LOiAiICsgKCRyIHwgQ29udmVydFRv
>>"%B64%" echo LUpzb24gLUNvbXByZXNzKSkgIkdyZWVuIg0KICAgICAgICByZXR1cm4gJHRydWUN
>>"%B64%" echo CiAgICB9IGNhdGNoIHsNCiAgICAgICAgV3JpdGUtTG9nICgiQ0hZQkEgb2Rlc2xh
>>"%B64%" echo bmk6ICIgKyAkXy5FeGNlcHRpb24uTWVzc2FnZSkgIlJlZCINCiAgICAgICAgcmV0
>>"%B64%" echo dXJuICRmYWxzZQ0KICAgIH0NCn0NCg0KaWYgKC1ub3QgKFRlc3QtUGF0aCAkV2F0
>>"%B64%" echo Y2hGb2xkZXIpKSB7DQogICAgTmV3LUl0ZW0gLUl0ZW1UeXBlIERpcmVjdG9yeSAt
>>"%B64%" echo UGF0aCAkV2F0Y2hGb2xkZXIgLUZvcmNlIHwgT3V0LU51bGwNCiAgICBXcml0ZS1M
>>"%B64%" echo b2cgIlZ5dHZvcmVuYSBzbG96a2EgJFdhdGNoRm9sZGVyIiAiWWVsbG93Ig0KfQ0K
>>"%B64%" echo DQokZmlsZVBhdGggPSBKb2luLVBhdGggJFdhdGNoRm9sZGVyICRUYXJnZXRGaWxl
>>"%B64%" echo TmFtZQ0KJGxhc3RTZW50SGFzaCA9ICRudWxsDQoNCldyaXRlLUxvZyAiQWdlbnQg
>>"%B64%" echo c3B1c3Rlbi4gU2xvemthOiAkV2F0Y2hGb2xkZXIgIFNvdWJvcjogJFRhcmdldEZp
>>"%B64%" echo bGVOYW1lIiAiQ3lhbiINCldyaXRlLUxvZyAiU2VydmVyOiAkU2VydmVyVXJsIiAi
>>"%B64%" echo Q3lhbiINCg0Kd2hpbGUgKCR0cnVlKSB7DQogICAgdHJ5IHsNCiAgICAgICAgaWYg
>>"%B64%" echo KFRlc3QtUGF0aCAkZmlsZVBhdGgpIHsNCiAgICAgICAgICAgICRzaXplMSA9IChH
>>"%B64%" echo ZXQtSXRlbSAkZmlsZVBhdGgpLkxlbmd0aA0KICAgICAgICAgICAgU3RhcnQtU2xl
>>"%B64%" echo ZXAgLVNlY29uZHMgMg0KICAgICAgICAgICAgJHNpemUyID0gKEdldC1JdGVtICRm
>>"%B64%" echo aWxlUGF0aCkuTGVuZ3RoDQogICAgICAgICAgICBpZiAoJHNpemUxIC1lcSAkc2l6
>>"%B64%" echo ZTIgLWFuZCAkc2l6ZTIgLWd0IDAgLWFuZCAoVGVzdC1GaWxlUmVhZGFibGUgJGZp
>>"%B64%" echo bGVQYXRoKSkgew0KICAgICAgICAgICAgICAgICRoYXNoID0gKEdldC1GaWxlSGFz
>>"%B64%" echo aCAtUGF0aCAkZmlsZVBhdGggLUFsZ29yaXRobSBTSEEyNTYpLkhhc2gNCiAgICAg
>>"%B64%" echo ICAgICAgICAgICBpZiAoJGhhc2ggLW5lICRsYXN0U2VudEhhc2gpIHsNCiAgICAg
>>"%B64%" echo ICAgICAgICAgICAgICAgV3JpdGUtTG9nICJOb3Z5L3ptZW5lbnkgc291Ym9yLCBv
>>"%B64%" echo ZGVzaWxhbSAoJHNpemUyIEIpLi4uIiAiQ3lhbiINCiAgICAgICAgICAgICAgICAg
>>"%B64%" echo ICAgaWYgKFNlbmQtRmlsZSAkZmlsZVBhdGgpIHsgJGxhc3RTZW50SGFzaCA9ICRo
>>"%B64%" echo YXNoIH0NCiAgICAgICAgICAgICAgICB9DQogICAgICAgICAgICB9DQogICAgICAg
>>"%B64%" echo IH0NCiAgICB9IGNhdGNoIHsNCiAgICAgICAgV3JpdGUtTG9nICgiTmVvY2VrYXZh
>>"%B64%" echo bmEgY2h5YmE6ICIgKyAkXy5FeGNlcHRpb24uTWVzc2FnZSkgIlJlZCINCiAgICB9
>>"%B64%" echo DQogICAgU3RhcnQtU2xlZXAgLVNlY29uZHMgJEludGVydmFsU2Vjb25kcw0KfQ0K
certutil -f -decode "%B64%" "%SCRIPT%" >> "%LOG%" 2>&1
del /f /q "%B64%" >nul 2>&1
if not exist "%SCRIPT%" (
  echo CHYBA: agent se nepodarilo zapsat. Podivejte se do %LOG%
  pause
  exit /b 1
)
echo       OK: %SCRIPT%

echo [2/4] Kontrola spojeni se serverem 10.20.0.81:8080...
powershell -NoProfile -Command "if ((Test-NetConnection 10.20.0.81 -Port 8080 -WarningAction SilentlyContinue).TcpTestSucceeded) { Write-Host '      Server je dostupny.' -ForegroundColor Green } else { Write-Host '      POZOR: server 10.20.0.81:8080 neni dostupny (sit/firewall).' -ForegroundColor Red }"

echo [3/4] Automaticky start po prihlaseni...
schtasks /delete /tn "%TASK%" /f >nul 2>&1
schtasks /create /tn "%TASK%" /sc onlogon /rl limited /f /tr "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File \"%SCRIPT%\"" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo       POZOR: planovana uloha se nevytvorila, viz %LOG%
) else (
  echo       OK: uloha %TASK%
)

echo [4/4] Spoustim agenta na pozadi...
start "" powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File "%SCRIPT%"
timeout /t 6 /nobreak >nul
if exist "%DEST%\sync.log" (
  echo       Agent bezi. Posledni radky logu:
  powershell -NoProfile -Command "Get-Content -LiteralPath 'C:\Krizik\sync.log' -Tail 5"
) else (
  echo       POZOR: agent nenapsal zadny log. Zkuste jej spustit rucne:
  echo       powershell -ExecutionPolicy Bypass -File "%SCRIPT%"
)

echo.
echo ============================================================
echo  HOTOVO. Vse je v C:\Krizik
echo  Export z Bakalaru ukladejte do C:\Krizik jako suplprehtrid.html
echo  Kontrola: C:\Krizik\sync.log  (radek "ODESLANO OK")
echo  Web: http://10.20.0.81:8080
echo ============================================================
echo.
pause
exit /b 0
