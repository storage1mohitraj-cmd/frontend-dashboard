$ip = "140.245.192.181"
$key = "$env:USERPROFILE\.ssh\oracle_vm_key"

Write-Host "Waiting for Oracle VM to come online and SSH to become available..."
while ($true) {
    # Test SSH port 22
    $connection = Test-NetConnection $ip -Port 22 -InformationLevel Quiet
    if ($connection) {
        Write-Host "SSH is UP! Creating 2GB Swap Memory and restarting bot..."
        
        # Stop PM2 immediately to prevent OOM crash loop during setup
        ssh -i $key -o StrictHostKeyChecking=no opc@140.245.192.181 "pm2 stop discordbot"
        
        # Bash script to create swap
        $swapScript = @"
if [ ! -f /swapfile ]; then
    echo 'Creating 2GB swap file...'
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    
    # Make it permanent
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo 'Swap file created and enabled!'
    free -m
else
    echo 'Swap file already exists.'
    free -m
fi
"@

        # Run swap setup on VM
        ssh -i $key -o StrictHostKeyChecking=no opc@140.245.192.181 $swapScript
        
        # Restart the bot safely with the extra memory
        ssh -i $key -o StrictHostKeyChecking=no opc@140.245.192.181 "pm2 restart discordbot --update-env && pm2 save"
        
        Write-Host "Swap Memory injected and bot restarted successfully!"
        break
    }
    
    Start-Sleep -Seconds 5
    Write-Host "." -NoNewline
}
