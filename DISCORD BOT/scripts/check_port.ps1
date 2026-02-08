param(
    [int]$Port = 8080,
    [switch]$Kill
)

$netstat = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue

if ($netstat) {
    Write-Host "Port $Port is in use by Process ID: $($netstat.OwningProcess)" -ForegroundColor Yellow
    try {
        $process = Get-Process -Id $netstat.OwningProcess -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "Process Name: $($process.ProcessName)" -ForegroundColor Cyan
            
            if ($Kill) {
                Stop-Process -Id $netstat.OwningProcess -Force
                Write-Host "Process $($netstat.OwningProcess) ($($process.ProcessName)) killed." -ForegroundColor Green
            } else {
                Write-Host "Use -Kill switch to terminate this process." -ForegroundColor Gray
            }
        }
    } catch {
        Write-Host "Could not retrieve process info (likely requires Admin privileges)." -ForegroundColor Red
    }
} else {
    Write-Host "Port $Port is free." -ForegroundColor Green
}
