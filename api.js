// api.js - Real API communication
export const API = {
  baseUrl: 'https://your-render-app.onrender.com',
  
  async getSystemStatus() {
    try {
      const res = await fetch(`${this.baseUrl}/api/system`);
      return await res.json();
    } catch (e) {
      console.error("API Error:", e);
      return { status: "offline", lastSync: "Never" };
    }
  },
  
  async getActivities() {
    try {
      const res = await fetch(`${this.baseUrl}/api/activities`);
      return await res.json();
    } catch (e) {
      return [];
    }
  },
  
  async syncNow() {
    try {
      const res = await fetch(`${this.baseUrl}/api/sync`, {
        method: 'POST'
      });
      return await res.json();
    } catch (e) {
      return { success: false, error: e.message };
    }
  }
};
