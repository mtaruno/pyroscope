import { ArrowLeft, Edit2, AlertTriangle, Thermometer, Flame, MapPin, FileText } from 'lucide-react'
import './ScanResults.css'

function ScanResults({ scanData, onBack }) {
  return (
    <div className="scan-results">
      {/* Header */}
      <div className="results-header">
        <button className="back-button" onClick={onBack}>
          <ArrowLeft size={20} />
        </button>
        <h1 className="results-title">{scanData.zoneId}</h1>
      </div>

      <div className="results-content">
        {/* Left Panel */}
        <div className="results-sidebar">
          <div className="status-badge completed">
            Scan Completed
          </div>

          {/* Scan Information */}
          <section className="results-section">
            <h3 className="results-section-title">
              <FileText size={16} />
              Scan Information
            </h3>
            <div className="results-card">
              <div className="results-row">
                <span className="results-label">Location:</span>
                <span className="results-value editable">
                  {scanData.location}
                  <Edit2 size={12} className="edit-icon" />
                </span>
              </div>
              <div className="results-row">
                <span className="results-label">Area Size:</span>
                <span className="results-value">{scanData.areaSize}</span>
              </div>
              <div className="results-row">
                <span className="results-label">Scan Duration:</span>
                <span className="results-value">{scanData.duration}</span>
              </div>
              <div className="results-row">
                <span className="results-label">Completed At:</span>
                <span className="results-value">{scanData.completedAt}</span>
              </div>
            </div>
          </section>

          {/* Data Analysis */}
          <section className="results-section">
            <h3 className="results-section-title">
              <Thermometer size={16} />
              Data Analysis
            </h3>
            <div className="results-card">
              <div className="results-row">
                <span className="results-label">Risk Level:</span>
                <span className={`results-value risk-${scanData.riskLevel.toLowerCase()}`}>
                  {scanData.riskLevel} Risk Area
                </span>
              </div>
              <div className="results-row">
                <span className="results-label">Avg Plant Temp:</span>
                <span className="results-value">{scanData.avgPlantTemp} °C</span>
              </div>
              <div className="results-row">
                <span className="results-label">Avg Air Temp:</span>
                <span className="results-value">{scanData.avgAirTemp} °C</span>
              </div>
              <div className="results-row">
                <span className="results-label">Temp Difference:</span>
                <span className={`results-value ${scanData.tempDiff > 0 ? 'temp-high' : 'temp-low'}`}>
                  {scanData.tempDiff > 0 ? '+' : ''}{scanData.tempDiff} °C
                </span>
              </div>
            </div>
          </section>

          {/* Fuel Estimation */}
          <section className="results-section">
            <h3 className="results-section-title">
              <Flame size={16} />
              Fuel Estimation
            </h3>
            <div className="results-card">
              <div className="results-row">
                <span className="results-label">Estimated Fuel Load:</span>
                <span className={`results-value fuel-${scanData.fuelLoad.toLowerCase()}`}>
                  {scanData.fuelLoad}
                </span>
              </div>
              <div className="results-row">
                <span className="results-label">Fuel Density Index:</span>
                <span className="results-value">{scanData.fuelDensity}</span>
              </div>
              <div className="results-row">
                <span className="results-label">Estimated Biomass:</span>
                <span className="results-value">{scanData.biomass} kg / m²</span>
              </div>
            </div>
          </section>

          {/* Recommendations */}
          <section className="results-section">
            <h3 className="results-section-title">
              <AlertTriangle size={16} />
              Recommendations
            </h3>
            <div className="results-card recommendations">
              <ul className="recommendations-list">
                {scanData.recommendations.map((rec, index) => (
                  <li key={index}>{rec}</li>
                ))}
              </ul>
            </div>
          </section>

          {/* GPS Coordinates */}
          <section className="results-section">
            <h3 className="results-section-title">
              <MapPin size={16} />
              GPS Coordinates
            </h3>
            <div className="results-card">
              <div className="results-row">
                <span className="results-label">Latitude:</span>
                <span className="results-value mono">{scanData.latitude}</span>
              </div>
              <div className="results-row">
                <span className="results-label">Longitude:</span>
                <span className="results-value mono">{scanData.longitude}</span>
              </div>
            </div>
          </section>
        </div>

        {/* Right Panel - Thermal Map */}
        <div className="results-main">
          <div className="thermal-map-container">
            <div className="thermal-map-placeholder">
              <Thermometer size={48} className="thermal-icon" />
              <h2>Thermal Map</h2>
              <p>Thermal imaging data will be displayed here</p>
            </div>
          </div>

          {/* Temperature Legend */}
          <div className="temperature-legend">
            <span className="legend-title">Temperature</span>
            <div className="legend-gradient"></div>
            <div className="legend-labels">
              <span>25°C</span>
              <span>32°C</span>
              <span>40°C</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ScanResults

