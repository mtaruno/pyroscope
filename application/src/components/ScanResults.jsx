import { useState, useEffect } from 'react'
import { ArrowLeft, Edit2, AlertTriangle, Thermometer, Flame, MapPin, FileText, ChevronDown, ChevronUp, Table } from 'lucide-react'
import HeatmapPanel from './HeatmapPanel'
import apiClient from '../services/api'
import './ScanResults.css'

function ScanResults({ scanData, onBack }) {
  // Extract scan ID from scanData
  const scanId = scanData.id || scanData.scanId
  const [pointData, setPointData] = useState(null)
  const [showPointData, setShowPointData] = useState(false)
  const [loadingPoints, setLoadingPoints] = useState(false)
  const [samplesData, setSamplesData] = useState(null)
  const [showSamples, setShowSamples] = useState(false)
  const [loadingSamples, setLoadingSamples] = useState(false)

  // Load point-level data when toggled
  useEffect(() => {
    const loadPointData = async () => {
      if (showPointData && !pointData && scanId) {
        setLoadingPoints(true)
        try {
          const data = await apiClient.getHeatmapData(scanId)
          setPointData(data)
        } catch (error) {
          console.error('Failed to load point data:', error)
        } finally {
          setLoadingPoints(false)
        }
      }
    }
    loadPointData()
  }, [showPointData, scanId, pointData])

  // Load waypoint samples when toggled
  useEffect(() => {
    const loadSamples = async () => {
      if (showSamples && !samplesData && scanId) {
        setLoadingSamples(true)
        try {
          const data = await apiClient.getScanSamples(scanId, { limit: 200 })
          setSamplesData(data)
        } catch (error) {
          console.error('Failed to load waypoint samples:', error)
        } finally {
          setLoadingSamples(false)
        }
      }
    }
    loadSamples()
  }, [showSamples, scanId, samplesData])
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
                <span className="results-label">Avg Ground Temp:</span>
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
              {/* Total Fuel Load */}
              {scanData.fuel_load !== undefined && scanData.fuel_load !== null && (
                <div className="results-row highlight">
                  <span className="results-label">Total Fuel Load:</span>
                  <span className="results-value fuel-total">
                    {scanData.fuel_load.toFixed(3)} tons/acre
                  </span>
                </div>
              )}
              
              {/* Detailed Fuel Breakdown */}
              {scanData.one_hour_fuel !== undefined && scanData.one_hour_fuel !== null && (
                <div className="results-row">
                  <span className="results-label">1-Hour Fuel:</span>
                  <span className="results-value">{scanData.one_hour_fuel.toFixed(3)} tons/acre</span>
                </div>
              )}
              
              {scanData.ten_hour_fuel !== undefined && scanData.ten_hour_fuel !== null && (
                <div className="results-row">
                  <span className="results-label">10-Hour Fuel:</span>
                  <span className="results-value">{scanData.ten_hour_fuel.toFixed(3)} tons/acre</span>
                </div>
              )}
              
              {scanData.hundred_hour_fuel !== undefined && scanData.hundred_hour_fuel !== null && (
                <div className="results-row">
                  <span className="results-label">100-Hour Fuel:</span>
                  <span className="results-value">{scanData.hundred_hour_fuel.toFixed(3)} tons/acre</span>
                </div>
              )}
              
              {/* Pine Cone Count */}
              {scanData.pine_cone_count !== undefined && scanData.pine_cone_count !== null && (
                <div className="results-row">
                  <span className="results-label">Pine Cone Count:</span>
                  <span className="results-value">{scanData.pine_cone_count}</span>
                </div>
              )}
              
              {/* Legacy Fields (if new data not available) */}
              {!scanData.fuel_load && scanData.fuelLoad && (
                <div className="results-row">
                  <span className="results-label">Estimated Fuel Load:</span>
                  <span className={`results-value fuel-${scanData.fuelLoad.toLowerCase()}`}>
                    {scanData.fuelLoad}
                  </span>
                </div>
              )}
              
              {scanData.fuelDensity && (
                <div className="results-row">
                  <span className="results-label">Fuel Density Index:</span>
                  <span className="results-value">{scanData.fuelDensity}</span>
                </div>
              )}
              
              {scanData.biomass && (
                <div className="results-row">
                  <span className="results-label">Estimated Biomass:</span>
                  <span className="results-value">{scanData.biomass} kg / m²</span>
                </div>
              )}
              
              {/* No Data Message */}
              {!scanData.fuel_load && !scanData.fuelLoad && (
                <div className="results-row">
                  <span className="results-value" style={{ color: '#666', fontStyle: 'italic' }}>
                    No fuel estimation data available
                  </span>
                </div>
              )}
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

          {/* Waypoint samples (SHT40 + thermal per waypoint) */}
          <section className="results-section">
            <button
              className="point-data-toggle"
              onClick={() => setShowSamples(!showSamples)}
            >
              <div className="point-data-toggle-header">
                <Thermometer size={16} />
                <span>Waypoint samples</span>
              </div>
              {showSamples ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {showSamples && (
              <div className="point-data-container">
                {loadingSamples ? (
                  <div className="point-data-loading">Loading samples...</div>
                ) : samplesData && samplesData.samples?.length > 0 ? (
                  <div className="point-data-table-wrapper">
                    <div className="point-data-count">
                      {samplesData.total} waypoint sample(s)
                    </div>
                    <table className="point-data-table">
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>RGB</th>
                          <th>Time</th>
                          <th>Air T°</th>
                          <th>Humidity</th>
                          <th>Thermal mean</th>
                        </tr>
                      </thead>
                      <tbody>
                        {samplesData.samples.map((s) => (
                          <tr key={s.sequence_index}>
                            <td>{s.sequence_index + 1}</td>
                            <td>
                              {s.rgb_image_url ? (
                                <a href={apiClient.getBaseUrl() + s.rgb_image_url} target="_blank" rel="noreferrer">
                                  <img
                                    src={apiClient.getBaseUrl() + s.rgb_image_url}
                                    alt={`wp-${s.sequence_index}`}
                                    className="waypoint-rgb-thumb"
                                  />
                                </a>
                              ) : '-'}
                            </td>
                            <td>{s.captured_at ? new Date(s.captured_at).toLocaleString() : '-'}</td>
                            <td>{s.air_temperature != null ? `${s.air_temperature.toFixed(1)} °C` : '-'}</td>
                            <td>{s.air_humidity != null ? `${s.air_humidity.toFixed(0)} %` : '-'}</td>
                            <td>{s.thermal_mean != null ? `${s.thermal_mean.toFixed(1)} °C` : '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="point-data-empty">No waypoint samples for this scan</div>
                )}
              </div>
            )}
          </section>

          {/* Point-Level Data */}
          <section className="results-section">
            <button 
              className="point-data-toggle"
              onClick={() => setShowPointData(!showPointData)}
            >
              <div className="point-data-toggle-header">
                <Table size={16} />
                <span>Point-Level Data</span>
              </div>
              {showPointData ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            
            {showPointData && (
              <div className="point-data-container">
                {loadingPoints ? (
                  <div className="point-data-loading">Loading data...</div>
                ) : pointData && pointData.data_points ? (
                  <div className="point-data-table-wrapper">
                    <div className="point-data-count">
                      {pointData.total_points} measurement points
                    </div>
                    <table className="point-data-table">
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Lat</th>
                          <th>Lng</th>
                          <th>Ground T°</th>
                          <th>Air T°</th>
                          <th>Humidity</th>
                          <th>1h Fuel</th>
                          <th>10h Fuel</th>
                          <th>100h Fuel</th>
                          <th>Risk</th>
                        </tr>
                      </thead>
                      <tbody>
                        {pointData.data_points.map((point, index) => (
                          <tr key={index}>
                            <td>{index + 1}</td>
                            <td>{point.latitude?.toFixed(6) || '-'}</td>
                            <td>{point.longitude?.toFixed(6) || '-'}</td>
                            <td>{point.plant_temperature?.toFixed(1) || '-'}°C</td>
                            <td>{point.air_temperature?.toFixed(1) || '-'}°C</td>
                            <td>{point.air_humidity?.toFixed(0) || '-'}%</td>
                            <td>{point.one_hour_fuel?.toFixed(3) || '-'}</td>
                            <td>{point.ten_hour_fuel?.toFixed(3) || '-'}</td>
                            <td>{point.hundred_hour_fuel?.toFixed(3) || '-'}</td>
                            <td>
                              <span className={`risk-badge risk-${getRiskLevel(point.fire_risk)}`}>
                                {point.fire_risk?.toFixed(2) || '-'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="point-data-empty">No point data available</div>
                )}
              </div>
            )}
          </section>
        </div>

        {/* Right Panel - Heatmap */}
        <div className="results-main">
          {scanId ? (
            <HeatmapPanel 
              scanId={scanId}
              centerLat={parseFloat(scanData.latitude)}
              centerLng={parseFloat(scanData.longitude)}
            />
          ) : (
            <div className="thermal-map-container">
              <div className="thermal-map-placeholder">
                <Thermometer size={48} className="thermal-icon" />
                <h2>Heatmap Visualization</h2>
                <p>No scan ID available</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Helper function to categorize risk level
function getRiskLevel(riskValue) {
  if (!riskValue) return 'unknown'
  if (riskValue < 0.33) return 'low'
  if (riskValue < 0.67) return 'medium'
  return 'high'
}

export default ScanResults

