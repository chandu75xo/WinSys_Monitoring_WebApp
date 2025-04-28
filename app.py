from flask import Flask, render_template, jsonify, request, session
import psutil
import platform
import subprocess
import os
from datetime import datetime
from functools import wraps
import json
import time

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Required for session management

def require_server_connection(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.args.get('remote') == 'true' and 'server_info' not in session:
            return jsonify({"error": "No server connection established"}), 401
        return f(*args, **kwargs)
    return decorated_function

def run_remote_powershell(command, server_info):
    try:
        remote_cmd = f'''powershell "Invoke-Command -ComputerName {server_info['server']} -Credential (New-Object PSCredential('{server_info['username']}', (ConvertTo-SecureString '{server_info['password']}' -AsPlainText -Force))) -ScriptBlock {{
            {command}
        }}"'''
        result = subprocess.run(remote_cmd, capture_output=True, text=True, shell=True)
        return result.stdout
    except Exception as e:
        return str(e)

def get_local_system_details():
    try:
        system_info = {
            "os_name": platform.system(),
            "os_version": platform.version(),
            "os_release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "node_name": platform.node()
        }
        
        if platform.system() == 'Windows':
            commands = {
                "System Model": "wmic computersystem get model",
                "System Type": "wmic computersystem get systemtype",
                "BIOS Version": "wmic bios get smbiosbiosversion",
                "BIOS Date": "wmic bios get releasedate",
                "Total RAM": "wmic computersystem get totalphysicalmemory",
                "Manufacturer": "wmic computersystem get manufacturer"
            }
            
            for key, command in commands.items():
                try:
                    result = subprocess.run(command, capture_output=True, text=True, shell=True)
                    value = result.stdout.strip().split('\n')[-1].strip()
                    system_info[key.lower().replace(' ', '_')] = value
                except Exception as e:
                    system_info[key.lower().replace(' ', '_')] = f"Error: {str(e)}"
        
        return system_info
    except Exception as e:
        return {"error": str(e)}

@app.route("/api/connect", methods=['POST'])
def connect_to_server():
    try:
        # Get the absolute path to the PowerShell script
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'connect_server.ps1')
        
        # Use a simpler command to open PowerShell
        command = f'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& {{Start-Process powershell -ArgumentList \'-NoProfile -ExecutionPolicy Bypass -File \\\"{script_path}\\\"\' -Verb RunAs}}"'
        
        # Run the command
        subprocess.run(command, shell=True)
        
        # Wait a bit for the script to run
        time.sleep(2)
        
        # Read connection info from JSON file
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'connection_info.json')
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                connection_info = json.load(f)
                if connection_info.get('isConnected'):
                    session['server_info'] = {
                        'server': connection_info['server'],
                        'username': connection_info['username'],
                        'password': connection_info['password']
                    }
                    return jsonify(connection_info)
        
        return jsonify({"error": "Connection failed", "isConnected": False}), 401
    except Exception as e:
        return jsonify({"error": str(e), "isConnected": False}), 500

def get_windows_updates(server_info=None):
    try:
        cmd = 'Get-WmiObject -Class Win32_QuickFixEngineering | Select-Object HotFixID, Description, InstalledOn, InstalledBy, Caption, CSName, FixComments | ConvertTo-Json'
        if server_info:
            result = run_remote_powershell(cmd, server_info)
        else:
            result = subprocess.run(f'powershell "{cmd}"', capture_output=True, text=True, shell=True)
            result = result.stdout

        updates = json.loads(result)
        if not isinstance(updates, list):
            updates = [updates]

        formatted_updates = []
        for update in updates:
            formatted_update = {
                'HotFixID': update.get('HotFixID', 'N/A'),
                'Description': update.get('Description', 'N/A'),
                'InstalledOn': update.get('InstalledOn', 'N/A'),
                'InstalledBy': update.get('InstalledBy', 'N/A'),
                'Caption': update.get('Caption', 'N/A'),
                'CSName': update.get('CSName', 'N/A'),
                'FixComments': update.get('FixComments', 'N/A')
            }
            formatted_updates.append(formatted_update)
        return formatted_updates
    except Exception as e:
        return [{"Error": f"Error fetching updates: {str(e)}"}]

def get_logged_in_users(server_info=None):
    try:
        if server_info:
            cmd = 'Get-WmiObject -Class Win32_LoggedOnUser | Select-Object Antecedent,Dependent | ConvertTo-Json'
            result = run_remote_powershell(cmd, server_info)
            users = json.loads(result)
            return [f"{user.get('Antecedent', 'Unknown User')}" for user in users]
        else:
            users = psutil.users()
            return [f"{u.name} (logged in since {datetime.fromtimestamp(u.started)})" for u in users]
    except Exception as e:
        return [f"Error: {e}"]

def get_network_info(server_info=None):
    try:
        if server_info:
            cmd = 'Get-NetAdapter | Select-Object Name,InterfaceDescription,Status | ConvertTo-Json'
            result = run_remote_powershell(cmd, server_info)
            return json.loads(result)
        else:
            info = psutil.net_if_addrs()
            interfaces = {}
            for iface, addrs in info.items():
                ip = [a.address for a in addrs if a.family == 2]
                if ip:
                    interfaces[iface] = ip
            return interfaces
    except Exception as e:
        return {"Error": str(e)}

@app.route("/")
def home():
    return render_template("index.html")

def get_running_services(server_info=None):
    try:
        if server_info:
            cmd = 'Get-Service | Where-Object {$_.Status -eq "Running"} | Select-Object Name,DisplayName,Status | ConvertTo-Json'
            result = run_remote_powershell(cmd, server_info)
            return json.loads(result)
        else:
            services = []
            for s in psutil.win_service_iter():
                try:
                    info = s.as_dict()
                    if info['status'] == 'running':
                        services.append({
                            "name": info["name"],
                            "display_name": info["display_name"],
                            "status": info["status"]
                        })
                except Exception:
                    continue
            return services
    except Exception as e:
        return [{"Error": f"Error fetching services: {str(e)}"}]

@app.route("/api/system")
@require_server_connection
def system_info():
    is_remote = request.args.get('remote') == 'true'
    
    if is_remote and 'server_info' in session:
        server_info = session.get('server_info')
        commands = {
            'cpu': 'Get-WmiObject Win32_Processor | Select-Object LoadPercentage | ConvertTo-Json',
            'memory': 'Get-WmiObject Win32_OperatingSystem | Select-Object @{Name="MemoryUsage";Expression={[math]::Round((1 - $_.FreePhysicalMemory/$_.TotalVisibleMemorySize) * 100, 2)}} | ConvertTo-Json',
            'disk': 'Get-WmiObject Win32_LogicalDisk | Select-Object Size,FreeSpace | ConvertTo-Json',
            'system_details': '''
                $os = Get-WmiObject Win32_OperatingSystem
                $cs = Get-WmiObject Win32_ComputerSystem
                $bios = Get-WmiObject Win32_BIOS
                @{
                    os_name = $os.Caption
                    os_version = $os.Version
                    system_model = $cs.Model
                    system_type = $cs.SystemType
                    processor = $cs.NumberOfProcessors
                    bios_version = $bios.SMBIOSBIOSVersion
                    bios_date = $bios.ReleaseDate
                    manufacturer = $cs.Manufacturer
                    total_ram = [math]::Round($cs.TotalPhysicalMemory/1GB, 2)
                } | ConvertTo-Json
            '''
        }

        results = {}
        for key, command in commands.items():
            output = run_remote_powershell(command, server_info)
            try:
                results[key] = json.loads(output)
            except:
                results[key] = output

        services = get_running_services(server_info)
        results['services'] = services
        
        return jsonify(results)
    else:
        # Local system information collection
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent
        system_details = get_local_system_details()

        processes = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                proc = p.info
                processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        processes.sort(key=lambda x: x['cpu_percent'], reverse=True)

        boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        uptime = str(datetime.now() - datetime.fromtimestamp(psutil.boot_time())).split('.')[0]

        services = get_running_services()

        return jsonify({
            "system_details": system_details,
            "cpu": cpu,
            "memory": memory,
            "disk": disk,
            "processes": processes,
            "boot_time": boot_time,
            "uptime": uptime,
            "services": services
        })

@app.route("/api/updates")
@require_server_connection
def updates_api():
    is_remote = request.args.get('remote') == 'true'
    server_info = session.get('server_info') if is_remote else None
    updates = get_windows_updates(server_info)
    return jsonify({"updates": updates})

@app.route("/api/users")
@require_server_connection
def users_api():
    is_remote = request.args.get('remote') == 'true'
    server_info = session.get('server_info') if is_remote else None
    return jsonify({"users": get_logged_in_users(server_info)})

@app.route("/api/network")
@require_server_connection
def network_api():
    is_remote = request.args.get('remote') == 'true'
    server_info = session.get('server_info') if is_remote else None
    return jsonify({"network": get_network_info(server_info)})

if __name__ == "__main__":
    app.run(debug=True)