// Hardware Monitoring JavaScript

let systemChart = null;
const cpuHistory = [];
const memoryHistory = [];
const maxHistoryLength = 20;

// Initialize hardware monitoring
document.addEventListener('DOMContentLoaded', function() {
    initializeChart();
    updateHardwareStats();
    
    // Update every 3 seconds
    setInterval(updateHardwareStats, 3000);
});

// Initialize Chart.js
function initializeChart() {
    const ctx = document.getElementById('system-chart');
    if (!ctx) return;
    
    systemChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: Array(maxHistoryLength).fill(''),
            datasets: [
                {
                    label: 'CPU %',
                    data: [],
                    borderColor: '#6c9ef8',
                    backgroundColor: 'rgba(108, 158, 248, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true
                },
                {
                    label: 'Memory %',
                    data: [],
                    borderColor: '#8ab4f8',
                    backgroundColor: 'rgba(138, 180, 248, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#e0e0e0',
                        font: {
                            size: 12
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        color: '#888',
                        callback: function(value) {
                            return value + '%';
                        }
                    },
                    grid: {
                        color: 'rgba(100, 100, 200, 0.1)'
                    }
                },
                x: {
                    display: false,
                    grid: {
                        display: false
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            }
        }
    });
}

// Update hardware statistics
async function updateHardwareStats() {
    try {
        const response = await fetch('/api/hardware');
        const data = await response.json();
        
        if (data.success) {
            updateCPU(data.cpu);
            updateMemory(data.memory);
            updateDisk(data.disk);
            updateTemperature(data.temperature);
            updateChart(data.cpu.percent, data.memory.percent);
        }
    } catch (error) {
        console.error('Failed to fetch hardware stats:', error);
    }
}

// Update CPU display
function updateCPU(cpu) {
    const valueEl = document.getElementById('cpu-value');
    const progressEl = document.getElementById('cpu-progress');
    
    if (valueEl && progressEl) {
        valueEl.textContent = cpu.percent.toFixed(1) + '%';
        progressEl.style.width = cpu.percent + '%';
        
        // Color based on usage
        progressEl.className = 'progress-fill';
        if (cpu.percent > 80) {
            progressEl.classList.add('danger');
        } else if (cpu.percent > 60) {
            progressEl.classList.add('warning');
        }
    }
}

// Update Memory display
function updateMemory(memory) {
    const valueEl = document.getElementById('memory-value');
    const progressEl = document.getElementById('memory-progress');
    
    if (valueEl && progressEl) {
        valueEl.textContent = `${memory.used_gb.toFixed(1)} / ${memory.total_gb.toFixed(1)}`;
        progressEl.style.width = memory.percent + '%';
        
        progressEl.className = 'progress-fill';
        if (memory.percent > 85) {
            progressEl.classList.add('danger');
        } else if (memory.percent > 70) {
            progressEl.classList.add('warning');
        }
    }
}

// Update Disk display
function updateDisk(disk) {
    const valueEl = document.getElementById('disk-value');
    const progressEl = document.getElementById('disk-progress');
    
    if (valueEl && progressEl) {
        valueEl.textContent = `${disk.used_gb.toFixed(1)} / ${disk.total_gb.toFixed(1)}`;
        progressEl.style.width = disk.percent + '%';
        
        progressEl.className = 'progress-fill';
        if (disk.percent > 90) {
            progressEl.classList.add('danger');
        } else if (disk.percent > 75) {
            progressEl.classList.add('warning');
        }
    }
}

// Update Temperature display
function updateTemperature(temp) {
    const valueEl = document.getElementById('temp-value');
    const progressEl = document.getElementById('temp-progress');
    
    if (valueEl && progressEl && temp.celsius !== null) {
        valueEl.textContent = temp.celsius.toFixed(1);
        
        // Temperature scale: 0-80°C
        const tempPercent = Math.min((temp.celsius / 80) * 100, 100);
        progressEl.style.width = tempPercent + '%';
        
        progressEl.className = 'progress-fill';
        if (temp.celsius > 70) {
            progressEl.classList.add('danger');
        } else if (temp.celsius > 60) {
            progressEl.classList.add('warning');
        }
    } else if (valueEl) {
        valueEl.textContent = 'N/A';
    }
}

// Update chart with new data
function updateChart(cpuPercent, memoryPercent) {
    if (!systemChart) return;
    
    // Add new data
    cpuHistory.push(cpuPercent);
    memoryHistory.push(memoryPercent);
    
    // Limit history length
    if (cpuHistory.length > maxHistoryLength) {
        cpuHistory.shift();
        memoryHistory.shift();
    }
    
    // Update chart
    systemChart.data.datasets[0].data = [...cpuHistory];
    systemChart.data.datasets[1].data = [...memoryHistory];
    systemChart.update('none'); // Update without animation for smoother experience
}
