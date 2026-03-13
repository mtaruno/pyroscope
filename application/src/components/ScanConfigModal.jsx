import { useMemo, useState } from 'react'
import './ScanConfigModal.css'

const AREA_OPTIONS = [1, 2, 3]
const PRECISION_OPTIONS = [0.25, 0.5, 1]
const SCAN_SECONDS_PER_SQUARE_METER = 5
const SCAN_SECONDS_PER_POINT = 8
const FUEL_ESTIMATE_SECONDS_PER_POINT = 60

const WALL_MARGIN = 0.45

function calcTotalPoints(areaSize, precision, rowSpacing) {
  const ew = areaSize - 2 * WALL_MARGIN
  const eh = areaSize - 2 * WALL_MARGIN
  if (ew <= 0 || eh <= 0) return 1
  const numRows = Math.max(1, Math.ceil(eh / rowSpacing) + 1)
  const numCols = Math.max(1, Math.ceil(ew / precision) + 1)
  return numRows * numCols
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
  const [areaSize, setAreaSize] = useState(3)
  const [precision, setPrecision] = useState(0.5)
  const [originX, setOriginX] = useState(0)
  const [originY, setOriginY] = useState(0)
  const [rowSpacing, setRowSpacing] = useState(0.5)
  const [dwellTime, setDwellTime] = useState(2.0)
  const [waypointTimeout, setWaypointTimeout] = useState(30.0)

  const totalPoints = useMemo(
    () => calcTotalPoints(areaSize, precision, rowSpacing),
    [areaSize, precision, rowSpacing]
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
          <p className="scan-config-label">Area Size (meters)</p>
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

        <div className="scan-config-group">
          <p className="scan-config-label">Area Center in Odom (meters)</p>
          <div className="scan-config-inputs">
            <label className="scan-config-input-label">
              X
              <input
                type="number"
                step="0.1"
                value={originX}
                onChange={(e) => setOriginX(parseFloat(e.target.value) || 0)}
                className="scan-config-input"
              />
            </label>
            <label className="scan-config-input-label">
              Y
              <input
                type="number"
                step="0.1"
                value={originY}
                onChange={(e) => setOriginY(parseFloat(e.target.value) || 0)}
                className="scan-config-input"
              />
            </label>
          </div>
        </div>

        <div className="scan-config-group">
          <p className="scan-config-label">Advanced</p>
          <div className="scan-config-inputs">
            <label className="scan-config-input-label">
              Row spacing (m)
              <input
                type="number"
                step="0.1"
                min="0.1"
                value={rowSpacing}
                onChange={(e) => setRowSpacing(parseFloat(e.target.value) || 0.5)}
                className="scan-config-input"
              />
            </label>
            <label className="scan-config-input-label">
              Dwell time (s)
              <input
                type="number"
                step="0.5"
                min="0"
                value={dwellTime}
                onChange={(e) => setDwellTime(parseFloat(e.target.value) || 2.0)}
                className="scan-config-input"
              />
            </label>
            <label className="scan-config-input-label">
              Waypoint timeout (s)
              <input
                type="number"
                step="1"
                min="5"
                value={waypointTimeout}
                onChange={(e) => setWaypointTimeout(parseFloat(e.target.value) || 30.0)}
                className="scan-config-input"
              />
            </label>
          </div>
        </div>

        <div className="scan-config-summary">
          <p>Points per side: <strong>{Math.round(areaSize / precision) + 1}</strong></p>
          <p>Total points: <strong>{totalPoints}</strong></p>
          <p>Estimated scan time: <strong>{formatDuration(scanEstimateSeconds)}</strong> <span className="scan-config-note">(~5s per m² + ~8s per point)</span></p>
          <p>Estimated full result time: <strong>{formatDuration(fullEstimateSeconds)}</strong> <span className="scan-config-note">(includes fuel API, ~1m per point)</span></p>
        </div>

        <div className="scan-config-actions">
          <button type="button" className="scan-config-btn cancel" onClick={onCancel}>Cancel</button>
          <button
            type="button"
            className="scan-config-btn confirm"
            onClick={() => onConfirm({
              areaSize,
              precision,
              totalPoints,
              originX,
              originY,
              rowSpacing,
              dwellTime,
              waypointTimeout,
            })}
          >
            Start Scan
          </button>
        </div>
      </div>
    </div>
  )
}

export default ScanConfigModal
