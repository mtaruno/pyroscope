import React, { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';

/**
 * Interpolated Heatmap using custom Canvas GridLayer
 * Uses bilinear interpolation for smooth gradients from grid data
 */

// Color gradient function (blue -> cyan -> green -> yellow -> orange -> red)
const getColorForValue = (value, min, max) => {
    // Normalize value to 0-1
    const normalized = (value - min) / (max - min);
    const clamped = Math.max(0, Math.min(1, normalized));

    // Define color stops
    const colors = [
        { pos: 0.0, r: 0, g: 0, b: 255 },     // Blue
        { pos: 0.25, r: 0, g: 255, b: 255 },  // Cyan
        { pos: 0.5, r: 0, g: 255, b: 0 },     // Green
        { pos: 0.65, r: 255, g: 255, b: 0 },  // Yellow
        { pos: 0.8, r: 255, g: 128, b: 0 },   // Orange
        { pos: 1.0, r: 255, g: 0, b: 0 }      // Red
    ];

    // Find the two color stops to interpolate between
    let i = 0;
    while (i < colors.length - 1 && colors[i + 1].pos < clamped) {
        i++;
    }

    const c1 = colors[i];
    const c2 = colors[Math.min(i + 1, colors.length - 1)];

    // Interpolate between the two colors
    const range = c2.pos - c1.pos;
    const rangePct = range === 0 ? 0 : (clamped - c1.pos) / range;

    const r = Math.round(c1.r + (c2.r - c1.r) * rangePct);
    const g = Math.round(c1.g + (c2.g - c1.g) * rangePct);
    const b = Math.round(c1.b + (c2.b - c1.b) * rangePct);

    return { r, g, b };
};

// Bilinear interpolation for smooth gradients
// x corresponds to column (longitude), y corresponds to row (latitude)
const bilinearInterpolate = (x, y, gridData, cellSize) => {
    if (!gridData || gridData.length === 0 || !gridData[0]) {
        return null;
    }

    // Find grid cell indices
    // x is column index (longitude direction)
    // y is row index (latitude direction)
    const col = x / cellSize;
    const row = y / cellSize;

    const col0 = Math.floor(col);
    const row0 = Math.floor(row);
    const col1 = col0 + 1;
    const row1 = row0 + 1;

    // Fractional parts for interpolation
    const dx = col - col0;
    const dy = row - row0;

    // Get values at the 4 corners (with boundary checks)
    // gridData[row][col] where row is latitude, col is longitude
    const getGridValue = (r, c) => {
        if (r < 0 || r >= gridData.length || c < 0 || c >= gridData[0].length) {
            return null;
        }
        const val = gridData[r][c];
        return (val !== null && val !== undefined && !isNaN(val)) ? val : null;
    };

    const v00 = getGridValue(row0, col0);
    const v10 = getGridValue(row0, col1);
    const v01 = getGridValue(row1, col0);
    const v11 = getGridValue(row1, col1);

    // Count valid values
    const validValues = [v00, v10, v01, v11].filter(v => v !== null);
    if (validValues.length === 0) return null;

    // If we have all 4 corners, do proper bilinear interpolation
    if (validValues.length === 4) {
        const top = v00 * (1 - dx) + v10 * dx;
        const bottom = v01 * (1 - dx) + v11 * dx;
        return top * (1 - dy) + bottom * dy;
    }

    // Otherwise, use weighted average of available values
    let sum = 0;
    let weightSum = 0;

    if (v00 !== null) {
        const weight = (1 - dx) * (1 - dy);
        sum += v00 * weight;
        weightSum += weight;
    }
    if (v10 !== null) {
        const weight = dx * (1 - dy);
        sum += v10 * weight;
        weightSum += weight;
    }
    if (v01 !== null) {
        const weight = (1 - dx) * dy;
        sum += v01 * weight;
        weightSum += weight;
    }
    if (v11 !== null) {
        const weight = dx * dy;
        sum += v11 * weight;
        weightSum += weight;
    }

    return weightSum > 0 ? sum / weightSum : null;
};

// Custom GridLayer class
const InterpolatedHeatmapLayer = L.GridLayer.extend({
    options: {
        tileSize: 256,
        opacity: 1.0,
        updateWhenIdle: false,
        updateWhenZooming: false,
        keepBuffer: 2,
        pane: 'overlayPane'
    },

    initialize: function (data, valueExtractor, options) {
        console.log('[InterpolatedHeatmapLayer] Initializing...');
        L.GridLayer.prototype.initialize.call(this, options);
        this.data = data;
        this.valueExtractor = valueExtractor;
        this._buildGrid();
    },

    onAdd: function (map) {
        console.log('[InterpolatedHeatmapLayer] onAdd called');
        L.GridLayer.prototype.onAdd.call(this, map);
        console.log('[InterpolatedHeatmapLayer] Container created:', !!this._container);
        if (this._container) {
            this._container.style.zIndex = '650';
            this._container.style.opacity = '1';
            console.log('[InterpolatedHeatmapLayer] ✓ Styled container in onAdd');
        }
    },

    _buildGrid: function () {
        if (!this.data || this.data.length === 0) {
            console.log('[InterpolatedHeatmap] No data provided');
            this.gridData = [];
            this.bounds = null;
            return;
        }

        console.log('[InterpolatedHeatmap] Building grid from', this.data.length, 'points');

        // Find bounds and build a regular grid
        const lats = this.data.map(p => p.latitude);
        const lngs = this.data.map(p => p.longitude);
        const values = this.data.map(this.valueExtractor).filter(v => v !== null && v !== undefined);

        if (values.length === 0) {
            console.log('[InterpolatedHeatmap] No valid values extracted');
            this.gridData = [];
            this.bounds = null;
            return;
        }

        this.minLat = Math.min(...lats);
        this.maxLat = Math.max(...lats);
        this.minLng = Math.min(...lngs);
        this.maxLng = Math.max(...lngs);
        this.minValue = Math.min(...values);
        this.maxValue = Math.max(...values);

        console.log('[InterpolatedHeatmap] Bounds:', {
            lat: [this.minLat, this.maxLat],
            lng: [this.minLng, this.maxLng],
            value: [this.minValue, this.maxValue]
        });

        // Assume 20x20 grid from the data
        // Build a 2D array indexed by [row][col]
        const gridSize = 20;
        const latStep = (this.maxLat - this.minLat) / (gridSize - 1);
        const lngStep = (this.maxLng - this.minLng) / (gridSize - 1);

        // Initialize grid
        this.gridData = Array(gridSize).fill(null).map(() => Array(gridSize).fill(null));

        // Fill grid with data points
        let pointsMapped = 0;
        this.data.forEach(point => {
            const value = this.valueExtractor(point);
            if (value === null || value === undefined) return;

            // Find closest grid position
            const row = Math.round((point.latitude - this.minLat) / latStep);
            const col = Math.round((point.longitude - this.minLng) / lngStep);

            if (row >= 0 && row < gridSize && col >= 0 && col < gridSize) {
                this.gridData[row][col] = value;
                pointsMapped++;
            }
        });

        console.log('[InterpolatedHeatmap] Mapped', pointsMapped, 'points to', gridSize, 'x', gridSize, 'grid');

        // Log first few grid values for debugging
        console.log('[InterpolatedHeatmap] Sample grid values:', this.gridData[0].slice(0, 5));

        this.bounds = L.latLngBounds(
            L.latLng(this.minLat, this.minLng),
            L.latLng(this.maxLat, this.maxLng)
        );
    },

    createTile: function (coords, done) {
        const tile = document.createElement('canvas');
        const tileSize = this.getTileSize();
        tile.width = tileSize.x;
        tile.height = tileSize.y;

        const ctx = tile.getContext('2d');

        if (!this.gridData || this.gridData.length === 0) {
            console.log('[InterpolatedHeatmap] No grid data, skipping tile', coords);
            done(null, tile);
            return tile;
        }

        // Get tile bounds in lat/lng
        const tileBounds = this._tileCoordsToBounds(coords);
        const nwPoint = tileBounds.getNorthWest();
        const sePoint = tileBounds.getSouthEast();

        // Check if tile intersects with data bounds
        if (!this.bounds || !this.bounds.intersects(tileBounds)) {
            done(null, tile);
            return tile;
        }

        console.log('[InterpolatedHeatmap] Creating tile', coords, 'bounds:', {
            nw: [nwPoint.lat, nwPoint.lng],
            se: [sePoint.lat, sePoint.lng]
        });

        // Calculate pixel-to-latlng conversion
        const latRange = nwPoint.lat - sePoint.lat;
        const lngRange = sePoint.lng - nwPoint.lng;

        // Create ImageData for direct pixel manipulation
        const imageData = ctx.createImageData(tileSize.x, tileSize.y);
        const data = imageData.data;

        // Grid cell size in lat/lng degrees
        const gridSize = this.gridData.length;
        const gridLatSize = (this.maxLat - this.minLat) / (gridSize - 1);
        const gridLngSize = (this.maxLng - this.minLng) / (gridSize - 1);

        let pixelsDrawn = 0;

        // For each pixel in the tile
        for (let py = 0; py < tileSize.y; py++) {
            for (let px = 0; px < tileSize.x; px++) {
                // Convert pixel to lat/lng
                const lat = nwPoint.lat - (py / tileSize.y) * latRange;
                const lng = nwPoint.lng + (px / tileSize.x) * lngRange;

                // Check if within data bounds
                if (lat < this.minLat || lat > this.maxLat || lng < this.minLng || lng > this.maxLng) {
                    continue;
                }

                // Convert to grid coordinates (0-based indices)
                const gridX = (lng - this.minLng) / gridLngSize;
                const gridY = (lat - this.minLat) / gridLatSize;

                // Bilinear interpolation
                const value = bilinearInterpolate(gridX, gridY, this.gridData, 1.0);

                if (value !== null && !isNaN(value)) {
                    const color = getColorForValue(value, this.minValue, this.maxValue);
                    const idx = (py * tileSize.x + px) * 4;
                    data[idx] = color.r;
                    data[idx + 1] = color.g;
                    data[idx + 2] = color.b;
                    data[idx + 3] = 200; // Alpha (~0.78 opacity) - more visible
                    pixelsDrawn++;
                }
            }
        }

        console.log('[InterpolatedHeatmap] Drew', pixelsDrawn, 'pixels in tile');

        ctx.putImageData(imageData, 0, 0);

        // DEBUG: Draw a bright border around the tile to verify it's visible
        ctx.strokeStyle = 'rgba(255, 0, 255, 0.8)';  // Bright magenta
        ctx.lineWidth = 3;
        ctx.strokeRect(0, 0, tileSize.x, tileSize.y);

        // CRITICAL: Force tile styling
        tile.style.position = 'absolute';
        tile.style.opacity = '1';
        tile.style.zIndex = '650';

        done(null, tile);
        return tile;
    }
});

// React component wrapper
const InterpolatedHeatmap = ({ data, valueExtractor, opacity = 0.75 }) => {
    const map = useMap();
    const layerRef = useRef(null);

    useEffect(() => {
        if (!map || !data || data.length === 0) {
            console.log('[InterpolatedHeatmap] Component: No map or data');
            return;
        }

        console.log('[InterpolatedHeatmap] Component: Creating layer with', data.length, 'points');

        // Create the heatmap layer
        const heatmapLayer = new InterpolatedHeatmapLayer(data, valueExtractor, {
            opacity: 1.0,
            pane: 'overlayPane'
        });

        console.log('[InterpolatedHeatmap] Component: Adding layer to map');

        // IMPORTANT: Wait for map to be ready
        map.whenReady(() => {
            console.log('[InterpolatedHeatmap] Map is ready, adding layer');
            heatmapLayer.addTo(map);
            layerRef.current = heatmapLayer;

            // Force redraw
            map.invalidateSize();

            // CRITICAL: Wait for layer to be fully added, then force visibility
            let retryCount = 0;
            const forceVisibility = () => {
                if (heatmapLayer._container) {
                    const container = heatmapLayer._container;
                    container.style.zIndex = '650';
                    container.style.pointerEvents = 'none';
                    container.style.opacity = '1';

                    console.log('[InterpolatedHeatmap] ✓ Container found and styled!');
                    console.log('[InterpolatedHeatmap] Canvas tiles:', container.querySelectorAll('canvas').length);
                } else {
                    retryCount++;
                    if (retryCount < 20) {
                        console.log('[InterpolatedHeatmap] No container yet, retry', retryCount);
                        setTimeout(forceVisibility, 100);
                    } else {
                        console.error('[InterpolatedHeatmap] ✗ Failed to find container after 20 retries');
                    }
                }
            };

            setTimeout(forceVisibility, 200);
        });

        return () => {
            if (layerRef.current && map.hasLayer(layerRef.current)) {
                console.log('[InterpolatedHeatmap] Component: Removing layer');
                map.removeLayer(layerRef.current);
            }
        };
    }, [map, data, valueExtractor, opacity]);

    return null;
};

export default InterpolatedHeatmap;
