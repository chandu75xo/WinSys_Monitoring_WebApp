from flask import Flask, render_template, jsonify, request, session, Response, redirect, url_for
import psutil
import platform
import subprocess
import os
from datetime import datetime
from functools import wraps
import json
import time
import logging

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
                "Manufacturer": "wmic computersystem get manufacturer",
                "System Architecture": "wmic os get osarchitecture",
                "CPU Cores": "wmic cpu get numberofcores",
                "System Family": "wmic computersystem get systemfamily",
                "System SKU": "wmic computersystem get systemsku",
                "System Serial": "wmic bios get serialnumber"
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

@app.route("/")
def landing():
    return render_template("connect.html")

@app.route("/dashboard")
def dashboard():
    return render_template("index.html")

@app.route("/api/connect", methods=['POST'])
def connect_to_server():
    try:
        data = request.get_json()
        server = data.get('server')
        username = data.get('username')
        password = data.get('password')
        if not all([server, username, password]):
            return jsonify({"error": "Missing credentials", "isConnected": False}), 400
        # Store remote connection info in session
        session['server_info'] = {'server': server, 'username': username, 'password': password}
        session['connection_type'] = 'remote'
        return jsonify({"isConnected": True})
    except Exception as e:
        return jsonify({"error": str(e), "isConnected": False}), 500

@app.route("/api/local", methods=['POST'])
def monitor_local():
    session.pop('server_info', None)
    session['connection_type'] = 'local'
    return jsonify({"success": True})

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
            installed_on = update.get('InstalledOn', 'N/A')
            # If InstalledOn is a dict/object, convert to string
            if isinstance(installed_on, dict):
                installed_on = installed_on.get('DateTime', str(installed_on))
            elif not isinstance(installed_on, str):
                installed_on = str(installed_on)
            formatted_update = {
                'HotFixID': update.get('HotFixID', 'N/A'),
                'Description': update.get('Description', 'N/A'),
                'InstalledOn': installed_on,
                'InstalledBy': update.get('InstalledBy', 'N/A'),
                'Caption': update.get('Caption', 'N/A'),
                'CSName': update.get('CSName', 'N/A'),
                'FixComments': update.get('FixComments', 'N/A')
            }
            formatted_updates.append(formatted_update)

        # Sort updates by InstalledOn (latest first)
        def parse_date(val):
            try:
                # Try to parse as date string (common formats)
                for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%b-%y"):
                    try:
                        return datetime.strptime(val, fmt)
                    except Exception:
                        continue
            except Exception:
                pass
            return datetime.min
        formatted_updates.sort(key=lambda u: parse_date(u['InstalledOn']), reverse=True)
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

@app.route("/api/system")
@require_server_connection
def system_info():
    connection_type = session.get('connection_type', 'local')
    is_remote = connection_type == 'remote'
    
    try:
        if is_remote and 'server_info' in session:
            server_info = session.get('server_info')
            # Test the connection first
            test_cmd = 'Test-WSMan -ComputerName {0} -Credential (New-Object PSCredential(\'{1}\', (ConvertTo-SecureString \'{2}\' -AsPlainText -Force)))'.format(
                server_info['server'], server_info['username'], server_info['password']
            )
            test_result = subprocess.run(f'powershell "{test_cmd}"', capture_output=True, text=True, shell=True)
            
            if test_result.returncode != 0:
                session.pop('server_info', None)
                return jsonify({"error": "Connection lost", "isConnected": False}), 401
            
            # Rest of your remote system info collection code...
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
                remote_cmd = f'''powershell "Invoke-Command -ComputerName {server_info['server']} -Credential (New-Object PSCredential('{server_info['username']}', (ConvertTo-SecureString '{server_info['password']}' -AsPlainText -Force))) -ScriptBlock {{
                    {command}
                }}"'''
                output = subprocess.run(remote_cmd, capture_output=True, text=True, shell=True)
                try:
                    results[key] = json.loads(output.stdout)
                except:
                    results[key] = output.stdout

            services = get_running_services(server_info)
            results['services'] = services
            
            return jsonify(results)
        else:
            # Local system information collection
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory().percent
            root = os.environ.get('SystemDrive', 'C:') + '\\'
            disk = psutil.disk_usage(root).percent
            system_details = get_local_system_details()

            processes = []
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    proc = p.info
                    processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)

            # Return ALL services, not just running
            services = []
            for s in psutil.win_service_iter():
                try:
                    info = s.as_dict()
                    services.append({
                        "name": info["name"],
                        "display_name": info["display_name"],
                        "status": info["status"],
                        "start_type": info.get("start_type", "N/A")
                    })
                except Exception:
                    continue

            boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
            uptime = str(datetime.now() - datetime.fromtimestamp(psutil.boot_time())).split('.')[0]

            return jsonify({
                "system_details": system_details,
                "cpu": cpu,
                "memory": memory,
                "disk": disk,
                "processes": processes,
                "services": services,
                "boot_time": boot_time,
                "uptime": uptime
            })
    except Exception as e:
        return jsonify({"error": str(e), "isConnected": False}), 500

@app.route("/api/updates")
@require_server_connection
def updates_api():
    is_remote = session.get('connection_type', 'local') == 'remote'
    server_info = session.get('server_info') if is_remote else None
    try:
        cmd = 'Get-WmiObject -Class Win32_QuickFixEngineering | Select-Object HotFixID, Description, InstalledOn, InstalledBy, Caption, CSName, FixComments | ConvertTo-Json -Depth 4'
        if server_info:
            result = run_remote_powershell(cmd, server_info)
        else:
            result = subprocess.run(f'powershell "{cmd}"', capture_output=True, text=True, shell=True)
            result = result.stdout
        updates = json.loads(result)
        if not isinstance(updates, list):
            updates = [updates]
        # Sort updates by InstalledOn descending (latest first)
        def parse_date(val):
            try:
                for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%b-%y"):
                    try:
                        return datetime.strptime(val, fmt)
                    except Exception:
                        continue
            except Exception:
                pass
            return datetime.min
        updates.sort(key=lambda u: parse_date(u.get('InstalledOn', '')), reverse=True)
        return jsonify({"updates": updates})
    except Exception as e:
        return jsonify({"updates": [], "error": str(e)})

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

def get_drive_info():
    drives = []
    for partition in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            drive_info = {
                "drive": partition.device,
                "mountpoint": partition.mountpoint,
                "fstype": partition.fstype,
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "used_percent": usage.percent,
                "free_percent": 100 - usage.percent
            }
            drives.append(drive_info)
        except Exception:
            continue
    return drives

@app.route("/api/stream")
def stream():
    connection_type = session.get('connection_type', 'local')
    is_remote = connection_type == 'remote'
    server_info = session.get('server_info') if is_remote else None
    def generate(is_remote, server_info):
        # Initialize counters
        last_net_io = psutil.net_io_counters()
        last_disk_io = psutil.disk_io_counters()
        last_time = time.time()
        
        # Pre-initialize CPU monitoring
        psutil.cpu_percent(interval=None)
        
        while True:
            try:
                # Get system stats (non-blocking)
                cpu = psutil.cpu_percent(interval=None)
                memory = psutil.virtual_memory().percent
                disk = psutil.disk_usage("/").percent
                
                # Get drive information
                drives = get_drive_info()
                
                # Network stats
                current_net_io = psutil.net_io_counters()
                current_time = time.time()
                time_diff = current_time - last_time
                
                if current_net_io and time_diff > 0:
                    download_speed = (current_net_io.bytes_recv - last_net_io.bytes_recv) / time_diff
                    upload_speed = (current_net_io.bytes_sent - last_net_io.bytes_sent) / time_diff
                    total_download = current_net_io.bytes_recv / (1024 * 1024)
                    total_upload = current_net_io.bytes_sent / (1024 * 1024)
                else:
                    download_speed = upload_speed = total_download = total_upload = 0.0
                
                # Disk I/O stats
                current_disk_io = psutil.disk_io_counters()
                if current_disk_io and time_diff > 0:
                    disk_read_speed = (current_disk_io.read_bytes - last_disk_io.read_bytes) / time_diff
                    disk_write_speed = (current_disk_io.write_bytes - last_disk_io.write_bytes) / time_diff
                    disk_read_ops = (current_disk_io.read_count - last_disk_io.read_count) / time_diff
                    disk_write_ops = (current_disk_io.write_count - last_disk_io.write_count) / time_diff
                else:
                    disk_read_speed = disk_write_speed = disk_read_ops = disk_write_ops = 0.0
                
                # Update last values
                last_net_io = current_net_io
                last_disk_io = current_disk_io
                last_time = current_time
                
                # Get all processes without limiting
                processes = []
                for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                    try:
                        proc = p.info
                        processes.append(proc)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
                
                # Get all services without limiting
                services = []
                for s in psutil.win_service_iter():
                    try:
                        info = s.as_dict()
                        services.append({
                            "name": info["name"],
                            "display_name": info["display_name"],
                            "status": info["status"]
                        })
                    except Exception:
                        continue
                
                # Create minimal data object with millisecond precision
                data = {
                    "cpu": round(cpu, 2),
                    "memory": round(memory, 2),
                    "disk": round(disk, 2),
                    "drives": drives,
                    "processes": processes,
                    "services": services,
                    "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                    "network": {
                        "download_speed": round(download_speed / (1024 * 1024), 3),
                        "upload_speed": round(upload_speed / (1024 * 1024), 3),
                        "total_download": round(total_download, 3),
                        "total_upload": round(total_upload, 3)
                    },
                    "disk_io": {
                        "read_speed": round(disk_read_speed / (1024 * 1024), 3),
                        "write_speed": round(disk_write_speed / (1024 * 1024), 3),
                        "read_ops": round(disk_read_ops, 3),
                        "write_ops": round(disk_write_ops, 3)
                    }
                }
                
                # Send data immediately without any delay
                yield f"data: {json.dumps(data)}\n\n"
                time.sleep(0.01)  # Add this line for 10ms sleep
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(generate(is_remote, server_info), mimetype='text/event-stream')

if __name__ == "__main__":
    app.run(debug=True)