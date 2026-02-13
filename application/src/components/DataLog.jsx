import { useState, useRef, useEffect, useCallback } from 'react'
import { ChevronDown, ChevronUp, Database, Maximize2, Minimize2 } from 'lucide-react'
import './DataLog.css'

function DataLog({ logs }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [height, setHeight] = useState(250)
  const [isDragging, setIsDragging] = useState(false)
  const containerRef = useRef(null)
  const startYRef = useRef(0)
  const startHeightRef = useRef(0)

  const getFuelLoadClass = (fuelLoad) => {
    switch (fuelLoad.toLowerCase()) {
      case 'high':
        return 'fuel-high'
      case 'medium':
        return 'fuel-medium'
      case 'low':
        return 'fuel-low'
      default:
        return ''
    }
  }

  const handleMouseDown = useCallback((e) => {
    if (!isExpanded) return
    e.preventDefault()
    setIsDragging(true)
    startYRef.current = e.clientY
    startHeightRef.current = height
  }, [isExpanded, height])

  const handleMouseMove = useCallback((e) => {
    if (!isDragging) return
    const deltaY = startYRef.current - e.clientY
    const newHeight = Math.min(Math.max(startHeightRef.current + deltaY, 150), 500)
    setHeight(newHeight)
  }, [isDragging])

  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
  }, [])

  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = 'ns-resize'
      document.body.style.userSelect = 'none'
    } else {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [isDragging, handleMouseMove, handleMouseUp])

  return (
    <div 
      ref={containerRef}
      className={`data-log-wrapper ${isExpanded ? 'expanded' : 'collapsed'} ${isDragging ? 'dragging' : ''}`}
    >
      <div className="data-log">
        {/* Resize Handle - only visible when expanded */}
        {isExpanded && (
          <div 
            className="resize-handle"
            onMouseDown={handleMouseDown}
          >
            <div className="resize-bar"></div>
          </div>
        )}
        <div className="data-log-header" onClick={() => setIsExpanded(!isExpanded)}>
          <div className="header-left">
            <Database size={18} />
            <h3>Scan Data Log</h3>
            <span className="log-count">{logs.length} records</span>
          </div>
          <button className="toggle-btn" title={isExpanded ? 'Collapse' : 'Expand'}>
            {isExpanded ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
            {isExpanded ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
          </button>
        </div>

        <div 
          className={`data-log-content ${isExpanded ? 'show' : 'hide'}`}
          style={isExpanded ? { maxHeight: `${height}px` } : {}}
        >
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Time</th>
                <th>Zone</th>
                <th>Avg Air Temp (°C)</th>
                <th>Avg Humidity (%)</th>
                <th>Avg Plant Temp</th>
                <th>Fuel Load</th>
              </tr>
            </thead>
            <tbody>
              {logs.map(log => (
                <tr key={log.id}>
                  <td>{log.date}</td>
                  <td>{log.time}</td>
                  <td>{log.zone}</td>
                  <td>{log.avgAirTemp} °C</td>
                  <td>{log.avgHumidity} %</td>
                  <td>{log.avgPlantTemp}</td>
                  <td>
                    <span className={`fuel-badge ${getFuelLoadClass(log.fuelLoad)}`}>
                      {log.fuelLoad}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          {logs.length === 0 && (
            <div className="empty-state">
              <p>No scan data available yet. Start a scan to collect data.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default DataLog
