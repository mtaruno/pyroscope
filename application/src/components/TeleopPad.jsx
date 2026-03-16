import { useEffect, useCallback, useRef, useState } from 'react'
import apiClient from '../services/api'
import './TeleopPad.css'

const LINEAR_SPEED = 0.2
const ANGULAR_SPEED = 1.0
const SEND_INTERVAL_MS = 200

export default function TeleopPad() {
  const [activeKeys, setActiveKeys] = useState(new Set())
  const keysRef = useRef(new Set())
  const intervalRef = useRef(null)

  const computeVelocity = useCallback(() => {
    const keys = keysRef.current
    let lx = 0
    let az = 0
    if (keys.has('forward')) lx += LINEAR_SPEED
    if (keys.has('backward')) lx -= LINEAR_SPEED
    if (keys.has('left')) az += ANGULAR_SPEED
    if (keys.has('right')) az -= ANGULAR_SPEED
    return { lx, az }
  }, [])

  const sendCommand = useCallback(() => {
    const { lx, az } = computeVelocity()
    apiClient.sendTeleop(lx, az).catch(() => {})
  }, [computeVelocity])

  const keyToAction = (e) => {
    switch (e.key) {
      case 'w': case 'ArrowUp': case 'i': return 'forward'
      case 's': case 'ArrowDown': case ',': return 'backward'
      case 'a': case 'ArrowLeft': case 'j': return 'left'
      case 'd': case 'ArrowRight': case 'l': return 'right'
      default: return null
    }
  }

  useEffect(() => {
    const onKeyDown = (e) => {
      const action = keyToAction(e)
      if (!action) return
      e.preventDefault()
      if (keysRef.current.has(action)) return
      keysRef.current.add(action)
      setActiveKeys(new Set(keysRef.current))
      if (!intervalRef.current) {
        sendCommand()
        intervalRef.current = setInterval(sendCommand, SEND_INTERVAL_MS)
      }
    }
    const onKeyUp = (e) => {
      const action = keyToAction(e)
      if (!action) return
      e.preventDefault()
      keysRef.current.delete(action)
      setActiveKeys(new Set(keysRef.current))
      if (keysRef.current.size === 0) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
        apiClient.sendTeleop(0, 0).catch(() => {})
      }
    }
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [sendCommand])

  const startButton = (action) => {
    keysRef.current.add(action)
    setActiveKeys(new Set(keysRef.current))
    if (!intervalRef.current) {
      sendCommand()
      intervalRef.current = setInterval(sendCommand, SEND_INTERVAL_MS)
    }
  }

  const stopButton = (action) => {
    keysRef.current.delete(action)
    setActiveKeys(new Set(keysRef.current))
    if (keysRef.current.size === 0) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
      apiClient.sendTeleop(0, 0).catch(() => {})
    }
  }

  const stopAll = () => {
    keysRef.current.clear()
    setActiveKeys(new Set())
    clearInterval(intervalRef.current)
    intervalRef.current = null
    apiClient.sendTeleop(0, 0).catch(() => {})
  }

  const btn = (action, label) => (
    <button
      className={`teleop-btn ${activeKeys.has(action) ? 'active' : ''}`}
      onMouseDown={() => startButton(action)}
      onMouseUp={() => stopButton(action)}
      onMouseLeave={() => stopButton(action)}
      onTouchStart={(e) => { e.preventDefault(); startButton(action) }}
      onTouchEnd={(e) => { e.preventDefault(); stopButton(action) }}
    >
      {label}
    </button>
  )

  return (
    <div className="teleop-pad">
      <div className="teleop-title">Manual Control</div>
      <div className="teleop-hint">W/A/S/D or arrow keys</div>
      <div className="teleop-grid">
        <div className="teleop-row">
          <div className="teleop-spacer" />
          {btn('forward', '\u25B2')}
          <div className="teleop-spacer" />
        </div>
        <div className="teleop-row">
          {btn('left', '\u25C0')}
          <button className="teleop-btn teleop-stop" onClick={stopAll}>STOP</button>
          {btn('right', '\u25B6')}
        </div>
        <div className="teleop-row">
          <div className="teleop-spacer" />
          {btn('backward', '\u25BC')}
          <div className="teleop-spacer" />
        </div>
      </div>
    </div>
  )
}
