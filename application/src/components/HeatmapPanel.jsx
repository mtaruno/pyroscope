import { useState, useEffect } from 'react'
import { MapContainer, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Layers, Thermometer, Droplets, Flame, AlertTriangle } from 'lucide-react'
import './HeatmapPanel.css'
import SimpleHeatmap from './SimpleHeatmap'
import apiClient from '../services/api'

// Boundary layer component (50m and 200m boundaries)
function BoundaryLayer({ dataPoints }) {
    const map = useMap()

    useEffect(() => {
        if (!dataPoints || dataPoints.length === 0) return

        // Calculate bounds for the data points
        const bounds = L.latLngBounds(dataPoints.map(d => [d.latitude, d.longitude]))
        const center = bounds.getCenter()

        // Calculate 200m boundary
        const lat200Diff = 200 / 111000
        const lng200Diff = 200 / (111000 * Math.cos(center.lat * Math.PI / 180))

        const bounds200m = [
            [center.lat - lat200Diff / 2, center.lng - lng200Diff / 2],
            [center.lat + lat200Diff / 2, center.lng + lng200Diff / 2]
        ]

        const boundary200m = L.rectangle(bounds200m, {
            color: '#22c55e',
            weight: 2,
            fillOpacity: 0,
            fill: false,
            dashArray: '8, 6',
            className: 'boundary-200m',
            interactive: false,
            pane: 'overlayPane'
        }).addTo(map)

        // Calculate 50m boundary
        const lat50Diff = 50 / 111000
        const lng50Diff = 50 / (111000 * Math.cos(center.lat * Math.PI / 180))

        const bounds50m = [
            [center.lat - lat50Diff / 2, center.lng - lng50Diff / 2],
            [center.lat + lat50Diff / 2, center.lng + lng50Diff / 2]
        ]

        const boundary50m = L.rectangle(bounds50m, {
            color: '#ffffff',
            weight: 3,
            fillOpacity: 0,
            fill: false,
            dashArray: '10, 5',
            className: 'boundary-50m',
            interactive: false,
            pane: 'overlayPane'
        }).addTo(map)

        // Fit to 200m boundary with padding
        map.fitBounds(bounds200m, { padding: [40, 40], maxZoom: 20 })

        return () => {
            map.removeLayer(boundary200m)
            map.removeLayer(boundary50m)
        }
    }, [dataPoints, map])

    return null
}

function HeatmapPanel({ scanId, centerLat, centerLng }) {
    const [heatmapData, setHeatmapData] = useState(null)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState(null)
    const [activeLayer, setActiveLayer] = useState('fire_risk')

    // Layer definitions with value extractors for interpolated heatmap
    const layers = [
        {
            id: 'plant_temp',
            name: 'Ground Temp',
            icon: <Thermometer size={16} />,
            extractor: (point) => point.plant_temperature,
            unit: '°C',
            minValue: 20,
            maxValue: 45
        },
        {
            id: 'air_temp',
            name: 'Air Temp',
            icon: <Thermometer size={16} />,
            extractor: (point) => point.air_temperature,
            unit: '°C',
            minValue: 18,
            maxValue: 40
        },
        {
            id: 'humidity',
            name: 'Humidity',
            icon: <Droplets size={16} />,
            extractor: (point) => point.air_humidity,
            unit: '%',
            minValue: 30,
            maxValue: 90
        },
        {
            id: 'one_hour_fuel',
            name: '1-Hour Fuel',
            icon: <Flame size={16} />,
            extractor: (point) => point.one_hour_fuel,
            unit: 't/acre',
            minValue: 0,
            maxValue: 0.1
        },
        {
            id: 'ten_hour_fuel',
            name: '10-Hour Fuel',
            icon: <Flame size={16} />,
            extractor: (point) => point.ten_hour_fuel,
            unit: 't/acre',
            minValue: 0,
            maxValue: 0.2
        },
        {
            id: 'hundred_hour_fuel',
            name: '100-Hour Fuel',
            icon: <Flame size={16} />,
            extractor: (point) => point.hundred_hour_fuel,
            unit: 't/acre',
            minValue: 0,
            maxValue: 0.4
        },
        {
            id: 'fire_risk',
            name: 'Fire Risk',
            icon: <AlertTriangle size={16} />,
            extractor: (point) => point.fire_risk,
            unit: '',
            minValue: 0,
            maxValue: 1.0
        }
    ]

    // Load heatmap data
    useEffect(() => {
        const fetchData = async () => {
            setIsLoading(true)
            setError(null)

            try {
                const data = await apiClient.getHeatmapData(scanId)
                setHeatmapData(data)
            } catch (err) {
                console.error('Failed to load heatmap data:', err)
                setError(err.message || 'Failed to fetch')
            } finally {
                setIsLoading(false)
            }
        }

        if (scanId) {
            fetchData()
        }
    }, [scanId])

    // Get current layer configuration
    const currentLayer = layers.find(l => l.id === activeLayer)

    if (isLoading) {
        return (
            <div className="heatmap-panel">
                <div className="heatmap-loading">Loading heatmap data...</div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="heatmap-panel">
                <div className="heatmap-error">Error loading heatmap: {error}</div>
            </div>
        )
    }

    if (!heatmapData || !heatmapData.data_points || heatmapData.data_points.length === 0) {
        return (
            <div className="heatmap-panel">
                <div className="heatmap-empty">No heatmap data available</div>
            </div>
        )
    }

    return (
        <div className="heatmap-panel">
            {/* Layer Switcher */}
            <div className="heatmap-header">
                <div className="heatmap-title">
                    <Layers size={18} />
                    <span>Heatmap Layers</span>
                    <span className="point-count">({heatmapData.total_points} points)</span>
                </div>

                <div className="layer-switcher">
                    {layers.map(layer => (
                        <button
                            key={layer.id}
                            className={`layer-button ${activeLayer === layer.id ? 'active' : ''}`}
                            onClick={() => setActiveLayer(layer.id)}
                            title={layer.name}
                        >
                            {layer.icon}
                            <span>{layer.name}</span>
                        </button>
                    ))}
                </div>
            </div>

            {/* Map Container */}
            <div className="heatmap-container">
                <MapContainer
                    center={[centerLat || 34.2257, centerLng || -117.8512]}
                    zoom={20}
                    minZoom={20}
                    maxZoom={20}
                    zoomControl={false}
                    dragging={true}
                    scrollWheelZoom={false}
                    doubleClickZoom={false}
                    touchZoom={false}
                    style={{ height: '100%', width: '100%' }}
                >
                    <TileLayer
                        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                        attribution='&copy; Esri'
                        maxNativeZoom={19}
                        maxZoom={20}
                    />

                    {currentLayer && (
                        <>
                            <SimpleHeatmap
                                data={heatmapData.data_points}
                                valueExtractor={currentLayer.extractor}
                                opacity={0.75}
                            />
                            <BoundaryLayer dataPoints={heatmapData.data_points} />
                        </>
                    )}
                </MapContainer>
            </div>

            {/* Legend */}
            <div className="heatmap-legend">
                <div className="legend-header">
                    <span className="legend-title">{currentLayer?.name}</span>
                    {currentLayer?.unit && (
                        <span className="legend-unit">({currentLayer.unit})</span>
                    )}
                </div>
                <div className="legend-gradient"></div>
                <div className="legend-labels">
                    <span>{currentLayer?.minValue || 0}</span>
                    <span>{currentLayer?.maxValue || 1}</span>
                </div>
            </div>
        </div>
    )
}

export default HeatmapPanel
