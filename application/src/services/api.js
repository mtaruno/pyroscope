const API_BASE_URL = 'http://localhost:8000/api';

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
}

// Export singleton instance
const apiClient = new ApiClient();
export default apiClient;
