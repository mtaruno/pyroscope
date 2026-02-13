import { Edit2, MapPin, Settings, Activity, Thermometer, History, Target, Pause, Play, Square } from 'lucide-react'
import './Sidebar.css'

function Sidebar({
  locationData,
  setLocationData,
  scanConfig,
  scanTarget,
  robotStatus,
  environmentalData,
  scanHistory,
  isScanning,
  isPaused,
  scanProgress,
  scanPhase,
  onStartScan,
  onPauseScan,
  onResumeScan,
  onStopScan
}) {
  const handleZoneNameEdit = () => {
    const newName = prompt('Enter new zone name:', locationData.zoneName)
    if (newName) {
      setLocationData(prev => ({ ...prev, zoneName: newName }))
    }
  }

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="logo">
        <img src="/pyroscope-logo.svg" alt="Pyroscope" className="logo-image" />
      </div>

      {/* Current Location */}
      <section className="sidebar-section">
        <h3 className="section-title">
          <MapPin size={16} />
          Current Location
        </h3>
        <div className="info-card">
          <div className="info-row">
            <span className="info-label">Zone Name:</span>
            <span className="info-value editable" onClick={handleZoneNameEdit}>
              {locationData.zoneName}
              <Edit2 size={12} className="edit-icon" />
            </span>
          </div>
          <div className="info-row">
            <span className="info-label">Latitude:</span>
            <span className="info-value">{locationData.latitude.toFixed(4)}</span>
          </div>
          <div className="info-row">
            <span className="info-label">Longitude:</span>
            <span className="info-value">{locationData.longitude.toFixed(4)}</span>
          </div>
          <div className="info-row">
            <span className="info-label">GPS Accuracy:</span>
            <span className="info-value">±{locationData.gpsAccuracy} m</span>
          </div>
          
          {/* Designated Scan Location */}
          {scanTarget && (
            <>
              <div className="info-divider"></div>
              <div className="subsection-header">
                <Target size={14} />
                <span>Designated Scan Location</span>
              </div>
              <div className="info-row">
                <span className="info-label">Target Lat:</span>
                <span className="info-value scan-target">{scanTarget.lat.toFixed(4)}</span>
              </div>
              <div className="info-row">
                <span className="info-label">Target Lng:</span>
                <span className="info-value scan-target">{scanTarget.lng.toFixed(4)}</span>
              </div>
              <div className="info-row">
                <span className="info-label">Offset:</span>
                <span className="info-value offset-value">
                  {Math.round(Math.sqrt(
                    Math.pow((scanTarget.lat - locationData.latitude) * 111000, 2) +
                    Math.pow((scanTarget.lng - locationData.longitude) * 111000 * Math.cos(locationData.latitude * Math.PI / 180), 2)
                  ))} m from current
                </span>
              </div>
            </>
          )}
          
          {/* Scan Progress */}
          {(isScanning || scanProgress > 0) && (
            <div className="scan-progress-container">
              <div className="scan-progress-header">
                <span className="scan-progress-label">Scan Progress</span>
                <span className="scan-progress-percent">{Math.round(scanProgress)}%</span>
              </div>
              <div className="scan-progress-bar">
                <div 
                  className="scan-progress-fill"
                  style={{ width: `${scanProgress}%` }}
                />
                <div className="scan-progress-robot" style={{ left: `${scanProgress}%` }}>
                  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    {/* Tank body */}
                    <rect x="4" y="10" width="16" height="8" rx="2" fill="#22c55e"/>
                    {/* Tank turret */}
                    <rect x="8" y="6" width="8" height="5" rx="1" fill="#16a34a"/>
                    {/* Tank tracks */}
                    <ellipse cx="7" cy="18" rx="3" ry="2" fill="#166534"/>
                    <ellipse cx="17" cy="18" rx="3" ry="2" fill="#166534"/>
                    {/* Track details */}
                    <rect x="4" y="17" width="16" height="2" fill="#166534"/>
                    {/* Antenna */}
                    <line x1="10" y1="6" x2="10" y2="3" stroke="#22c55e" strokeWidth="1"/>
                    <circle cx="10" cy="2.5" r="1" fill="#4ade80"/>
                    {/* Window/sensor */}
                    <rect x="10" y="7.5" width="4" height="2" rx="0.5" fill="#86efac"/>
                  </svg>
                </div>
              </div>
              <div className="scan-phase">{scanPhase}</div>
            </div>
          )}
          
          {/* Scan Control Buttons */}
          {isScanning ? (
            <div className="scan-controls">
              <button 
                className={`scan-button pause-btn ${isPaused ? 'paused' : ''}`}
                onClick={isPaused ? onResumeScan : onPauseScan}
              >
                {isPaused ? (
                  <>
                    <Play size={20} />
                    <span>Resume</span>
                  </>
                ) : (
                  <>
                    <Pause size={20} />
                    <span>Pause</span>
                  </>
                )}
              </button>
              <button 
                className="scan-button stop-btn"
                onClick={onStopScan}
                title="Stop Scan"
              >
                <Square size={16} fill="currentColor" />
              </button>
            </div>
          ) : (
            <button 
              className="scan-button start-btn"
              onClick={onStartScan}
            >
              {scanProgress >= 100 ? 'New Scan' : 'Start Scan'}
            </button>
          )}
        </div>
      </section>

      {/* Scan Configuration */}
      <section className="sidebar-section">
        <h3 className="section-title">
          <Settings size={16} />
          Scan Configuration
        </h3>
        <div className="info-card">
          <div className="info-row">
            <span className="info-label">Scan Area:</span>
            <span className="info-value">{scanConfig.scanArea}</span>
          </div>
          <div className="info-row">
            <span className="info-label">Boundary Area:</span>
            <span className="info-value">{scanConfig.boundaryArea}</span>
          </div>
          <div className="info-row">
            <span className="info-label">Estimated Duration:</span>
            <span className="info-value">{scanConfig.estimatedDuration}</span>
          </div>
        </div>
      </section>

      {/* Robot Status */}
      <section className="sidebar-section">
        <h3 className="section-title">
          <Activity size={16} />
          Robot Status
        </h3>
        <div className="info-card">
          <div className="info-row">
            <span className="info-label">Battery:</span>
            <span className="info-value">{robotStatus.battery}%</span>
          </div>
          <div className="progress-bar">
            <div 
              className="progress-fill battery"
              style={{ width: `${robotStatus.battery}%` }}
            />
          </div>
          <div className="info-row">
            <span className="info-label">Storage:</span>
            <span className="info-value">
              {robotStatus.storageUsed} GB / {robotStatus.storageTotal} GB
            </span>
          </div>
          <div className="info-row">
            <span className="info-label">Signal Strength:</span>
            <span className={`info-value status-${robotStatus.signalStrength.toLowerCase()}`}>
              {robotStatus.signalStrength}
            </span>
          </div>
          <div className="info-row">
            <span className="info-label">Operating State:</span>
            <span className={`info-value status-${robotStatus.operatingState.toLowerCase()}`}>
              {robotStatus.operatingState}
            </span>
          </div>
        </div>
      </section>

      {/* Environmental Data */}
      <section className="sidebar-section">
        <h3 className="section-title">
          <Thermometer size={16} />
          Environmental Data
        </h3>
        <div className="info-card">
          <div className="info-row">
            <span className="info-label">Air Temperature:</span>
            <span className="info-value">
              {environmentalData.airTemperature !== null 
                ? `${environmentalData.airTemperature} °C` 
                : '— °C'}
            </span>
          </div>
          <div className="info-row">
            <span className="info-label">Air Humidity:</span>
            <span className="info-value">
              {environmentalData.airHumidity !== null 
                ? `${environmentalData.airHumidity} %` 
                : '— %'}
            </span>
          </div>
          <div className="info-row">
            <span className="info-label">Wind Speed:</span>
            <span className="info-value">
              {environmentalData.windSpeed !== null 
                ? `${environmentalData.windSpeed} m/s` 
                : '— m/s'}
            </span>
          </div>
        </div>
      </section>

      {/* Scanning History */}
      <section className="sidebar-section">
        <h3 className="section-title">
          <History size={16} />
          Scanning History
        </h3>
        <div className="history-list">
          {scanHistory.map(item => (
            <div key={item.id} className="history-item">
              <span className={`history-dot risk-${item.riskLevel}`} />
              <span className="history-zone">{item.zone}</span>
              <span className="history-date">{item.date}</span>
            </div>
          ))}
        </div>
      </section>
    </aside>
  )
}

export default Sidebar

