function fetchData() {
    // Fetch System Stats
    fetch('/api/system_stats')
        .then(response => response.json())
        .then(data => {
            document.getElementById('cpu').textContent = `CPU Usage: ${data.cpu_usage}%`;
            document.getElementById('memory').textContent = `Memory Usage: ${data.memory_usage}%`;
            document.getElementById('disk').textContent = `Disk Usage: ${data.disk_usage}%`;
        });

    // Fetch Installed Updates
    fetch('/api/installed_updates')
        .then(response => response.json())
        .then(data => {
            const updatesList = document.getElementById('updates');
            updatesList.innerHTML = '';
            data.forEach(update => {
                const listItem = document.createElement('li');
                listItem.textContent = update;
                updatesList.appendChild(listItem);
            });
        });

    // Fetch Running Processes
    fetch('/api/running_processes')
        .then(response => response.json())
        .then(data => {
            const processesTable = document.getElementById('processes');
            processesTable.innerHTML = '';
            data.forEach(process => {
                const row = document.createElement('tr');
                row.innerHTML = `<td>${process.pid}</td><td>${process.name}</td><td>${process.cpu}</td><td>${process.memory}</td>`;
                processesTable.appendChild(row);
            });
        });

    // Fetch Network Connections
    fetch('/api/network_connections')
        .then(response => response.json())
        .then(data => {
            const networkTable = document.getElementById('network');
            networkTable.innerHTML = '';
            data.forEach(conn => {
                const row = document.createElement('tr');
                row.innerHTML = `<td>${conn.local_address}</td><td>${conn.remote_address}</td><td>${conn.status}</td>`;
                networkTable.appendChild(row);
            });
        });
}

// Update every 5 seconds
setInterval(fetchData, 5000);

// Initial data load
fetchData();
