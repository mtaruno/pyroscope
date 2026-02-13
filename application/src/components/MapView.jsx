import { useState, useEffect, useRef, useMemo } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Rectangle, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Layers, Check, Crosshair } from 'lucide-react'
import './MapView.css'

// Convert meters to degrees (approximate)
const metersToDegreesLat = (meters) => meters / 111000
const metersToDegreesLng = (meters, lat) => meters / (111000 * Math.cos(lat * Math.PI / 180))

// Calculate bounds for a rectangle centered at a point
const getBounds = (center, widthMeters, heightMeters) => {
  const latOffset = metersToDegreesLat(heightMeters / 2)
  const lngOffset = metersToDegreesLng(widthMeters / 2, center.lat)
  
  return [
    [center.lat - latOffset, center.lng - lngOffset], // Southwest
    [center.lat + latOffset, center.lng + lngOffset]  // Northeast
  ]
}

// Clamp position within bounds
const clampPosition = (pos, boundaryCenter, boundarySize, innerSize) => {
  const maxOffset = (boundarySize - innerSize) / 2
  const maxLatOffset = metersToDegreesLat(maxOffset)
  const maxLngOffset = metersToDegreesLng(maxOffset, boundaryCenter.lat)
  
  return {
    lat: Math.max(
      boundaryCenter.lat - maxLatOffset,
      Math.min(boundaryCenter.lat + maxLatOffset, pos.lat)
    ),
    lng: Math.max(
      boundaryCenter.lng - maxLngOffset,
      Math.min(boundaryCenter.lng + maxLngOffset, pos.lng)
    )
  }
}

// Custom marker icons
const createCustomIcon = (color, isRobot = false) => {
  if (isRobot) {
    return L.divIcon({
      className: 'custom-marker robot-marker',
      html: `
        <div class="robot-target" title="Drag to move scan area">
          <div class="target-hitbox"></div>
          <div class="target-outer"></div>
          <div class="target-inner"></div>
          <div class="target-line target-top"></div>
          <div class="target-line target-bottom"></div>
          <div class="target-line target-left"></div>
          <div class="target-line target-right"></div>
          <div class="target-center"></div>
        </div>
      `,
      iconSize: [48, 48],
      iconAnchor: [24, 24]
    })
  }

  const colors = {
    low: '#22c55e',
    medium: '#eab308', 
    high: '#ef4444'
  }

  return L.divIcon({
    className: `custom-marker risk-${color}`,
    html: `
      <div class="marker-pin" style="background: ${colors[color]}">
        <div class="marker-inner"></div>
      </div>
    `,
    iconSize: [24, 24],
    iconAnchor: [12, 12]
  })
}

// Component to store map reference
function MapController({ mapRef }) {
  const map = useMap()
  
  useEffect(() => {
    mapRef.current = map
  }, [map, mapRef])
  
  return null
}

// Draggable robot marker component
function DraggableRobotMarker({ position, onPositionChange, boundaryCenter, boundarySize, scanSize }) {
  const markerRef = useRef(null)
  
  const eventHandlers = useMemo(
    () => ({
      dragend() {
        const marker = markerRef.current
        if (marker != null) {
          const newPos = marker.getLatLng()
          // Clamp position within the boundary
          const clampedPos = clampPosition(
            { lat: newPos.lat, lng: newPos.lng },
            boundaryCenter,
            boundarySize,
            scanSize
          )
          onPositionChange(clampedPos)
        }
      },
    }),
    [onPositionChange, boundaryCenter, boundarySize, scanSize]
  )

  return (
    <Marker
      draggable={true}
      eventHandlers={eventHandlers}
      position={[position.lat, position.lng]}
      ref={markerRef}
      icon={createCustomIcon('robot', true)}
    >
      <Popup>
        <div className="marker-popup">
          <strong>Scan Target Position</strong>
          <br />
          <span>Lat: {position.lat.toFixed(4)}</span>
          <br />
          <span>Lng: {position.lng.toFixed(4)}</span>
          <br />
          <em style={{ fontSize: '0.8em', color: '#666' }}>Drag to adjust scan location</em>
        </div>
      </Popup>
    </Marker>
  )
}

// Marker component that shows popup on hover and navigates on click
function HoverMarker({ marker, onClick }) {
  const markerRef = useRef(null)

  const eventHandlers = useMemo(
    () => ({
      mouseover() {
        const markerEl = markerRef.current
        if (markerEl) {
          markerEl.openPopup()
        }
      },
      mouseout() {
        const markerEl = markerRef.current
        if (markerEl) {
          markerEl.closePopup()
        }
      },
      click() {
        if (onClick) {
          onClick(marker)
        }
      }
    }),
    [marker, onClick]
  )

  const scanDate = marker.scanData?.completedAt || 'N/A'

  return (
    <Marker
      ref={markerRef}
      position={[marker.lat, marker.lng]}
      icon={createCustomIcon(marker.riskLevel, false)}
      eventHandlers={eventHandlers}
    >
      <Popup closeButton={false}>
        <div className="marker-popup clickable">
          <div className="popup-header">
            <strong>
              {marker.scanData?.location || `Area`}
            </strong>
            <span className={`popup-risk ${marker.riskLevel}`}>
              {marker.riskLevel.charAt(0).toUpperCase() + marker.riskLevel.slice(1)} Risk
            </span>
          </div>
          <span className="popup-date">{scanDate}</span>
          <span className="popup-hint">Click to view details</span>
        </div>
      </Popup>
    </Marker>
  )
}

function MapView({ center, markers, robotPosition, onScanTargetChange, onMarkerClick }) {
  const [layerVisibility, setLayerVisibility] = useState({
    low: true,
    medium: true,
    high: true
  })
  const [showLegend, setShowLegend] = useState(true)
  const mapRef = useRef(null)
  
  // Scan target starts at robot position
  const [scanTarget, setScanTarget] = useState(robotPosition)
  
  // Track previous robot position to detect actual GPS changes
  const prevRobotPosRef = useRef(robotPosition)
  
  // Only reset scan target when the actual GPS location changes (not just reference)
  useEffect(() => {
    if (robotPosition && prevRobotPosRef.current) {
      const prevPos = prevRobotPosRef.current
      // Only reset if GPS actually changed significantly (more than 10 meters)
      const latDiff = Math.abs(robotPosition.lat - prevPos.lat)
      const lngDiff = Math.abs(robotPosition.lng - prevPos.lng)
      if (latDiff > 0.0001 || lngDiff > 0.0001) {
        setScanTarget(robotPosition)
        prevRobotPosRef.current = robotPosition
      }
    } else if (robotPosition && !prevRobotPosRef.current) {
      setScanTarget(robotPosition)
      prevRobotPosRef.current = robotPosition
    }
  }, [robotPosition?.lat, robotPosition?.lng])

  const toggleLayer = (layer) => {
    setLayerVisibility(prev => ({
      ...prev,
      [layer]: !prev[layer]
    }))
  }

  const handleCenterOnLocation = () => {
    if (mapRef.current && robotPosition) {
      mapRef.current.flyTo([robotPosition.lat, robotPosition.lng], 17, {
        duration: 1
      })
    }
  }
  
  const handleScanTargetChange = (newPos) => {
    setScanTarget(newPos)
    if (onScanTargetChange) {
      onScanTargetChange(newPos)
    }
  }

  const filteredMarkers = markers.filter(marker => {
    return layerVisibility[marker.riskLevel]
  })

  // Frame sizes in meters
  const BOUNDARY_SIZE = 200 // 200m × 200m
  const SCAN_SIZE = 50 // 50m × 50m

  // Calculate bounds for the frames
  const boundaryBounds = robotPosition ? getBounds(robotPosition, BOUNDARY_SIZE, BOUNDARY_SIZE) : null
  const scanBounds = scanTarget ? getBounds(scanTarget, SCAN_SIZE, SCAN_SIZE) : null

  return (
    <div className="map-container">
      <MapContainer
        center={center}
        zoom={17}
        className="leaflet-map"
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.esri.com/">Esri</a>'
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        />
        <MapController mapRef={mapRef} />
        
        {/* Large boundary frame - 200m × 200m (Green) */}
        {boundaryBounds && (
          <>
            {/* Outer glow effect */}
            <Rectangle
              bounds={boundaryBounds}
              pathOptions={{
                color: '#4ade80',
                weight: 8,
                fill: false,
                opacity: 0.15,
                lineCap: 'square'
              }}
            />
            {/* Main boundary line */}
            <Rectangle
              bounds={boundaryBounds}
              pathOptions={{
                color: '#22c55e',
                weight: 2.5,
                dashArray: '12, 8',
                fill: true,
                fillColor: '#22c55e',
                fillOpacity: 0.03,
                opacity: 0.9,
                lineCap: 'square'
              }}
            />
            {/* Inner accent line */}
            <Rectangle
              bounds={boundaryBounds}
              pathOptions={{
                color: '#86efac',
                weight: 1,
                dashArray: '12, 8',
                dashOffset: '6',
                fill: false,
                opacity: 0.5,
                lineCap: 'square'
              }}
            />
          </>
        )}
        
        {/* Scan area frame - 50m × 50m (White) */}
        {scanBounds && (
          <>
            {/* Outer glow effect */}
            <Rectangle
              bounds={scanBounds}
              pathOptions={{
                color: '#ffffff',
                weight: 10,
                fill: false,
                opacity: 0.25,
                lineCap: 'square'
              }}
            />
            {/* Fill area */}
            <Rectangle
              bounds={scanBounds}
              pathOptions={{
                color: 'transparent',
                weight: 0,
                fill: true,
                fillColor: '#ffffff',
                fillOpacity: 0.08
              }}
            />
            {/* Main scan area line */}
            <Rectangle
              bounds={scanBounds}
              pathOptions={{
                color: '#ffffff',
                weight: 2.5,
                dashArray: '6, 4',
                fill: false,
                opacity: 0.9,
                lineCap: 'square'
              }}
            />
            {/* Inner bright line */}
            <Rectangle
              bounds={scanBounds}
              pathOptions={{
                color: '#e5e5e5',
                weight: 1,
                dashArray: '6, 4',
                dashOffset: '3',
                fill: false,
                opacity: 0.5,
                lineCap: 'square'
              }}
            />
          </>
        )}
        
        {/* Past examination markers - show popup on hover, click to view details */}
        {filteredMarkers.map(marker => (
          <HoverMarker key={marker.id} marker={marker} onClick={onMarkerClick} />
        ))}
        
        {/* Draggable robot marker for scan target */}
        {scanTarget && robotPosition && (
          <DraggableRobotMarker
            position={scanTarget}
            onPositionChange={handleScanTargetChange}
            boundaryCenter={robotPosition}
            boundarySize={BOUNDARY_SIZE}
            scanSize={SCAN_SIZE}
          />
        )}
      </MapContainer>
      
      {/* Center on location button */}
      {robotPosition && (
        <button 
          className="center-location-btn" 
          onClick={handleCenterOnLocation} 
          title="Center on current location"
        >
          <Crosshair size={20} />
        </button>
      )}

      {/* Map Legend */}
      <div className={`map-legend ${showLegend ? 'expanded' : ''}`}>
        <div className="legend-header" onClick={() => setShowLegend(!showLegend)}>
          <Layers size={16} />
          <span>Map Layer</span>
        </div>
        {showLegend && (
          <div className="legend-content">
            <label className="legend-item">
              <input
                type="checkbox"
                checked={layerVisibility.low}
                onChange={() => toggleLayer('low')}
              />
              <span className="checkbox-custom">
                {layerVisibility.low && <Check size={12} />}
              </span>
              <span className="legend-dot low"></span>
              <span>Low Risk Area</span>
            </label>
            <label className="legend-item">
              <input
                type="checkbox"
                checked={layerVisibility.medium}
                onChange={() => toggleLayer('medium')}
              />
              <span className="checkbox-custom">
                {layerVisibility.medium && <Check size={12} />}
              </span>
              <span className="legend-dot medium"></span>
              <span>Medium Risk Area</span>
            </label>
            <label className="legend-item">
              <input
                type="checkbox"
                checked={layerVisibility.high}
                onChange={() => toggleLayer('high')}
              />
              <span className="checkbox-custom">
                {layerVisibility.high && <Check size={12} />}
              </span>
              <span className="legend-dot high"></span>
              <span>High Risk Area</span>
            </label>
            <div className="legend-divider"></div>
            <div className="legend-frame-item">
              <span className="frame-line boundary"></span>
              <span>Boundary (200m)</span>
            </div>
            <div className="legend-frame-item">
              <span className="frame-line scan"></span>
              <span>Scan Area (50m)</span>
            </div>
          </div>
        )}
      </div>

    </div>
  )
}

export default MapView
