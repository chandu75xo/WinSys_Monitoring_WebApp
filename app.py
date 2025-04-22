from flask import Flask, render_template, jsonify
import psutil
import platform
import subprocess
import os
from datetime import datetime

app = Flask(__name__)

def get_windows_updates():
    try:
        cmd = 'powershell "Get-WmiObject -Class Win32_QuickFixEngineering | Select-Object -ExpandProperty HotFixID"'
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        updates = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return updates
    except Exception as e:
        return [f"Error fetching updates: {e}"]

def get_logged_in_users():
    try:
        users = psutil.users()
        return [f"{u.name} (logged in since {u.started})" for u in users]
    except Exception as e:
        return [f"Error: {e}"]

def get_network_info():
    try:
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

def get_running_services():
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

@app.route("/api/system")
def system_info():
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent

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
        "cpu": cpu,
        "memory": memory,
        "disk": disk,
        "processes": processes,
        "boot_time": boot_time,
        "uptime": uptime,
        "services": services
    })
@app.route("/api/updates")
def updates_api():
    updates = get_windows_updates()
    return jsonify({"updates": updates})

@app.route("/api/users")
def users_api():
    return jsonify({"users": get_logged_in_users()})

@app.route("/api/network")
def network_api():
    return jsonify({"network": get_network_info()})

if __name__ == "__main__":
    app.run(debug=True)
