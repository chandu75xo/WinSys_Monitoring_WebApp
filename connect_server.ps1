param(
    [string]$server,
    [string]$username,
    [string]$password
)

if (-not $server -or -not $username -or -not $password) {
    Write-Host "Missing required parameters. Usage: -server <server> -username <username> -password <password>"
    exit 1
}

# Convert password to SecureString
$securePassword = ConvertTo-SecureString $password -AsPlainText -Force

# Get the script's directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$jsonPath = Join-Path $scriptPath "connection_info.json"
$tempJsonPath = "$jsonPath.tmp"

# Clear the screen and set window title
Clear-Host
$Host.UI.RawUI.WindowTitle = "Server Connection"

Write-Host "=== Server Connection ==="
Write-Host ""

try {
    Write-Host "`nAttempting to connect to $server..."
    $credential = New-Object System.Management.Automation.PSCredential($username, $securePassword)
    $session = New-PSSession -ComputerName $server -Credential $credential -ErrorAction Stop
    
    # Test if we can get basic system info
    $testCommand = "Get-WmiObject Win32_OperatingSystem | Select-Object Caption"
    $testResult = Invoke-Command -Session $session -ScriptBlock { Invoke-Expression $using:testCommand }
    
    if ($testResult) {
        # Store the connection details in a JSON file (atomic write)
        $connectionInfo = @{
            server = $server
            username = $username
            password = $password
            isConnected = $true
            timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        }
        $connectionInfo | ConvertTo-Json | Out-File $tempJsonPath -Force
        Move-Item -Force $tempJsonPath $jsonPath
        Write-Host "`nSuccessfully connected to $server"
        Write-Host "Connection details saved to $jsonPath"
        Remove-PSSession $session
        exit 0
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
    $connectionInfo | ConvertTo-Json | Out-File $tempJsonPath -Force
    Move-Item -Force $tempJsonPath $jsonPath
    exit 1
}

Write-Host "`nPress any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") 