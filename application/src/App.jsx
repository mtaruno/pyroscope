import { useState, useEffect, useRef } from 'react'
import Sidebar from './components/Sidebar'
import MapView from './components/MapView'
import DataLog from './components/DataLog'
import ScanResults from './components/ScanResults'
import SensorPanel from './components/SensorPanel'
import ScanConfigModal from './components/ScanConfigModal'
import apiClient from './services/api'
import './App.css'

function App() {
  const [locationData, setLocationData] = useState({
    zoneName: 'Area A-01',
    latitude: 47.1607476,
    longitude: -120.7953433,
    gpsAccuracy: 2.3
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
  const [activeScanId, setActiveScanId] = useState(null)
  const [latestCapture, setLatestCapture] = useState(null)
  const latestCapturePollRef = useRef(null)
  const [showScanConfigModal, setShowScanConfigModal] = useState(false)
  const [capturedPoints, setCapturedPoints] = useState(0)
  const [totalPoints, setTotalPoints] = useState(0)
  const finishHandledRef = useRef(false)

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
          battery: status.battery_level ?? 100,
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

  // Poll mission progress to update real progress based on capture-ready count / total points.
  useEffect(() => {
    if (!isScanning || !activeScanId) return
    const poll = async () => {
      try {
        const progress = await apiClient.getMissionProgress()
        const nextCaptured = progress?.captured_points || 0
        const nextTotal = progress?.total_points || totalPoints || 0
        const nextPercent = progress?.progress_percent || 0

        setCapturedPoints(nextCaptured)
        setTotalPoints(nextTotal)
        setScanProgress(nextPercent)
        setScanPhase(
          nextTotal > 0
            ? `Captured ${nextCaptured}/${nextTotal} points`
            : `Captured ${nextCaptured} point(s)`
        )

        if (progress?.status === 'completed' && !finishHandledRef.current) {
          finishHandledRef.current = true
          try {
            await apiClient.stopCoverageMission()
          } catch (stopError) {
            console.error('Failed to stop completed mission cleanly:', stopError)
          }
          setIsScanning(false)
          setRobotStatus(prev => ({ ...prev, operatingState: 'Idle' }))
          setScanPhase('Scan complete')
          // Go straight to scan results
          await loadAndShowScanResult(activeScanId)
          setActiveScanId(null)
          setLatestCapture(null)
        }
      } catch (error) {
        console.error('Mission progress poll failed:', error)
      }
    }
    poll()
    const progressInterval = setInterval(poll, 1000)
    return () => clearInterval(progressInterval)
  }, [isScanning, activeScanId, totalPoints])

  // Poll latest waypoint capture while scanning
  useEffect(() => {
    if (!isScanning || !activeScanId) {
      if (latestCapturePollRef.current) {
        clearInterval(latestCapturePollRef.current)
        latestCapturePollRef.current = null
      }
      return
    }
    const poll = async () => {
      try {
        const data = await apiClient.getLatestCapture(activeScanId)
        setLatestCapture(data)
      } catch (e) {
        console.error('Latest capture poll failed:', e)
      }
    }
    poll()
    latestCapturePollRef.current = setInterval(poll, 2000)
    return () => {
      if (latestCapturePollRef.current) clearInterval(latestCapturePollRef.current)
    }
  }, [isScanning, activeScanId])

  const buildScanDataFromDetail = (scanDetail) => ({
    id: scanDetail.id,
    zoneId: scanDetail.zone_id || 'Unknown',
    location: `Area ${scanDetail.zone_id}`,
    areaSize: scanDetail.scan_area || '50 m × 50 m',
    duration: scanDetail.duration || 'N/A',
    completedAt: scanDetail.completed_at ? new Date(scanDetail.completed_at).toLocaleString() : 'N/A',
    riskLevel: (scanDetail.risk_level || 'medium').charAt(0).toUpperCase() + (scanDetail.risk_level || '').slice(1),
    avgPlantTemp: scanDetail.avg_plant_temp || 0,
    avgAirTemp: scanDetail.avg_air_temp || 0,
    tempDiff: scanDetail.temp_diff || 0,
    fuel_load: scanDetail.fuel_load,
    one_hour_fuel: scanDetail.one_hour_fuel,
    ten_hour_fuel: scanDetail.ten_hour_fuel,
    hundred_hour_fuel: scanDetail.hundred_hour_fuel,
    pine_cone_count: scanDetail.pine_cone_count,
    fuelLoad: scanDetail.fuel_load || 'Unknown',
    fuelDensity: scanDetail.fuel_density || 0,
    biomass: scanDetail.biomass || 0,
    recommendations: ['View detailed analysis', 'Check environmental data', 'Review scan images'],
    latitude: scanDetail.latitude != null ? String(scanDetail.latitude) : '0',
    longitude: scanDetail.longitude != null ? String(scanDetail.longitude) : '0',
    images: scanDetail.images || []
  })

  const loadAndShowScanResult = async (scanId) => {
    if (!scanId) return
    try {
      const scanDetail = await apiClient.getScanDetail(scanId).catch(() => null)
      if (scanDetail) {
        setScanResultData(buildScanDataFromDetail(scanDetail))
        setShowResults(true)
      }
    } catch (error) {
      console.error('Failed to load scan result:', error)
    }
  }

  const handleStartScan = () => {
    setShowScanConfigModal(true)
  }

  const handleConfirmStartScan = async ({
    areaSize, precision, totalPoints: configuredTotal,
    originX = 0, originY = 0, rowSpacing = 0.5, dwellTime = 2.0, waypointTimeout = 30.0
  }) => {
    setShowScanConfigModal(false)
    try {
      const missionConfig = {
        area_size_m: areaSize,
        sampling_precision_m: precision,
        area_width: areaSize,
        area_height: areaSize,
        row_spacing: rowSpacing,
        waypoint_spacing: precision,
        origin_x: originX,
        origin_y: originY,
        dwell_time: dwellTime,
        waypoint_timeout: waypointTimeout
      }
      const response = await apiClient.startCoverageMission(missionConfig)
      const scanId = response?.scan_id ?? null
      if (!scanId) {
        throw new Error('Mission started but scan_id is missing')
      }
      finishHandledRef.current = false
      setActiveScanId(scanId)
      setLatestCapture(null)
      setIsScanning(true)
      setIsPaused(false)
      setCapturedPoints(response?.captured_points || 0)
      setTotalPoints(response?.total_points || configuredTotal || 0)
      setScanProgress(response?.progress_percent || 0)
      setScanPhase('Waiting for /coverage/capture_ready = true ...')
      setRobotStatus(prev => ({ ...prev, operatingState: 'Scanning' }))
    } catch (error) {
      console.error('Failed to start coverage mission:', error)
      alert(`Failed to start mission: ${error.message}`)
    }
  }

  const handlePauseScan = () => {
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
    setIsScanning(false)
    setIsPaused(false)
    setScanProgress(0)
    setScanPhase('')
    setCapturedPoints(0)
    setTotalPoints(0)
    setShowScanConfigModal(false)
    setRobotStatus(prev => ({ ...prev, operatingState: 'Idle' }))
    if (activeScanId) {
      await loadAndShowScanResult(activeScanId)
      setActiveScanId(null)
      setLatestCapture(null)
    }
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
    setActiveScanId(null)
    setLatestCapture(null)
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
        scanTarget={scanTarget}
        robotStatus={robotStatus}
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
        <SensorPanel expanded={isScanning} />
        {isScanning && (
          <section className="latest-capture-panel" aria-label="Latest capture">
            <h3 className="latest-capture-title">Latest capture</h3>
            <div className="latest-capture-content">
              {latestCapture?.rgb_image_url && (
                <div className="latest-capture-image-wrap">
                  <p className="latest-capture-img-label">RGB (RealSense)</p>
                  <img
                    src={apiClient.getBaseUrl() + latestCapture.rgb_image_url}
                    alt="Latest RGB"
                    className="latest-capture-image"
                  />
                </div>
              )}
              {latestCapture?.thermal_image_url && (
                <div className="latest-capture-image-wrap">
                  <p className="latest-capture-img-label">Thermal</p>
                  <img
                    src={apiClient.getBaseUrl() + latestCapture.thermal_image_url}
                    alt="Latest thermal"
                    className="latest-capture-image"
                  />
                </div>
              )}
              <div className="latest-capture-fields">
                {latestCapture?.captured_at != null && (
                  <p className="latest-capture-time">
                    {new Date(latestCapture.captured_at).toLocaleString()}
                  </p>
                )}
                {latestCapture?.air_temperature != null && (
                  <p>Air temp: <strong>{latestCapture.air_temperature} °C</strong></p>
                )}
                {latestCapture?.air_humidity != null && (
                  <p>Humidity: <strong>{latestCapture.air_humidity} %</strong></p>
                )}
                {latestCapture?.thermal_mean != null && (
                  <p>Thermal mean: <strong>{latestCapture.thermal_mean} °C</strong></p>
                )}
                {!latestCapture?.captured_at && activeScanId && (
                  <p className="latest-capture-wait">Waiting for first capture…</p>
                )}
              </div>
            </div>
          </section>
        )}
        <DataLog logs={scanLogs} />
      </main>
      <ScanConfigModal
        open={showScanConfigModal}
        onCancel={() => setShowScanConfigModal(false)}
        onConfirm={handleConfirmStartScan}
      />
    </div>
  )
}

export default App
