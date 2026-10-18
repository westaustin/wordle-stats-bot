# Stops the running bot (the scheduled task and the Python process it started).
# Add -Uninstall to also remove the task so it no longer starts at boot.
param([switch]$Uninstall)

$TaskName = "Wordle Bot"
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -like "*-m wordle_bot*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Stopped and removed '$TaskName'."
} else {
    Write-Host "Stopped '$TaskName'. Start it again with: Start-ScheduledTask -TaskName '$TaskName'"
}
