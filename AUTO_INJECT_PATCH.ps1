$ip = "140.245.241.54"
$user = "ubuntu"
$key = "$env:USERPROFILE\.ssh\oracle_vm_key"
$botDir = "/home/ubuntu/bot"

Write-Host "Waiting for Oracle VM to reboot and SSH to become available..."
while ($true) {
    # Test SSH port 22
    $connection = Test-NetConnection $ip -Port 22 -InformationLevel Quiet
    if ($connection) {
        Write-Host "SSH is UP! Injecting the PM2 patch immediately..."
        
        # Stop the bad process so it doesn't OOM while copying
        ssh -i $key -o StrictHostKeyChecking=no ${user}@${ip} "pm2 stop discordbot"
        
        # SCP the patched file
        scp -i $key -o StrictHostKeyChecking=no "f:\Whiteout Survival Bot\DISCORD BOT\cogs\gift_captchasolver.py" ${user}@${ip}:"${botDir}/cogs/gift_captchasolver.py"
        
        # Restart the daemon safely
        ssh -i $key -o StrictHostKeyChecking=no ${user}@${ip} "pm2 start discordbot"
        
        Write-Host "Patch injected and bot restarted successfully!"
        break
    }
    
    Start-Sleep -Seconds 5
    Write-Host "." -NoNewline
}
