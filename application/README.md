# Pyroscope Dashboard

A React-based wildfire monitoring dashboard for autonomous ground robots. This frontend application provides real-time visualization of scan data, GPS tracking, and risk assessment for wildfire prevention.

![Dashboard Preview](https://img.shields.io/badge/Status-In%20Development-yellow)
![React](https://img.shields.io/badge/React-18.x-61DAFB?logo=react)
![Vite](https://img.shields.io/badge/Vite-6.x-646CFF?logo=vite)

## Features

### 🗺️ Interactive Satellite Map
- Real-time GPS location tracking with draggable scan target marker
- Historical scan points with color-coded risk levels (Low/Medium/High)
- 200m × 200m boundary frame and 50m × 50m scan area visualization
- Hover-to-preview and click-to-view-details for past scans
- Layer visibility controls and map legend

### 📊 Sidebar Information Panel
- **Location Data**: Current GPS coordinates and designated scan target
- **Scan Configuration**: Area size and estimated duration
- **Robot Status**: Battery level, storage, signal strength, operating state
- **Environmental Data**: Temperature, humidity, wind speed (from sensors)
- **Scan History**: Quick access to recent scans

### 🔍 Scan Operations
- Start/Pause/Resume/Stop scan controls
- Real-time progress bar with phase indicators
- Animated robot icon tracking scan progress
- Automatic transition to results page on completion

### 📈 Scan Results Page
- Thermal map visualization (placeholder for sensor data)
- Temperature analysis and comparison
- Fuel load estimation and biomass data
- Risk assessment with actionable recommendations
- GPS coordinates of scanned area

### 📋 Data Log
- Collapsible scan history table
- Resizable panel with drag handle
- Displays key metrics: temperature, humidity, fuel load

## Tech Stack

- **Framework**: React 18 with Vite
- **Mapping**: Leaflet + React-Leaflet
- **Icons**: Lucide React
- **Styling**: CSS with custom properties
- **Tile Provider**: Esri World Imagery (satellite view)

## Getting Started

### Prerequisites
- Node.js 18+ 
- npm or yarn

### Installation

```bash
# Clone the repository
git clone https://github.com/xanx66/pyroscope_dashboard.git

# Navigate to project directory
cd pyroscope_dashboard

# Install dependencies
npm install

# Start development server
npm run dev
```

The app will be available at `http://localhost:5173`

### Build for Production

```bash
npm run build
```

## Project Structure

```
pyroscope/
├── public/
│   └── favicon.svg
├── src/
│   ├── components/
│   │   ├── DataLog.jsx        # Scan history table
│   │   ├── DataLog.css
│   │   ├── MapView.jsx        # Interactive satellite map
│   │   ├── MapView.css
│   │   ├── ScanResults.jsx    # Post-scan results page
│   │   ├── ScanResults.css
│   │   ├── Sidebar.jsx        # Left panel with controls
│   │   └── Sidebar.css
│   ├── App.jsx                # Main application component
│   ├── App.css
│   ├── main.jsx               # Entry point
│   └── index.css              # Global styles
├── index.html
├── package.json
└── vite.config.js
```

## Usage

1. **View Current Location**: The red crosshair marker shows the robot's current GPS position
2. **Set Scan Target**: Drag the marker within the green boundary frame to select scan area
3. **Start Scan**: Click "Start Scan" button in the sidebar
4. **Monitor Progress**: Watch the progress bar and phase indicators
5. **View Results**: After scan completion, review the thermal map and analysis
6. **Browse History**: Hover over map markers to preview, click for full details

## Future Enhancements

- [ ] Backend API integration for real sensor data
- [ ] Real-time WebSocket updates
- [ ] Thermal map rendering from actual sensor output
- [ ] Multi-robot fleet management
- [ ] Historical data analytics and trends
- [ ] Export reports to PDF

## License

This project is part of a wildfire monitoring research initiative.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

