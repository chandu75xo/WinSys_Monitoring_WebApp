# Set execution policy to allow script execution
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

# Get the script's directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$jsonPath = Join-Path $scriptPath "connection_info.json"

# Clear the screen and set window title
Clear-Host
$Host.UI.RawUI.WindowTitle = "Server Connection"

Write-Host "=== Server Connection ==="
Write-Host ""

# Get server details
$server = Read-Host "Enter Server IP or FQDN"
if (-not $server) { 
    Write-Host "No server specified. Exiting..."
    Start-Sleep -Seconds 2
    exit 
}

$username = Read-Host "Enter Username"
if (-not $username) { 
    Write-Host "No username specified. Exiting..."
    Start-Sleep -Seconds 2
    exit 
}

$password = Read-Host "Enter Password" -AsSecureString
if (-not $password) { 
    Write-Host "No password specified. Exiting..."
    Start-Sleep -Seconds 2
    exit 
}

# Convert secure string to plain text for the session
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
$plainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

try {
    Write-Host "`nAttempting to connect to $server..."
    $credential = New-Object System.Management.Automation.PSCredential($username, $password)
    $session = New-PSSession -ComputerName $server -Credential $credential -ErrorAction Stop
    
    # Test if we can get basic system info
    $testCommand = "Get-WmiObject Win32_OperatingSystem | Select-Object Caption"
    $testResult = Invoke-Command -Session $session -ScriptBlock { Invoke-Expression $using:testCommand }
    
    if ($testResult) {
        # Store the connection details in a JSON file
        $connectionInfo = @{
            server = $server
            username = $username
            password = $plainPassword
            isConnected = $true
            timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        }
        
        $connectionInfo | ConvertTo-Json | Out-File $jsonPath -Force
        
        Write-Host "`nSuccessfully connected to $server"
        Write-Host "Connection details saved to $jsonPath"
        Remove-PSSession $session
    } else {
        throw "Could not retrieve system information from remote server"
    }
} catch {
    Write-Host "`nFailed to connect to $server : $_"
    $connectionInfo = @{
        isConnected = $false
        error = $_.Exception.Message
        timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    }
    $connectionInfo | ConvertTo-Json | Out-File $jsonPath -Force
}

Write-Host "`nPress any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") 