import { useMemo, useState } from 'react'
import './ScanConfigModal.css'

const AREA_OPTIONS = [3, 25, 50]
const PRECISION_OPTIONS = [1, 5]
const SCAN_SECONDS_PER_SQUARE_METER = 60
const SCAN_SECONDS_PER_POINT = 5
const FUEL_ESTIMATE_SECONDS_PER_POINT = 60

function calcTotalPoints(areaSize, precision) {
  const pointsPerSide = Math.round(areaSize / precision) + 1
  return pointsPerSide * pointsPerSide
}

function formatDuration(totalSeconds) {
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  if (hours > 0) return `${hours}h ${minutes}m`
  if (minutes > 0) return `${minutes}m ${seconds}s`
  return `${seconds}s`
}

function ScanConfigModal({ open, onCancel, onConfirm }) {
  const [areaSize, setAreaSize] = useState(50)
  const [precision, setPrecision] = useState(5)

  const totalPoints = useMemo(
    () => calcTotalPoints(areaSize, precision),
    [areaSize, precision]
  )
  const areaSquareMeters = areaSize * areaSize
  const scanEstimateSeconds =
    (areaSquareMeters * SCAN_SECONDS_PER_SQUARE_METER) +
    (totalPoints * SCAN_SECONDS_PER_POINT)
  const fullEstimateSeconds = scanEstimateSeconds + (totalPoints * FUEL_ESTIMATE_SECONDS_PER_POINT)

  if (!open) return null

  return (
    <div className="scan-config-overlay" role="dialog" aria-label="Scan configuration">
      <div className="scan-config-content">
        <h3 className="scan-config-title">Start Scan Configuration</h3>

        <div className="scan-config-group">
          <p className="scan-config-label">Area Size</p>
          <div className="scan-config-options">
            {AREA_OPTIONS.map((value) => (
              <button
                key={value}
                type="button"
                className={`scan-config-option ${areaSize === value ? 'active' : ''}`}
                onClick={() => setAreaSize(value)}
              >
                {value} x {value}
              </button>
            ))}
          </div>
        </div>

        <div className="scan-config-group">
          <p className="scan-config-label">Sampling Precision</p>
          <div className="scan-config-options">
            {PRECISION_OPTIONS.map((value) => (
              <button
                key={value}
                type="button"
                className={`scan-config-option ${precision === value ? 'active' : ''}`}
                onClick={() => setPrecision(value)}
              >
                {value}m
              </button>
            ))}
          </div>
        </div>

        <div className="scan-config-summary">
          <p>Points per side: <strong>{Math.round(areaSize / precision) + 1}</strong></p>
          <p>Total points: <strong>{totalPoints}</strong></p>
          <p>Estimated scan time: <strong>{formatDuration(scanEstimateSeconds)}</strong> <span className="scan-config-note">(~1 min per m² + ~5s per point)</span></p>
          <p>Estimated full result time: <strong>{formatDuration(fullEstimateSeconds)}</strong> <span className="scan-config-note">(includes fuel API, ~1m per point)</span></p>
        </div>

        <div className="scan-config-actions">
          <button type="button" className="scan-config-btn cancel" onClick={onCancel}>Cancel</button>
          <button
            type="button"
            className="scan-config-btn confirm"
            onClick={() => onConfirm({ areaSize, precision, totalPoints })}
          >
            Start Scan
          </button>
        </div>
      </div>
    </div>
  )
}

export default ScanConfigModal
