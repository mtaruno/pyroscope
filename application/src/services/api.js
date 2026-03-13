const API_BASE_URL = 'http://10.19.113.86:8000/api';

class ApiClient {
  async request(endpoint, options = {}) {
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers
    };

    const config = {
      ...options,
      headers
    };

    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, config);

      // Handle errors
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      return response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  // Scan Records
  async getScans(params = {}) {
    const query = new URLSearchParams(params).toString();
    return this.request(`/scans?${query}`);
  }

  async getScanDetail(scanId) {
    return this.request(`/scans/${scanId}`);
  }

  async createScan(scanData) {
    return this.request('/scans', {
      method: 'POST',
      body: JSON.stringify(scanData)
    });
  }

  // Environmental Data
  async uploadEnvironmentalData(scanId, dataArray) {
    return this.request('/environmental', {
      method: 'POST',
      body: JSON.stringify({
        scan_id: scanId,
        data: dataArray
      })
    });
  }

  // Image Upload
  async uploadImage(scanId, file, metadata) {
    const formData = new FormData();
    formData.append('scan_id', scanId);
    formData.append('image_type', metadata.image_type || 'visible');
    formData.append('file', file);

    if (metadata.latitude) formData.append('latitude', metadata.latitude);
    if (metadata.longitude) formData.append('longitude', metadata.longitude);
    if (metadata.captured_at) formData.append('captured_at', metadata.captured_at);
    if (metadata.metadata) formData.append('metadata', JSON.stringify(metadata.metadata));

    const response = await fetch(`${API_BASE_URL}/images/upload`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Image upload failed');
    }

    return response.json();
  }

  getImageUrl(imageId) {
    return `${API_BASE_URL}/images/${imageId}`;
  }

  /** Base URL for API server (no /api suffix), for relative paths like /api/images/1 */
  getBaseUrl() {
    return API_BASE_URL.replace(/\/api\/?$/, '');
  }

  // Robot Status
  async getRobotStatus(robotId) {
    return this.request(`/robot/${robotId}/status`);
  }

  async updateRobotStatus(statusData) {
    return this.request('/robot/status', {
      method: 'POST',
      body: JSON.stringify(statusData)
    });
  }

  // Heatmap Data
  async getHeatmapData(scanId) {
    return this.request(`/scans/${scanId}/heatmap-data`);
  }

  // Waypoint capture (latest + samples list)
  async getLatestCapture(scanId) {
    return this.request(`/scans/${scanId}/latest-capture`);
  }

  async getScanSamples(scanId, params = {}) {
    const query = new URLSearchParams(params).toString();
    return this.request(`/scans/${scanId}/samples?${query}`);
  }

  // Mission Control
  async startCoverageMission(config = {}) {
    return this.request('/robot/mission/start', {
      method: 'POST',
      body: JSON.stringify(config)
    });
  }

  async stopCoverageMission() {
    return this.request('/robot/mission/stop', {
      method: 'POST'
    });
  }

  async getMissionStatus() {
    return this.request('/robot/mission/status');
  }

  async getMissionProgress() {
    return this.request('/robot/mission/progress');
  }

  async estimateFuelForScan(scanId) {
    return this.request(`/images/estimate-fuel/${scanId}`, {
      method: 'POST'
    });
  }

  // Real-time Sensors
  async getLatestSensors() {
    return this.request('/sensors/live-snapshot');
  }

  async getSensorsAvailability() {
    return this.request('/sensors/availability');
  }

  /** Live ROS snapshot for scan modal (temperature, humidity, thermal_mean, image URLs). */
  async getLiveSnapshot() {
    return this.request('/sensors/live-snapshot');
  }

  getThermalImageUrl() {
    return `${API_BASE_URL}/sensors/live/thermal?t=${Date.now()}`;
  }

  getRgbImageUrl() {
    return `${API_BASE_URL}/sensors/live/rgb?t=${Date.now()}`;
  }
}

// Export singleton instance
const apiClient = new ApiClient();
export default apiClient;
