import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';

/**
 * Simple Heatmap using ImageOverlay
 * More reliable than GridLayer for React
 */

// Color gradient function
const getColorForValue = (value, min, max) => {
  const normalized = (value - min) / (max - min);
  const clamped = Math.max(0, Math.min(1, normalized));
  
  const colors = [
    { pos: 0.0, r: 0, g: 0, b: 255 },
    { pos: 0.25, r: 0, g: 255, b: 255 },
    { pos: 0.5, r: 0, g: 255, b: 0 },
    { pos: 0.65, r: 255, g: 255, b: 0 },
    { pos: 0.8, r: 255, g: 128, b: 0 },
    { pos: 1.0, r: 255, g: 0, b: 0 }
  ];
  
  let i = 0;
  while (i < colors.length - 1 && colors[i + 1].pos < clamped) {
    i++;
  }
  
  const c1 = colors[i];
  const c2 = colors[Math.min(i + 1, colors.length - 1)];
  
  const range = c2.pos - c1.pos;
  const rangePct = range === 0 ? 0 : (clamped - c1.pos) / range;
  
  const r = Math.round(c1.r + (c2.r - c1.r) * rangePct);
  const g = Math.round(c1.g + (c2.g - c1.g) * rangePct);
  const b = Math.round(c1.b + (c2.b - c1.b) * rangePct);
  
  return { r, g, b };
};

// Bilinear interpolation
const bilinearInterpolate = (x, y, gridData) => {
  if (!gridData || gridData.length === 0) return null;
  
  const col = x;
  const row = y;
  
  const col0 = Math.floor(col);
  const row0 = Math.floor(row);
  const col1 = Math.min(col0 + 1, gridData[0].length - 1);
  const row1 = Math.min(row0 + 1, gridData.length - 1);
  
  const dx = col - col0;
  const dy = row - row0;
  
  const getVal = (r, c) => {
    if (r < 0 || r >= gridData.length || c < 0 || c >= gridData[0].length) return null;
    const v = gridData[r][c];
    return (v !== null && v !== undefined && !isNaN(v)) ? v : null;
  };
  
  const v00 = getVal(row0, col0);
  const v10 = getVal(row0, col1);
  const v01 = getVal(row1, col0);
  const v11 = getVal(row1, col1);
  
  const validValues = [v00, v10, v01, v11].filter(v => v !== null);
  if (validValues.length === 0) return null;
  
  if (validValues.length === 4) {
    const top = v00 * (1 - dx) + v10 * dx;
    const bottom = v01 * (1 - dx) + v11 * dx;
    return top * (1 - dy) + bottom * dy;
  }
  
  let sum = 0, weightSum = 0;
  if (v00 !== null) { const w = (1-dx)*(1-dy); sum += v00*w; weightSum += w; }
  if (v10 !== null) { const w = dx*(1-dy); sum += v10*w; weightSum += w; }
  if (v01 !== null) { const w = (1-dx)*dy; sum += v01*w; weightSum += w; }
  if (v11 !== null) { const w = dx*dy; sum += v11*w; weightSum += w; }
  
  return weightSum > 0 ? sum / weightSum : null;
};

const SimpleHeatmap = ({ data, valueExtractor, opacity = 0.75 }) => {
  const map = useMap();
  const overlayRef = useRef(null);
  
  useEffect(() => {
    if (!map || !data || data.length === 0) {
      console.log('[SimpleHeatmap] No map or data');
      return;
    }
    
    console.log('[SimpleHeatmap] Creating heatmap with', data.length, 'points');
    
    // Build grid
    const lats = data.map(p => p.latitude);
    const lngs = data.map(p => p.longitude);
    const values = data.map(valueExtractor).filter(v => v !== null && v !== undefined);
    
    if (values.length === 0) {
      console.log('[SimpleHeatmap] No valid values');
      return;
    }
    
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    
    console.log('[SimpleHeatmap] Bounds:', { 
      lat: [minLat, maxLat], 
      lng: [minLng, maxLng],
      value: [minValue, maxValue]
    });
    
    // Build 20x20 grid
    const gridSize = 20;
    const latStep = (maxLat - minLat) / (gridSize - 1);
    const lngStep = (maxLng - minLng) / (gridSize - 1);
    
    const gridData = Array(gridSize).fill(null).map(() => Array(gridSize).fill(null));
    
    data.forEach(point => {
      const value = valueExtractor(point);
      if (value === null || value === undefined) return;
      
      const row = Math.round((point.latitude - minLat) / latStep);
      const col = Math.round((point.longitude - minLng) / lngStep);
      
      if (row >= 0 && row < gridSize && col >= 0 && col < gridSize) {
        gridData[row][col] = value;
      }
    });
    
    console.log('[SimpleHeatmap] Grid built, sample:', gridData[0].slice(0, 3));
    
    // Create canvas and draw heatmap
    const canvasSize = 512;  // High resolution
    const canvas = document.createElement('canvas');
    canvas.width = canvasSize;
    canvas.height = canvasSize;
    const ctx = canvas.getContext('2d');
    
    const imageData = ctx.createImageData(canvasSize, canvasSize);
    const pixelData = imageData.data;
    
    let pixelsDrawn = 0;
    
    for (let py = 0; py < canvasSize; py++) {
      for (let px = 0; px < canvasSize; px++) {
        // Pixel to grid coordinates
        const gridX = (px / canvasSize) * (gridSize - 1);
        const gridY = (py / canvasSize) * (gridSize - 1);
        
        const value = bilinearInterpolate(gridX, gridY, gridData);
        
        if (value !== null && !isNaN(value)) {
          const color = getColorForValue(value, minValue, maxValue);
          const idx = (py * canvasSize + px) * 4;
          pixelData[idx] = color.r;
          pixelData[idx + 1] = color.g;
          pixelData[idx + 2] = color.b;
          pixelData[idx + 3] = Math.round(opacity * 255);
          pixelsDrawn++;
        }
      }
    }
    
    console.log('[SimpleHeatmap] Drew', pixelsDrawn, 'pixels');
    
    ctx.putImageData(imageData, 0, 0);
    
    // Convert to data URL
    const imageUrl = canvas.toDataURL('image/png');
    console.log('[SimpleHeatmap] Image created, size:', imageUrl.length, 'bytes');
    
    // Create image overlay
    const bounds = L.latLngBounds(
      L.latLng(minLat, minLng),
      L.latLng(maxLat, maxLng)
    );
    
    const overlay = L.imageOverlay(imageUrl, bounds, {
      opacity: 1.0,
      interactive: false,
      pane: 'overlayPane'
    }).addTo(map);
    
    overlayRef.current = overlay;
    console.log('[SimpleHeatmap] ✓ Overlay added to map');
    
    return () => {
      if (overlayRef.current && map.hasLayer(overlayRef.current)) {
        map.removeLayer(overlayRef.current);
        console.log('[SimpleHeatmap] Overlay removed');
      }
    };
  }, [map, data, valueExtractor, opacity]);
  
  return null;
};

export default SimpleHeatmap;
