# BREW DAILY - Windows タスクスケジューラ設定スクリプト
# 管理者権限で実行してください: Right-click > Run as Administrator

param(
    [string]$ApiKey = "",
    [string]$PythonPath = ""
)

Write-Host "🍺 BREW DAILY タスクスケジューラ設定" -ForegroundColor Yellow
Write-Host "=" * 50

# Python パスの自動検出
if (-not $PythonPath) {
    $PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $PythonPath) {
        $PythonPath = "C:\Python313\python.exe"
    }
}
Write-Host "🐍 Python: $PythonPath"

# スクリプトのパス
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptPath = Join-Path $ScriptDir "brew_magazine.py"
Write-Host "📄 スクリプト: $ScriptPath"

# ANTHROPIC_API_KEY の設定
if (-not $ApiKey) {
    $ApiKey = $env:ANTHROPIC_API_KEY
}

if (-not $ApiKey) {
    $ApiKey = Read-Host "ANTHROPIC_API_KEY を入力してください"
}

# バッチファイル作成（タスクスケジューラから呼び出す）
$BatchFile = Join-Path $ScriptDir "run_brew_daily.bat"
$BatchContent = @"
@echo off
SET ANTHROPIC_API_KEY=$ApiKey
cd /d "$ScriptDir"
"$PythonPath" "$ScriptPath" >> "$ScriptDir\logs\brew_daily.log" 2>&1
"@

$LogDir = Join-Path $ScriptDir "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

Set-Content -Path $BatchFile -Value $BatchContent -Encoding UTF8
Write-Host "✅ バッチファイル作成: $BatchFile"

# タスクスケジューラの設定
$TaskName = "BREW_DAILY_Magazine"
$TaskDescription = "毎朝7時に世界の醸造所情報を収集し、日本語マガジンを生成します"

# 既存タスクの削除（再登録のため）
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "♻️ 既存タスクを削除しました"
}

# トリガー: 毎日 7:00 AM
$Trigger = New-ScheduledTaskTrigger -Daily -At "07:00AM"

# アクション: バッチファイルを実行
$Action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$BatchFile`"" `
    -WorkingDirectory $ScriptDir

# 設定
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# タスク登録
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description $TaskDescription `
        -Trigger $Trigger `
        -Action $Action `
        -Settings $Settings `
        -RunLevel Highest `
        -Force | Out-Null

    Write-Host ""
    Write-Host "✅ タスクスケジューラ設定完了!" -ForegroundColor Green
    Write-Host "   タスク名: $TaskName"
    Write-Host "   実行時刻: 毎日 07:00 AM"
    Write-Host "   ログ: $LogDir\brew_daily.log"
    Write-Host ""
    Write-Host "📋 確認方法:" -ForegroundColor Cyan
    Write-Host "   タスクスケジューラを開く → タスクスケジューラライブラリ → $TaskName"
    Write-Host ""
    Write-Host "🧪 今すぐテスト実行する場合:" -ForegroundColor Cyan
    Write-Host "   Start-ScheduledTask -TaskName '$TaskName'"
    Write-Host "   または: python `"$ScriptPath`" --demo"

} catch {
    Write-Host "❌ タスク登録エラー: $_" -ForegroundColor Red
    Write-Host "管理者権限で実行してください" -ForegroundColor Yellow
}
