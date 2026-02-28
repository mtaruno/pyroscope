import { useState, useEffect } from 'react'
import apiClient from '../services/api'
import './SensorPanel.css'

function SensorPanel({ expanded = false }) {
  const [sensorData, setSensorData] = useState({
    temperature: null,
    humidity: null,
    thermal_mean: null,
    thermal_image_url: null,
    rgb_image_url: null,
    timestamp: null
  })
  const [error, setError] = useState(null)
  const [available, setAvailable] = useState(false)

  useEffect(() => {
    // Poll sensor data every 1 second
    const pollSensors = async () => {
      try {
        const data = await apiClient.getLatestSensors()
        setSensorData(data)
        setError(null)
      } catch (err) {
        console.error('Failed to fetch sensor data:', err)
        setError(err.message)
      }
    }

    const pollAvailability = async () => {
      try {
        const status = await apiClient.getSensorsAvailability()
        setAvailable(Boolean(status?.available))
      } catch {
        setAvailable(false)
      }
    }

    pollSensors()
    pollAvailability()
    const interval = setInterval(pollSensors, 1000)
    const availabilityInterval = setInterval(pollAvailability, 2000)

    return () => {
      clearInterval(interval)
      clearInterval(availabilityInterval)
    }
  }, [])

  return (
    <div className="sensor-panel">
      <div className="sensor-panel-header">
        <h3 className="sensor-panel-title">Live Sensors</h3>
        <span className={`sensor-status ${available ? 'ok' : 'bad'}`}>
          {available ? 'sensors available' : 'sensors unavailable'}
        </span>
      </div>

      {expanded && (
        <>
          {error && <div className="sensor-error">Sensor data unavailable</div>}

          <div className="sensor-values">
            <div className="sensor-item">
              <span className="sensor-label">Temperature:</span>
              <span className="sensor-value">
                {sensorData.temperature !== null ? `${sensorData.temperature} °C` : '---'}
              </span>
            </div>

            <div className="sensor-item">
              <span className="sensor-label">Humidity:</span>
              <span className="sensor-value">
                {sensorData.humidity !== null ? `${sensorData.humidity} %` : '---'}
              </span>
            </div>

            <div className="sensor-item">
              <span className="sensor-label">Thermal Mean:</span>
              <span className="sensor-value">
                {sensorData.thermal_mean !== null ? `${sensorData.thermal_mean} °C` : '---'}
              </span>
            </div>
          </div>

          <div className="sensor-images">
            {sensorData.thermal_image_url && (
              <div className="sensor-image-container">
                <p className="sensor-image-label">Thermal Camera</p>
                <img
                  src={apiClient.getThermalImageUrl()}
                  alt="Thermal camera"
                  className="sensor-image"
                  key={sensorData.timestamp}
                />
              </div>
            )}

            {sensorData.rgb_image_url && (
              <div className="sensor-image-container">
                <p className="sensor-image-label">RGB Camera</p>
                <img
                  src={apiClient.getRgbImageUrl()}
                  alt="RGB camera"
                  className="sensor-image"
                  key={sensorData.timestamp}
                />
              </div>
            )}
          </div>

          {sensorData.timestamp && (
            <div className="sensor-timestamp">
              Updated: {new Date(sensorData.timestamp * 1000).toLocaleTimeString()}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default SensorPanel
