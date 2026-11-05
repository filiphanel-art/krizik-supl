# Suplovani Viewer - Windows agent
# Sleduje slozku a po zmene souboru suplprehtrid.html ho posle na server (HTTP POST).
# Spusteni: powershell -ExecutionPolicy Bypass -File C:\Krizik\windows_sync_agent.ps1

param(
    [string]$WatchFolder = "$env:USERPROFILE\Desktop\SuplovaniExport",
    [string]$ServerUrl = "http://10.20.0.81:8080/api/upload/krizik-supl-tajny-klic-2026",
    [string]$TargetFileName = "suplprehtrid.html",
    [int]$IntervalSeconds = 15,
    [string]$LogFile = "C:\Krizik\sync.log"
)

$ErrorActionPreference = "Continue"

function Write-Log {
    param([string]$Message, [string]$Color = "Gray")
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line -ForegroundColor $Color
    try {
        $dir = Split-Path $LogFile -Parent
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        # orezani logu, aby nerostl donekonecna
        if ((Test-Path $LogFile) -and ((Get-Item $LogFile).Length -gt 512KB)) {
            Get-Content $LogFile -Tail 200 | Set-Content $LogFile
        }
        Add-Content -Path $LogFile -Value $line
    } catch { }
}

function Test-FileReadable {
    param([string]$Path)
    try {
        $s = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        $s.Close()
        return $true
    } catch { return $false }
}

function Send-File {
    param([string]$Path)
    try {
        $r = Invoke-RestMethod -Uri $ServerUrl -Method Post -InFile $Path `
            -ContentType "text/html" -Headers @{ "X-Filename" = $TargetFileName } -TimeoutSec 60
        Write-Log ("ODESLANO OK: " + ($r | ConvertTo-Json -Compress)) "Green"
        return $true
    } catch {
        Write-Log ("CHYBA odeslani: " + $_.Exception.Message) "Red"
        return $false
    }
}

if (-not (Test-Path $WatchFolder)) {
    New-Item -ItemType Directory -Path $WatchFolder -Force | Out-Null
    Write-Log "Vytvorena slozka $WatchFolder" "Yellow"
}

$filePath = Join-Path $WatchFolder $TargetFileName
$lastSentHash = $null

Write-Log "Agent spusten. Slozka: $WatchFolder  Soubor: $TargetFileName" "Cyan"
Write-Log "Server: $ServerUrl" "Cyan"

while ($true) {
    try {
        if (Test-Path $filePath) {
            $size1 = (Get-Item $filePath).Length
            Start-Sleep -Seconds 2
            $size2 = (Get-Item $filePath).Length
            if ($size1 -eq $size2 -and $size2 -gt 0 -and (Test-FileReadable $filePath)) {
                $hash = (Get-FileHash -Path $filePath -Algorithm SHA256).Hash
                if ($hash -ne $lastSentHash) {
                    Write-Log "Novy/zmeneny soubor, odesilam ($size2 B)..." "Cyan"
                    if (Send-File $filePath) { $lastSentHash = $hash }
                }
            }
        }
    } catch {
        Write-Log ("Neocekavana chyba: " + $_.Exception.Message) "Red"
    }
    Start-Sleep -Seconds $IntervalSeconds
}
