@echo off
setlocal
title Suplovani Viewer - instalace
rem ============================================================
rem  Instalace agenta pro odesilani suplovani na server.
rem  Staci spustit dvojklikem. Nepotrebuje spravce.
rem ============================================================
set "DEST=%USERPROFILE%\Krizik"
set "SCRIPT=%DEST%\windows_sync_agent.ps1"
set "WATCH=%USERPROFILE%\Desktop\SuplovaniExport"
set "TASK=SuplovaniSync"

echo.
echo === Instalace Suplovani Viewer agenta ===
echo Slozka agenta:   %DEST%
echo Sledovana slozka: %WATCH%
echo.

if not exist "%DEST%" mkdir "%DEST%"
if not exist "%WATCH%" mkdir "%WATCH%"

echo [1/4] Zapisuji skript agenta...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -LiteralPath '%~f0' | Where-Object { $_ -like '::PS::*' } | ForEach-Object { $_.Substring(6) } | Set-Content -Encoding UTF8 -LiteralPath '%SCRIPT%'"
if not exist "%SCRIPT%" (
  echo CHYBA: skript se nepodarilo zapsat do %SCRIPT%
  pause
  exit /b 1
)

echo [2/4] Kontrola spojeni se serverem 10.20.0.81:8080...
powershell -NoProfile -Command "if ((Test-NetConnection 10.20.0.81 -Port 8080 -WarningAction SilentlyContinue).TcpTestSucceeded) { Write-Host 'Server je dostupny.' -ForegroundColor Green } else { Write-Host 'POZOR: server 10.20.0.81:8080 neni dostupny (sit/firewall).' -ForegroundColor Red }"

echo [3/4] Nastavuji automaticky start po prihlaseni...
schtasks /delete /tn "%TASK%" /f >nul 2>&1
schtasks /create /tn "%TASK%" /sc onlogon /rl limited /f /tr "powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File \"%SCRIPT%\""
if errorlevel 1 (
  echo POZOR: nepodarilo se vytvorit naplanovanou ulohu. Agent bude fungovat jen po rucnim spusteni.
)

echo [4/4] Spoustim agenta na pozadi...
schtasks /run /tn "%TASK%" >nul 2>&1
if errorlevel 1 start "" powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File "%SCRIPT%"

echo.
echo ============================================================
echo  HOTOVO.
echo  1) V Bakalarich nastavte export do slozky:
echo        %WATCH%
echo     pod nazvem  suplprehtrid.html
echo  2) Po ulozeni souboru se do cca 20 s odesle na server.
echo  3) Kontrola: otevrete soubor  %DEST%\sync.log
echo     (radek "ODESLANO OK" = vse funguje)
echo  4) Web: http://10.20.0.81:8080
echo ============================================================
echo.
pause
exit /b 0

::PS::# Suplovani Viewer - Windows agent
::PS::# Sleduje slozku a po zmene souboru suplprehtrid.html ho posle na server (HTTP POST).
::PS::# Spusteni: powershell -ExecutionPolicy Bypass -File C:\Krizik\windows_sync_agent.ps1
::PS::
::PS::param(
::PS::    [string]$WatchFolder = "$env:USERPROFILE\Desktop\SuplovaniExport",
::PS::    [string]$ServerUrl = "http://10.20.0.81:8080/api/upload/krizik-supl-tajny-klic-2026",
::PS::    [string]$TargetFileName = "suplprehtrid.html",
::PS::    [int]$IntervalSeconds = 15,
::PS::    [string]$LogFile = "$env:USERPROFILE\Krizik\sync.log"
::PS::)
::PS::
::PS::$ErrorActionPreference = "Continue"
::PS::
::PS::function Write-Log {
::PS::    param([string]$Message, [string]$Color = "Gray")
::PS::    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
::PS::    Write-Host $line -ForegroundColor $Color
::PS::    try {
::PS::        $dir = Split-Path $LogFile -Parent
::PS::        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
::PS::        # orezani logu, aby nerostl donekonecna
::PS::        if ((Test-Path $LogFile) -and ((Get-Item $LogFile).Length -gt 512KB)) {
::PS::            Get-Content $LogFile -Tail 200 | Set-Content $LogFile
::PS::        }
::PS::        Add-Content -Path $LogFile -Value $line
::PS::    } catch { }
::PS::}
::PS::
::PS::function Test-FileReadable {
::PS::    param([string]$Path)
::PS::    try {
::PS::        $s = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
::PS::        $s.Close()
::PS::        return $true
::PS::    } catch { return $false }
::PS::}
::PS::
::PS::function Send-File {
::PS::    param([string]$Path)
::PS::    try {
::PS::        $r = Invoke-RestMethod -Uri $ServerUrl -Method Post -InFile $Path `
::PS::            -ContentType "text/html" -Headers @{ "X-Filename" = $TargetFileName } -TimeoutSec 60
::PS::        Write-Log ("ODESLANO OK: " + ($r | ConvertTo-Json -Compress)) "Green"
::PS::        return $true
::PS::    } catch {
::PS::        Write-Log ("CHYBA odeslani: " + $_.Exception.Message) "Red"
::PS::        return $false
::PS::    }
::PS::}
::PS::
::PS::if (-not (Test-Path $WatchFolder)) {
::PS::    New-Item -ItemType Directory -Path $WatchFolder -Force | Out-Null
::PS::    Write-Log "Vytvorena slozka $WatchFolder" "Yellow"
::PS::}
::PS::
::PS::$filePath = Join-Path $WatchFolder $TargetFileName
::PS::$lastSentHash = $null
::PS::
::PS::Write-Log "Agent spusten. Slozka: $WatchFolder  Soubor: $TargetFileName" "Cyan"
::PS::Write-Log "Server: $ServerUrl" "Cyan"
::PS::
::PS::while ($true) {
::PS::    try {
::PS::        if (Test-Path $filePath) {
::PS::            $size1 = (Get-Item $filePath).Length
::PS::            Start-Sleep -Seconds 2
::PS::            $size2 = (Get-Item $filePath).Length
::PS::            if ($size1 -eq $size2 -and $size2 -gt 0 -and (Test-FileReadable $filePath)) {
::PS::                $hash = (Get-FileHash -Path $filePath -Algorithm SHA256).Hash
::PS::                if ($hash -ne $lastSentHash) {
::PS::                    Write-Log "Novy/zmeneny soubor, odesilam ($size2 B)..." "Cyan"
::PS::                    if (Send-File $filePath) { $lastSentHash = $hash }
::PS::                }
::PS::            }
::PS::        }
::PS::    } catch {
::PS::        Write-Log ("Neocekavana chyba: " + $_.Exception.Message) "Red"
::PS::    }
::PS::    Start-Sleep -Seconds $IntervalSeconds
::PS::}
