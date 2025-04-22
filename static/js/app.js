async function fetchStats() {
    const res = await fetch('/api/system');
    const data = await res.json();
  
    // Fill System Info
    document.getElementById('system-name').innerText = data.system_info.system_name;
    document.getElementById('os-name').innerText = data.system_info.os_name;
    document.getElementById('system-type').innerText = data.system_info.system_type;
    document.getElementById('bios-mode').innerText = data.system_info.bios_mode;
    document.getElementById('processor').innerText = data.system_info.processor;
  
    // Fill basic stats
    document.getElementById('cpu').innerText = data.cpu + '%';
    document.getElementById('memory').innerText = data.memory + '%';
    document.getElementById('disk').innerText = data.disk + '%';
    document.getElementById('boot-time').innerText = data.boot_time;
    document.getElementById('uptime').innerText = data.uptime;
  
    // Assume you have logic to render processes and services elsewhere
    allProcesses = data.processes;
    renderProcesses();
  
    allServices = data.services;
    renderServices();
  }
  
  // Call fetch function after page loads
  window.onload = fetchStats;
  