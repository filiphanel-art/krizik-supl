@echo off
setlocal EnableExtensions
title Suplovani Viewer - instalace
cd /d "%~dp0"
set "DEST=%USERPROFILE%\Krizik"
set "SCRIPT=%DEST%\windows_sync_agent.ps1"
set "B64=%DEST%\agent.b64"
set "LOG=%DEST%\install.log"
set "TASK=SuplovaniSync"

if not exist "%DEST%" mkdir "%DEST%"
echo Instalace %date% %time% > "%LOG%"

for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set "DESKTOP=%%D"
if "%DESKTOP%"=="" set "DESKTOP=%USERPROFILE%\Desktop"
set "WATCH=%DESKTOP%\SuplovaniExport"

echo.
echo === Instalace Suplovani Viewer agenta ===
echo Slozka agenta:    %DEST%
echo Sledovana slozka: %WATCH%
echo.
echo Plocha: %DESKTOP% >> "%LOG%"

if not exist "%WATCH%" mkdir "%WATCH%"

echo [1/4] Zapisuji agenta...
if exist "%B64%" del /f /q "%B64%"
>>"%B64%" echo 77u/IyBTdXBsb3ZhbmkgVmlld2VyIC0gV2luZG93cyBhZ2VudA0KIyBTbGVkdWpl
>>"%B64%" echo IHNsb3prdSBhIHBvIHptZW5lIHNvdWJvcnUgc3VwbHByZWh0cmlkLmh0bWwgaG8g
>>"%B64%" echo cG9zbGUgbmEgc2VydmVyIChIVFRQIFBPU1QpLg0KIyBTcHVzdGVuaTogcG93ZXJz
>>"%B64%" echo aGVsbCAtRXhlY3V0aW9uUG9saWN5IEJ5cGFzcyAtRmlsZSBDOlxLcml6aWtcd2lu
>>"%B64%" echo ZG93c19zeW5jX2FnZW50LnBzMQ0KDQpwYXJhbSgNCiAgICBbc3RyaW5nXSRXYXRj
>>"%B64%" echo aEZvbGRlciA9IChbRW52aXJvbm1lbnRdOjpHZXRGb2xkZXJQYXRoKCJEZXNrdG9w
>>"%B64%" echo IikgKyAiXFN1cGxvdmFuaUV4cG9ydCIpLA0KICAgIFtzdHJpbmddJFNlcnZlclVy
>>"%B64%" echo bCA9ICJodHRwOi8vMTAuMjAuMC44MTo4MDgwL2FwaS91cGxvYWQva3JpemlrLXN1
>>"%B64%" echo cGwtdGFqbnkta2xpYy0yMDI2IiwNCiAgICBbc3RyaW5nXSRUYXJnZXRGaWxlTmFt
>>"%B64%" echo ZSA9ICJzdXBscHJlaHRyaWQuaHRtbCIsDQogICAgW2ludF0kSW50ZXJ2YWxTZWNv
>>"%B64%" echo bmRzID0gMTUsDQogICAgW3N0cmluZ10kTG9nRmlsZSA9ICIkZW52OlVTRVJQUk9G
>>"%B64%" echo SUxFXEtyaXppa1xzeW5jLmxvZyINCikNCg0KJEVycm9yQWN0aW9uUHJlZmVyZW5j
>>"%B64%" echo ZSA9ICJDb250aW51ZSINCg0KZnVuY3Rpb24gV3JpdGUtTG9nIHsNCiAgICBwYXJh
>>"%B64%" echo bShbc3RyaW5nXSRNZXNzYWdlLCBbc3RyaW5nXSRDb2xvciA9ICJHcmF5IikNCiAg
>>"%B64%" echo ICAkbGluZSA9ICJ7MH0gIHsxfSIgLWYgKEdldC1EYXRlIC1Gb3JtYXQgInl5eXkt
>>"%B64%" echo TU0tZGQgSEg6bW06c3MiKSwgJE1lc3NhZ2UNCiAgICBXcml0ZS1Ib3N0ICRsaW5l
>>"%B64%" echo IC1Gb3JlZ3JvdW5kQ29sb3IgJENvbG9yDQogICAgdHJ5IHsNCiAgICAgICAgJGRp
>>"%B64%" echo ciA9IFNwbGl0LVBhdGggJExvZ0ZpbGUgLVBhcmVudA0KICAgICAgICBpZiAoLW5v
>>"%B64%" echo dCAoVGVzdC1QYXRoICRkaXIpKSB7IE5ldy1JdGVtIC1JdGVtVHlwZSBEaXJlY3Rv
>>"%B64%" echo cnkgLVBhdGggJGRpciAtRm9yY2UgfCBPdXQtTnVsbCB9DQogICAgICAgICMgb3Jl
>>"%B64%" echo emFuaSBsb2d1LCBhYnkgbmVyb3N0bCBkb25la29uZWNuYQ0KICAgICAgICBpZiAo
>>"%B64%" echo KFRlc3QtUGF0aCAkTG9nRmlsZSkgLWFuZCAoKEdldC1JdGVtICRMb2dGaWxlKS5M
>>"%B64%" echo ZW5ndGggLWd0IDUxMktCKSkgew0KICAgICAgICAgICAgR2V0LUNvbnRlbnQgJExv
>>"%B64%" echo Z0ZpbGUgLVRhaWwgMjAwIHwgU2V0LUNvbnRlbnQgJExvZ0ZpbGUNCiAgICAgICAg
>>"%B64%" echo fQ0KICAgICAgICBBZGQtQ29udGVudCAtUGF0aCAkTG9nRmlsZSAtVmFsdWUgJGxp
>>"%B64%" echo bmUNCiAgICB9IGNhdGNoIHsgfQ0KfQ0KDQpmdW5jdGlvbiBUZXN0LUZpbGVSZWFk
>>"%B64%" echo YWJsZSB7DQogICAgcGFyYW0oW3N0cmluZ10kUGF0aCkNCiAgICB0cnkgew0KICAg
>>"%B64%" echo ICAgICAkcyA9IFtTeXN0ZW0uSU8uRmlsZV06Ok9wZW4oJFBhdGgsIFtTeXN0ZW0u
>>"%B64%" echo SU8uRmlsZU1vZGVdOjpPcGVuLCBbU3lzdGVtLklPLkZpbGVBY2Nlc3NdOjpSZWFk
>>"%B64%" echo LCBbU3lzdGVtLklPLkZpbGVTaGFyZV06OlJlYWRXcml0ZSkNCiAgICAgICAgJHMu
>>"%B64%" echo Q2xvc2UoKQ0KICAgICAgICByZXR1cm4gJHRydWUNCiAgICB9IGNhdGNoIHsgcmV0
>>"%B64%" echo dXJuICRmYWxzZSB9DQp9DQoNCmZ1bmN0aW9uIFNlbmQtRmlsZSB7DQogICAgcGFy
>>"%B64%" echo YW0oW3N0cmluZ10kUGF0aCkNCiAgICB0cnkgew0KICAgICAgICAkciA9IEludm9r
>>"%B64%" echo ZS1SZXN0TWV0aG9kIC1VcmkgJFNlcnZlclVybCAtTWV0aG9kIFBvc3QgLUluRmls
>>"%B64%" echo ZSAkUGF0aCBgDQogICAgICAgICAgICAtQ29udGVudFR5cGUgInRleHQvaHRtbCIg
>>"%B64%" echo LUhlYWRlcnMgQHsgIlgtRmlsZW5hbWUiID0gJFRhcmdldEZpbGVOYW1lIH0gLVRp
>>"%B64%" echo bWVvdXRTZWMgNjANCiAgICAgICAgV3JpdGUtTG9nICgiT0RFU0xBTk8gT0s6ICIg
>>"%B64%" echo KyAoJHIgfCBDb252ZXJ0VG8tSnNvbiAtQ29tcHJlc3MpKSAiR3JlZW4iDQogICAg
>>"%B64%" echo ICAgIHJldHVybiAkdHJ1ZQ0KICAgIH0gY2F0Y2ggew0KICAgICAgICBXcml0ZS1M
>>"%B64%" echo b2cgKCJDSFlCQSBvZGVzbGFuaTogIiArICRfLkV4Y2VwdGlvbi5NZXNzYWdlKSAi
>>"%B64%" echo UmVkIg0KICAgICAgICByZXR1cm4gJGZhbHNlDQogICAgfQ0KfQ0KDQppZiAoLW5v
>>"%B64%" echo dCAoVGVzdC1QYXRoICRXYXRjaEZvbGRlcikpIHsNCiAgICBOZXctSXRlbSAtSXRl
>>"%B64%" echo bVR5cGUgRGlyZWN0b3J5IC1QYXRoICRXYXRjaEZvbGRlciAtRm9yY2UgfCBPdXQt
>>"%B64%" echo TnVsbA0KICAgIFdyaXRlLUxvZyAiVnl0dm9yZW5hIHNsb3prYSAkV2F0Y2hGb2xk
>>"%B64%" echo ZXIiICJZZWxsb3ciDQp9DQoNCiRmaWxlUGF0aCA9IEpvaW4tUGF0aCAkV2F0Y2hG
>>"%B64%" echo b2xkZXIgJFRhcmdldEZpbGVOYW1lDQokbGFzdFNlbnRIYXNoID0gJG51bGwNCg0K
>>"%B64%" echo V3JpdGUtTG9nICJBZ2VudCBzcHVzdGVuLiBTbG96a2E6ICRXYXRjaEZvbGRlciAg
>>"%B64%" echo U291Ym9yOiAkVGFyZ2V0RmlsZU5hbWUiICJDeWFuIg0KV3JpdGUtTG9nICJTZXJ2
>>"%B64%" echo ZXI6ICRTZXJ2ZXJVcmwiICJDeWFuIg0KDQp3aGlsZSAoJHRydWUpIHsNCiAgICB0
>>"%B64%" echo cnkgew0KICAgICAgICBpZiAoVGVzdC1QYXRoICRmaWxlUGF0aCkgew0KICAgICAg
>>"%B64%" echo ICAgICAgJHNpemUxID0gKEdldC1JdGVtICRmaWxlUGF0aCkuTGVuZ3RoDQogICAg
>>"%B64%" echo ICAgICAgICBTdGFydC1TbGVlcCAtU2Vjb25kcyAyDQogICAgICAgICAgICAkc2l6
>>"%B64%" echo ZTIgPSAoR2V0LUl0ZW0gJGZpbGVQYXRoKS5MZW5ndGgNCiAgICAgICAgICAgIGlm
>>"%B64%" echo ICgkc2l6ZTEgLWVxICRzaXplMiAtYW5kICRzaXplMiAtZ3QgMCAtYW5kIChUZXN0
>>"%B64%" echo LUZpbGVSZWFkYWJsZSAkZmlsZVBhdGgpKSB7DQogICAgICAgICAgICAgICAgJGhh
>>"%B64%" echo c2ggPSAoR2V0LUZpbGVIYXNoIC1QYXRoICRmaWxlUGF0aCAtQWxnb3JpdGhtIFNI
>>"%B64%" echo QTI1NikuSGFzaA0KICAgICAgICAgICAgICAgIGlmICgkaGFzaCAtbmUgJGxhc3RT
>>"%B64%" echo ZW50SGFzaCkgew0KICAgICAgICAgICAgICAgICAgICBXcml0ZS1Mb2cgIk5vdnkv
>>"%B64%" echo em1lbmVueSBzb3Vib3IsIG9kZXNpbGFtICgkc2l6ZTIgQikuLi4iICJDeWFuIg0K
>>"%B64%" echo ICAgICAgICAgICAgICAgICAgICBpZiAoU2VuZC1GaWxlICRmaWxlUGF0aCkgeyAk
>>"%B64%" echo bGFzdFNlbnRIYXNoID0gJGhhc2ggfQ0KICAgICAgICAgICAgICAgIH0NCiAgICAg
>>"%B64%" echo ICAgICAgIH0NCiAgICAgICAgfQ0KICAgIH0gY2F0Y2ggew0KICAgICAgICBXcml0
>>"%B64%" echo ZS1Mb2cgKCJOZW9jZWthdmFuYSBjaHliYTogIiArICRfLkV4Y2VwdGlvbi5NZXNz
>>"%B64%" echo YWdlKSAiUmVkIg0KICAgIH0NCiAgICBTdGFydC1TbGVlcCAtU2Vjb25kcyAkSW50
>>"%B64%" echo ZXJ2YWxTZWNvbmRzDQp9DQo=
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
schtasks /create /tn "%TASK%" /sc onlogon /rl limited /f /tr "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File \"%SCRIPT%\" -WatchFolder \"%WATCH%\"" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo       POZOR: planovana uloha se nevytvorila, viz %LOG%
) else (
  echo       OK: uloha %TASK%
)

echo [4/4] Spoustim agenta na pozadi...
start "" powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File "%SCRIPT%" -WatchFolder "%WATCH%"
timeout /t 6 /nobreak >nul
if exist "%DEST%\sync.log" (
  echo       Agent bezi. Posledni radky logu:
  powershell -NoProfile -Command "Get-Content -LiteralPath '%DEST%\sync.log' -Tail 5"
) else (
  echo       POZOR: agent nenapsal zadny log. Zkuste jej spustit rucne:
  echo       powershell -ExecutionPolicy Bypass -File "%SCRIPT%" -WatchFolder "%WATCH%"
)

echo.
echo ============================================================
echo  HOTOVO.
echo  Bakalare ukladejte do:  %WATCH%
echo  pod nazvem:             suplprehtrid.html
echo  Kontrola:               %DEST%\sync.log  (radek "ODESLANO OK")
echo  Web:                    http://10.20.0.81:8080
echo ============================================================
echo.
pause
exit /b 0
