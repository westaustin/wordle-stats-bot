# Registers "Wordle Bot" in Task Scheduler: starts at boot, runs whether or not anyone is logged in.
# Run from an elevated (Run as administrator) PowerShell:
#   powershell -ExecutionPolicy Bypass -File deploy\windows\install-task.ps1

$ErrorActionPreference = "Stop"
$TaskName = "Wordle Bot"
$BotDir = (Resolve-Path "$PSScriptRoot\..\..").Path
$RunScript = Join-Path $BotDir "deploy\windows\run-bot.cmd"

if (-not (Test-Path (Join-Path $BotDir ".venv\Scripts\python.exe"))) {
    throw "No virtual environment at $BotDir\.venv. Do the install steps in the README first."
}
if (-not (Test-Path (Join-Path $BotDir ".env"))) {
    throw "No .env file in $BotDir. Copy .env.example to .env and fill in DISCORD_TOKEN first."
}

# Running without anyone logged in needs the account's password (a Microsoft-account PIN won't work).
$cred = Get-Credential -UserName "$env:USERDOMAIN\$env:USERNAME" `
    -Message "Windows password for the account the bot runs as"

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$RunScript`"" -WorkingDirectory $BotDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger.Delay = "PT1M"  # give the network a minute after boot
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -User $cred.UserName -Password $cred.GetNetworkCredential().Password -RunLevel Limited -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName
Write-Host "Installed and started '$TaskName'. It will start automatically at every boot."
