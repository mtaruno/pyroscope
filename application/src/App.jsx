import { useState, useEffect, useRef } from 'react'
import Sidebar from './components/Sidebar'
import MapView from './components/MapView'
import DataLog from './components/DataLog'
import ScanResults from './components/ScanResults'
import apiClient from './services/api'
import './App.css'

function App() {
  const [locationData, setLocationData] = useState({
    zoneName: 'Area A-01',
    latitude: 47.1607476,
    longitude: -120.7953433,
    gpsAccuracy: 2.3
  })

  const [scanConfig, setScanConfig] = useState({
    scanArea: '50 m × 50 m',
    boundaryArea: '200 m × 200 m',
    estimatedDuration: '~ 15 min'
  })

  // Scan target position (where the robot will scan, can be dragged within boundary)
  const [scanTarget, setScanTarget] = useState({
    lat: 34.2257,
    lng: -117.8512
  })

  const [robotStatus, setRobotStatus] = useState({
    battery: 100,
    storageUsed: 0,
    storageTotal: 8,
    signalStrength: 'Good',
    operatingState: 'Idle'
  })

  const [environmentalData, setEnvironmentalData] = useState({
    airTemperature: null,
    airHumidity: null,
    windSpeed: null
  })

  const [scanHistory, setScanHistory] = useState([
    { id: 1, zone: 'Area A-01', date: '2026.02.01', riskLevel: 'high' },
    { id: 2, zone: 'Area B-03', date: '2026.01.28', riskLevel: 'low' }
  ])

  const [scanLogs, setScanLogs] = useState([])
  const [isLoadingScans, setIsLoadingScans] = useState(false)

  // Past examination GPS points (from previous scans) - loaded from API
  const [mapMarkers, setMapMarkers] = useState([])

  const [isScanning, setIsScanning] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [scanProgress, setScanProgress] = useState(0)
  const [scanPhase, setScanPhase] = useState('')
  const [showResults, setShowResults] = useState(false)
  const [scanResultData, setScanResultData] = useState(null)
  const scanIntervalRef = useRef(null)

  // Load scans from API on component mount
  useEffect(() => {
    const loadScans = async () => {
      setIsLoadingScans(true)
      try {
        // Try to load scans - works with or without authentication
        const response = await apiClient.getScans({ limit: 50 }).catch(() => ({ total: 0, scans: [] }))

        if (response && response.scans) {
          // Transform API data to map markers format
          const markers = response.scans.map(scan => ({
            id: scan.id,
            lat: scan.latitude,
            lng: scan.longitude,
            riskLevel: scan.risk_level || 'medium',
            scanData: {
              zoneId: scan.zone_id || 'Unknown',
              location: `Area ${scan.zone_id}`,  // 使用 zone_id 生成显示名称
              areaSize: scan.scan_area || '50 m × 50 m',
              duration: scan.duration || 'N/A',
              completedAt: scan.completed_at ? new Date(scan.completed_at).toLocaleString() : 'N/A',
              riskLevel: scan.risk_level ? scan.risk_level.charAt(0).toUpperCase() + scan.risk_level.slice(1) : 'Medium',
              avgPlantTemp: scan.avg_plant_temp || 0,
              avgAirTemp: scan.avg_air_temp || 0,
              tempDiff: scan.temp_diff || 0,
              fuelLoad: scan.fuel_load || 'Unknown',
              fuelDensity: scan.fuel_density || 0,
              biomass: scan.biomass || 0,
              recommendations: [
                'View detailed analysis',
                'Check environmental data',
                'Review scan images'
              ],
              latitude: scan.latitude.toFixed(6),
              longitude: scan.longitude.toFixed(6)
            }
          }))
          setMapMarkers(markers)

          // Transform for data log table
          const logs = response.scans.map(scan => ({
            id: scan.id,
            date: scan.completed_at ? new Date(scan.completed_at).toLocaleDateString('en-GB').replace(/\//g, '.') : 'N/A',
            time: scan.completed_at ? new Date(scan.completed_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }).replace(':', '.') : 'N/A',
            zone: scan.zone_id || 'N/A',
            avgAirTemp: scan.avg_air_temp || 0,
            avgHumidity: scan.avg_humidity || 0,
            avgPlantTemp: scan.avg_plant_temp || 0,
            fuelLoad: (scan.fuel_load !== null && scan.fuel_load !== undefined) ? parseFloat(scan.fuel_load) : null
          }))
          setScanLogs(logs)

          // Update scan history for sidebar - show all scans
          const history = response.scans.map(scan => ({
            id: scan.id,
            zone: `Area ${scan.zone_id}`,  // 使用 zone_id 生成显示名称
            date: scan.completed_at ? new Date(scan.completed_at).toLocaleDateString('en-GB').replace(/\//g, '.') : 'N/A',
            riskLevel: scan.risk_level || 'medium'
          }))
          setScanHistory(history)
        }
      } catch (error) {
        console.error('Failed to load scans:', error)
        // Set empty arrays if loading fails
        setMapMarkers([])
        setScanLogs([])
        setScanHistory([])
      } finally {
        setIsLoadingScans(false)
      }
    }

    loadScans()

    // Poll for new scans every 10 seconds
    const pollInterval = setInterval(loadScans, 10000)

    return () => clearInterval(pollInterval)
  }, [])

  // Poll robot status
  useEffect(() => {
    const pollRobotStatus = async () => {
      try {
        const status = await apiClient.getRobotStatus('ROBOT-001')
        setRobotStatus({
          battery: status.battery_level || 100,
          storageUsed: status.storage_used || 0,
          storageTotal: status.storage_total || 8,
          signalStrength: status.signal_strength || 'Good',
          operatingState: status.operating_state ?
            status.operating_state.charAt(0).toUpperCase() + status.operating_state.slice(1) : 'Idle'
        })

        // Update location if available
        if (status.latitude && status.longitude) {
          setLocationData(prev => ({
            ...prev,
            latitude: status.latitude,
            longitude: status.longitude
          }))
        }
      } catch (error) {
        // Silently fail if not authenticated or robot not found
        console.log('Robot status not available:', error.message)
      }
    }

    pollRobotStatus()
    const statusInterval = setInterval(pollRobotStatus, 5000)

    return () => clearInterval(statusInterval)
  }, [])

  // Simulate scan progress
  useEffect(() => {
    if (isScanning && !isPaused) {
      if (scanProgress === 0) {
        setScanPhase('Initializing...')
      }

      scanIntervalRef.current = setInterval(() => {
        setScanProgress(prev => {
          const newProgress = prev + Math.random() * 2 + 0.5

          // Update phase based on progress
          if (newProgress < 10) {
            setScanPhase('Initializing sensors...')
          } else if (newProgress < 25) {
            setScanPhase('Calibrating thermal camera...')
          } else if (newProgress < 40) {
            setScanPhase('Scanning quadrant 1/4...')
          } else if (newProgress < 55) {
            setScanPhase('Scanning quadrant 2/4...')
          } else if (newProgress < 70) {
            setScanPhase('Scanning quadrant 3/4...')
          } else if (newProgress < 85) {
            setScanPhase('Scanning quadrant 4/4...')
          } else if (newProgress < 95) {
            setScanPhase('Processing data...')
          } else {
            setScanPhase('Finalizing report...')
          }

          if (newProgress >= 100) {
            clearInterval(scanIntervalRef.current)
            setIsScanning(false)
            setRobotStatus(prev => ({ ...prev, operatingState: 'Idle' }))
            setScanPhase('Scan complete!')

            // Generate scan results and upload to backend
            setTimeout(async () => {
              const now = new Date()
              const scanData = {
                zoneId: locationData.zoneName.split(' ').pop() || 'A-01',
                location: locationData.zoneName,
                areaSize: scanConfig.scanArea,
                duration: '15 min 32 sec',
                completedAt: now.toLocaleDateString('en-GB', {
                  day: '2-digit',
                  month: 'short',
                  year: 'numeric'
                }) + ' ' + now.toLocaleTimeString('en-GB', {
                  hour: '2-digit',
                  minute: '2-digit'
                }),
                riskLevel: 'High',
                avgPlantTemp: 33.0,
                avgAirTemp: 29.3,
                tempDiff: 3.7,
                fuelLoad: 'High',
                fuelDensity: 0.78,
                biomass: 1.9,
                recommendations: [
                  'Action required',
                  'Inspect area immediately',
                  'Check for pests or drought'
                ],
                latitude: scanTarget.lat.toFixed(6),
                longitude: scanTarget.lng.toFixed(6)
              }

              // Upload scan to backend
              try {
                const uploadData = {
                  zone_id: scanData.zoneId,
                  latitude: scanTarget.lat,
                  longitude: scanTarget.lng,
                  gps_accuracy: locationData.gpsAccuracy,
                  scan_area: scanData.areaSize,
                  duration: scanData.duration,
                  risk_level: scanData.riskLevel.toLowerCase(),
                  avg_plant_temp: scanData.avgPlantTemp,
                  avg_air_temp: scanData.avgAirTemp,
                  avg_humidity: environmentalData.airHumidity,
                  wind_speed: environmentalData.windSpeed,
                  temp_diff: scanData.tempDiff,
                  fuel_load: scanData.fuelLoad,
                  fuel_density: scanData.fuelDensity,
                  biomass: scanData.biomass,
                  robot_id: 'ROBOT-001',
                  completed_at: now.toISOString()
                }

                const response = await apiClient.createScan(uploadData)
                console.log('Scan uploaded successfully:', response)

                // Reload scans to show the new one
                setTimeout(() => {
                  // Trigger a reload by calling the API
                  apiClient.getScans({ limit: 50 }).then(response => {
                    if (response && response.scans) {
                      const markers = response.scans.map(scan => ({
                        id: scan.id,
                        lat: scan.latitude,
                        lng: scan.longitude,
                        riskLevel: scan.risk_level || 'medium',
                        scanData: {
                          zoneId: scan.zone_id || 'Unknown',
                          location: `Area ${scan.zone_id}`,
                          areaSize: scan.scan_area || '50 m × 50 m',
                          duration: scan.duration || 'N/A',
                          completedAt: scan.completed_at ? new Date(scan.completed_at).toLocaleString() : 'N/A',
                          riskLevel: scan.risk_level ? scan.risk_level.charAt(0).toUpperCase() + scan.risk_level.slice(1) : 'Medium',
                          avgPlantTemp: scan.avg_plant_temp || 0,
                          avgAirTemp: scan.avg_air_temp || 0,
                          tempDiff: scan.temp_diff || 0,
                          fuelLoad: scan.fuel_load || 'Unknown',
                          fuelDensity: scan.fuel_density || 0,
                          biomass: scan.biomass || 0,
                          recommendations: [
                            'View detailed analysis',
                            'Check environmental data',
                            'Review scan images'
                          ],
                          latitude: scan.latitude.toFixed(6),
                          longitude: scan.longitude.toFixed(6)
                        }
                      }))
                      setMapMarkers(markers)
                    }
                  }).catch(err => console.error('Failed to reload scans:', err))
                }, 2000)
              } catch (error) {
                console.error('Failed to upload scan:', error)
              }

              setScanResultData(scanData)
              setShowResults(true)
            }, 1000)

            return 100
          }
          return newProgress
        })
      }, 500)
    }

    return () => {
      if (scanIntervalRef.current) {
        clearInterval(scanIntervalRef.current)
      }
    }
  }, [isScanning, isPaused])

  const handleStartScan = async () => {
    try {
      const missionConfig = {
        area_width: 5.0,
        area_height: 5.0,
        row_spacing: 0.8,
        waypoint_spacing: 0.5,
        origin_x: 0.0,
        origin_y: 0.0,
        dwell_time: 2.0,
        waypoint_timeout: 30.0
      }
      await apiClient.startCoverageMission(missionConfig)
      console.log('Coverage mission started on robot')
    } catch (error) {
      console.error('Failed to start coverage mission:', error)
      alert(`Failed to start mission: ${error.message}`)
      return
    }
    setIsScanning(true)
    setIsPaused(false)
    setScanProgress(0)
    setRobotStatus(prev => ({ ...prev, operatingState: 'Scanning' }))
  }

  const handlePauseScan = () => {
    if (scanIntervalRef.current) {
      clearInterval(scanIntervalRef.current)
    }
    setIsPaused(true)
    setScanPhase('Paused')
    setRobotStatus(prev => ({ ...prev, operatingState: 'Paused' }))
  }

  const handleResumeScan = () => {
    setIsPaused(false)
    setRobotStatus(prev => ({ ...prev, operatingState: 'Scanning' }))
  }

  const handleStopScan = async () => {
    try {
      await apiClient.stopCoverageMission()
      console.log('Coverage mission stopped on robot')
    } catch (error) {
      console.error('Failed to stop coverage mission:', error.message)
    }
    if (scanIntervalRef.current) {
      clearInterval(scanIntervalRef.current)
    }
    setIsScanning(false)
    setIsPaused(false)
    setScanProgress(0)
    setScanPhase('')
    setRobotStatus(prev => ({ ...prev, operatingState: 'Idle' }))
  }

  // Handle boundary update when location is refreshed
  const handleUpdateBoundary = (newLat, newLng) => {
    // Update scan target to new location
    setScanTarget({ lat: newLat, lng: newLng })
  }

  const handleScanTargetChange = (newTarget) => {
    setScanTarget(newTarget)
  }

  const handleBackFromResults = () => {
    setShowResults(false)
    setScanProgress(0)
    setScanPhase('')
  }

  // Handle clicking on a history marker to view its scan results
  const handleMarkerClick = async (marker) => {
    try {
      // Try to load detailed scan data from API
      const scanDetail = await apiClient.getScanDetail(marker.id).catch(() => null)

      if (scanDetail) {
        // Transform API response to scan data format
        const detailedScanData = {
          id: scanDetail.id,  // Add scan ID for heatmap
          zoneId: scanDetail.zone_id || 'Unknown',
          location: `Area ${scanDetail.zone_id}`,
          areaSize: scanDetail.scan_area || '50 m × 50 m',
          duration: scanDetail.duration || 'N/A',
          completedAt: scanDetail.completed_at ? new Date(scanDetail.completed_at).toLocaleString() : 'N/A',
          riskLevel: scanDetail.risk_level ? scanDetail.risk_level.charAt(0).toUpperCase() + scanDetail.risk_level.slice(1) : 'Medium',
          avgPlantTemp: scanDetail.avg_plant_temp || 0,
          avgAirTemp: scanDetail.avg_air_temp || 0,
          tempDiff: scanDetail.temp_diff || 0,
          fuel_load: scanDetail.fuel_load,  // Use new field name
          one_hour_fuel: scanDetail.one_hour_fuel,
          ten_hour_fuel: scanDetail.ten_hour_fuel,
          hundred_hour_fuel: scanDetail.hundred_hour_fuel,
          pine_cone_count: scanDetail.pine_cone_count,
          fuelLoad: scanDetail.fuel_load || 'Unknown',  // Keep legacy for display
          fuelDensity: scanDetail.fuel_density || 0,
          biomass: scanDetail.biomass || 0,
          recommendations: [
            'View detailed analysis',
            'Check environmental data',
            'Review scan images'
          ],
          latitude: scanDetail.latitude ? scanDetail.latitude.toFixed(6) : '0',
          longitude: scanDetail.longitude ? scanDetail.longitude.toFixed(6) : '0',
          images: scanDetail.images || []
        }
        setScanResultData(detailedScanData)
      } else if (marker.scanData) {
        // Fallback to cached data
        setScanResultData(marker.scanData)
      }

      setShowResults(true)
    } catch (error) {
      console.error('Failed to load scan details:', error)
      // Fallback to cached data if available
      if (marker.scanData) {
        setScanResultData(marker.scanData)
        setShowResults(true)
      }
    }
  }

  // Show scan results page
  if (showResults && scanResultData) {
    return <ScanResults scanData={scanResultData} onBack={handleBackFromResults} />
  }

  return (
    <div className="dashboard">
      <Sidebar
        locationData={locationData}
        setLocationData={setLocationData}
        scanConfig={scanConfig}
        scanTarget={scanTarget}
        robotStatus={robotStatus}
        environmentalData={environmentalData}
        scanHistory={scanHistory}
        isScanning={isScanning}
        isPaused={isPaused}
        scanProgress={scanProgress}
        scanPhase={scanPhase}
        onStartScan={handleStartScan}
        onPauseScan={handlePauseScan}
        onResumeScan={handleResumeScan}
        onStopScan={handleStopScan}
        onUpdateBoundary={handleUpdateBoundary}
      />
      <main className="main-content">
        <MapView
          center={[locationData.latitude, locationData.longitude]}
          markers={mapMarkers}
          robotPosition={{ lat: locationData.latitude, lng: locationData.longitude }}
          onScanTargetChange={handleScanTargetChange}
          onMarkerClick={handleMarkerClick}
        />
        <DataLog logs={scanLogs} />
      </main>
    </div>
  )
}

export default App

