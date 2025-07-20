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

try {
    $credential = New-Object System.Management.Automation.PSCredential($username, $securePassword)
    $session = New-PSSession -ComputerName $server -Credential $credential -ErrorAction Stop

    $data = Invoke-Command -Session $session -ScriptBlock {
        $cpu = (Get-WmiObject Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
        $mem = Get-WmiObject Win32_OperatingSystem
        $memory = [math]::Round((1 - $mem.FreePhysicalMemory/$mem.TotalVisibleMemorySize) * 100, 2)
        $fixedDisks = Get-WmiObject Win32_LogicalDisk | Where-Object { $_.DriveType -eq 3 }
        $totalSize = ($fixedDisks | Measure-Object -Property Size -Sum).Sum
        $totalFree = ($fixedDisks | Measure-Object -Property FreeSpace -Sum).Sum
        $diskPercent = if ($totalSize -gt 0) { [math]::Round((1 - ($totalFree / $totalSize)) * 100, 2) } else { 0 }
        $disks = $fixedDisks | ForEach-Object {
            $used_percent = if ($_.Size -and $_.FreeSpace) {
                [math]::Round((1 - ($_.FreeSpace / $_.Size)) * 100, 2)
            } else {
                0
            }
            [PSCustomObject]@{
                DeviceID = $_.DeviceID
                Size = $_.Size
                FreeSpace = $_.FreeSpace
                UsedPercent = $used_percent
            }
        }
        $processes = Get-Process | Select-Object Id,ProcessName,CPU,PM
        $services = Get-Service | Select-Object Name,DisplayName,Status
        $os = Get-WmiObject Win32_OperatingSystem
        $cs = Get-WmiObject Win32_ComputerSystem
        $bios = Get-WmiObject Win32_BIOS
        $system_details = @{
            os_name = $os.Caption
            os_version = $os.Version
            system_model = $cs.Model
            system_type = $cs.SystemType
            processor = $cs.NumberOfProcessors
            bios_version = $bios.SMBIOSBIOSVersion
            bios_date = $bios.ReleaseDate
            manufacturer = $cs.Manufacturer
            total_ram = [math]::Round($cs.TotalPhysicalMemory/1GB, 2)
        }
        $result = @{
            cpu = $cpu
            memory = $memory
            disk = $diskPercent
            disks = $disks
            processes = $processes
            services = $services
            system_details = $system_details
        }
        return $result | ConvertTo-Json -Depth 5
    }
    Remove-PSSession $session
    Write-Output $data
    exit 0
} catch {
    Write-Host "Failed to connect or fetch data: $_"
    exit 1
} 