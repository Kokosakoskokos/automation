import { dashboardData } from './data.js';
import { API } from './api.js';

class Dashboard {
  constructor() {
    this.init();
    this.updateInterval = setInterval(() => this.update(), 10000);
  }

  async init() {
    await this.update();
    this.setupEventListeners();
  }

  async update() {
    await this.updateSystemInfo();
    await this.updateActivities();
    this.updateLastSync();
  }

  async updateSystemInfo() {
    // Get real system data
    const system = await API.getSystemStatus();
    
    // Update UI
    document.getElementById('statusText').textContent = system.status;
    document.getElementById('statusIndicator').className = 
      `h-3 w-3 rounded-full ${system.status === 'active' ? 'bg-green-500' : 'bg-red-500'}`;
    
    // CPU
    const cpu = dashboardData.system.getCPU();
    if (cpu.percent !== 'N/A') {
      document.getElementById('cpuValue').textContent = `${cpu.percent}% (${cpu.cores} cores)`;
      document.getElementById('cpuBar').style.width = `${cpu.percent}%`;
    }
    
    // Memory
    const memory = dashboardData.system.getMemory();
    if (memory.used !== 'N/A') {
      document.getElementById('memoryValue').textContent = `${memory.used}/${memory.total} GB`;
      const percent = (memory.used / memory.total * 100).toFixed(1);
      document.getElementById('memoryBar').style.width = `${percent}%`;
    }
    
    // Storage
    const storage = await dashboardData.storage.getUsage();
    if (storage.used !== 'N/A') {
      document.getElementById('storageValue').textContent = `${storage.used}/${storage.total}`;
      // Calculate percentage if possible
      if (storage.total > 0) {
        const percent = (parseFloat(storage.used) / parseFloat(storage.total) * 100;
        document.getElementById('storageBar').style.width = `${percent.toFixed(1)}%`;
      }
    }
  }

  async updateActivities() {
    const activities = await API.getActivities();
    dashboardData.activities = activities;
    
    // Update UI with real activities
    activities.forEach(activity => {
      const element = document.querySelector(`[data-activity-id="${activity.id}"]`);
      if (element) {
        element.querySelector('.progress-bar').style.width = `${activity.progress}%`;
        element.querySelector('.activity-time').textContent = activity.time;
      }
    });
  }

  updateLastSync() {
    const lastSync = localStorage.getItem('lastSync') || 'Never';
    document.getElementById('lastSyncTime').textContent = lastSync;
  }

  setupEventListeners() {
    document.getElementById('manualSyncBtn').addEventListener('click', async () => {
      const btn = document.getElementById('manualSyncBtn');
      btn.disabled = true;
      btn.innerHTML = '<i class="fas fa-sync-alt fa-spin mr-2"></i> Syncing...';
      
      const result = await API.syncNow();
      if (result.success) {
        localStorage.setItem('lastSync', new Date().toLocaleString());
        this.update();
      }
      
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-sync-alt mr-2"></i> Sync Now';
    });
  }
}

// Initialize when DOM loads
document.addEventListener('DOMContentLoaded', () => new Dashboard());
