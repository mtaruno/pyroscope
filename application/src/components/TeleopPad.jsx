import { useEffect, useRef, useState } from 'react'
import apiClient from '../services/api'
import './TeleopPad.css'

const LINEAR_SPEED_LIMIT = 0.45
const ANGULAR_SPEED_LIMIT = 2.0
const DEFAULT_LINEAR_SPEED = 0.3
const DEFAULT_ANGULAR_SPEED = 1.2
const SPEED_STEP = 1.1
const MOVEMENT_BOOST_STEP = 0.15
const MAX_MOVEMENT_BOOST = 2.0
const SEND_INTERVAL_MS = 150

const MOVEMENT_KEYMAP = {
  w: ['forward'],
  ArrowUp: ['forward'],
  i: ['forward'],
  s: ['backward'],
  ArrowDown: ['backward'],
  ',': ['backward'],
  a: ['left'],
  ArrowLeft: ['left'],
  j: ['left'],
  d: ['right'],
  ArrowRight: ['right'],
  l: ['right'],
  u: ['forward', 'left'],
  o: ['forward', 'right'],
  m: ['backward', 'left'],
  '.': ['backward', 'right'],
}

const SPEED_KEYMAP = {
  Q: { linear: SPEED_STEP, angular: SPEED_STEP },
  Z: { linear: 1 / SPEED_STEP, angular: 1 / SPEED_STEP },
  W: { linear: SPEED_STEP, angular: 1 },
  X: { linear: 1 / SPEED_STEP, angular: 1 },
  E: { linear: 1, angular: SPEED_STEP },
  C: { linear: 1, angular: 1 / SPEED_STEP },
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function createActionCounts() {
  return { forward: 0, backward: 0, left: 0, right: 0 }
}

function createActionBoosts() {
  return { forward: 1, backward: 1, left: 1, right: 1 }
}

function isEditableTarget(target) {
  if (!target) return false
  const tagName = target.tagName?.toLowerCase()
  return tagName === 'input' || tagName === 'textarea' || tagName === 'select' || target.isContentEditable
}

function normalizeMovementKey(key) {
  return key.length === 1 ? key.toLowerCase() : key
}

export default function TeleopPad({ embedded = false }) {
  const [activeActions, setActiveActions] = useState(new Set())
  const [linearSpeed, setLinearSpeed] = useState(DEFAULT_LINEAR_SPEED)
  const [angularSpeed, setAngularSpeed] = useState(DEFAULT_ANGULAR_SPEED)
  const [boostSnapshot, setBoostSnapshot] = useState(createActionBoosts())

  const intervalRef = useRef(null)
  const inputActionsRef = useRef(new Map())
  const actionCountsRef = useRef(createActionCounts())
  const actionBoostsRef = useRef(createActionBoosts())
  const speedRef = useRef({
    linear: DEFAULT_LINEAR_SPEED,
    angular: DEFAULT_ANGULAR_SPEED,
  })

  const syncBoostSnapshot = () => {
    setBoostSnapshot({ ...actionBoostsRef.current })
  }

  const syncActiveActions = () => {
    const nextActive = new Set(
      Object.entries(actionCountsRef.current)
        .filter(([, count]) => count > 0)
        .map(([action]) => action)
    )
    setActiveActions(nextActive)
    return nextActive
  }

  const computeVelocity = () => {
    const counts = actionCountsRef.current
    const speeds = speedRef.current
    const boosts = actionBoostsRef.current
    const linearDirection = (counts.forward > 0 ? 1 : 0) - (counts.backward > 0 ? 1 : 0)
    const angularDirection = (counts.left > 0 ? 1 : 0) - (counts.right > 0 ? 1 : 0)
    const linearBoost = linearDirection > 0
      ? boosts.forward
      : linearDirection < 0
        ? boosts.backward
        : 1
    const angularBoost = angularDirection > 0
      ? boosts.left
      : angularDirection < 0
        ? boosts.right
        : 1
    return {
      lx: clamp(linearDirection * speeds.linear * linearBoost, -LINEAR_SPEED_LIMIT, LINEAR_SPEED_LIMIT),
      az: clamp(angularDirection * speeds.angular * angularBoost, -ANGULAR_SPEED_LIMIT, ANGULAR_SPEED_LIMIT),
    }
  }

  const sendCommand = () => {
    const { lx, az } = computeVelocity()
    apiClient.sendTeleop(lx, az).catch(() => {})
  }

  const clearIntervalLoop = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }

  const ensureIntervalLoop = () => {
    if (intervalRef.current) return
    sendCommand()
    intervalRef.current = setInterval(sendCommand, SEND_INTERVAL_MS)
  }

  const updateSpeed = (nextLinear, nextAngular) => {
    const clampedLinear = clamp(nextLinear, 0.05, LINEAR_SPEED_LIMIT)
    const clampedAngular = clamp(nextAngular, 0.2, ANGULAR_SPEED_LIMIT)
    speedRef.current = { linear: clampedLinear, angular: clampedAngular }
    setLinearSpeed(clampedLinear)
    setAngularSpeed(clampedAngular)
    if (inputActionsRef.current.size > 0) {
      sendCommand()
    }
  }

  const applySpeedAdjustment = (adjustment) => {
    updateSpeed(
      speedRef.current.linear * adjustment.linear,
      speedRef.current.angular * adjustment.angular
    )
  }

  const addInput = (inputId, actions) => {
    if (inputActionsRef.current.has(inputId)) return
    inputActionsRef.current.set(inputId, actions)
    actions.forEach((action) => {
      if (actionCountsRef.current[action] === 0) {
        actionBoostsRef.current[action] = 1
      }
      actionCountsRef.current[action] += 1
    })
    syncBoostSnapshot()
    syncActiveActions()
    ensureIntervalLoop()
  }

  const boostActions = (actions) => {
    let changed = false
    actions.forEach((action) => {
      if (actionCountsRef.current[action] <= 0) return
      const nextBoost = clamp(
        actionBoostsRef.current[action] + MOVEMENT_BOOST_STEP,
        1,
        MAX_MOVEMENT_BOOST
      )
      if (nextBoost !== actionBoostsRef.current[action]) {
        actionBoostsRef.current[action] = nextBoost
        changed = true
      }
    })
    if (changed) {
      syncBoostSnapshot()
      sendCommand()
    }
  }

  const removeInput = (inputId) => {
    const actions = inputActionsRef.current.get(inputId)
    if (!actions) return
    inputActionsRef.current.delete(inputId)
    actions.forEach((action) => {
      actionCountsRef.current[action] = Math.max(0, actionCountsRef.current[action] - 1)
      if (actionCountsRef.current[action] === 0) {
        actionBoostsRef.current[action] = 1
      }
    })
    syncBoostSnapshot()
    const nextActive = syncActiveActions()
    if (nextActive.size === 0) {
      clearIntervalLoop()
      apiClient.sendTeleop(0, 0).catch(() => {})
    } else {
      sendCommand()
    }
  }

  const stopAll = () => {
    inputActionsRef.current.clear()
    actionCountsRef.current = createActionCounts()
    actionBoostsRef.current = createActionBoosts()
    setActiveActions(new Set())
    syncBoostSnapshot()
    clearIntervalLoop()
    apiClient.sendTeleop(0, 0).catch(() => {})
  }

  const resetSpeeds = () => {
    updateSpeed(DEFAULT_LINEAR_SPEED, DEFAULT_ANGULAR_SPEED)
  }

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.altKey || event.ctrlKey || event.metaKey || isEditableTarget(event.target)) return

      const speedAdjustment = SPEED_KEYMAP[event.key]
      if (speedAdjustment) {
        event.preventDefault()
        if (!event.repeat) applySpeedAdjustment(speedAdjustment)
        return
      }

      const key = normalizeMovementKey(event.key)
      if (key === ' ' || key === 'k') {
        event.preventDefault()
        if (!event.repeat) stopAll()
        return
      }

      const actions = MOVEMENT_KEYMAP[key]
      if (!actions) return
      event.preventDefault()
      if (inputActionsRef.current.has(`key:${key}`)) {
        boostActions(actions)
        return
      }
      addInput(`key:${key}`, actions)
    }

    const onKeyUp = (event) => {
      const key = normalizeMovementKey(event.key)
      const actions = MOVEMENT_KEYMAP[key]
      if (!actions) return
      event.preventDefault()
      removeInput(`key:${key}`)
    }

    const onWindowBlur = () => stopAll()
    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') stopAll()
    }

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    window.addEventListener('blur', onWindowBlur)
    document.addEventListener('visibilitychange', onVisibilityChange)

    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      window.removeEventListener('blur', onWindowBlur)
      document.removeEventListener('visibilitychange', onVisibilityChange)
      clearIntervalLoop()
      apiClient.sendTeleop(0, 0).catch(() => {})
    }
  }, [])

  const command = computeVelocity()
  const maxActiveBoost = Math.max(
    ...Object.entries(boostSnapshot)
      .filter(([action]) => activeActions.has(action))
      .map(([, value]) => value),
    1
  )

  const directionalButton = (action, label) => (
    <button
      className={`teleop-btn ${activeActions.has(action) ? 'active' : ''}`}
      onMouseDown={() => addInput(`button:${action}`, [action])}
      onMouseUp={() => removeInput(`button:${action}`)}
      onMouseLeave={() => removeInput(`button:${action}`)}
      onTouchStart={(event) => {
        event.preventDefault()
        addInput(`button:${action}`, [action])
      }}
      onTouchEnd={(event) => {
        event.preventDefault()
        removeInput(`button:${action}`)
      }}
      onTouchCancel={(event) => {
        event.preventDefault()
        removeInput(`button:${action}`)
      }}
    >
      {label}
    </button>
  )

  return (
    <div className={`teleop-pad ${embedded ? 'embedded' : ''}`}>
      <div className="teleop-header">
        <div className="teleop-title">Manual Control</div>
        <button className="teleop-reset" onClick={resetSpeeds}>Reset</button>
      </div>

      <div className="teleop-hint">W/A/S/D, arrows, I/J/K/L, U/O/M/. for diagonals. Tap the same direction again to boost. Space or K to stop</div>

      <div className="teleop-speed-panel">
        <label className="teleop-speed-control">
          <span>Linear {linearSpeed.toFixed(2)} m/s</span>
          <input
            type="range"
            min="0.05"
            max={LINEAR_SPEED_LIMIT}
            step="0.01"
            value={linearSpeed}
            onChange={(event) => updateSpeed(Number(event.target.value), angularSpeed)}
          />
        </label>

        <label className="teleop-speed-control">
          <span>Angular {angularSpeed.toFixed(2)} rad/s</span>
          <input
            type="range"
            min="0.2"
            max={ANGULAR_SPEED_LIMIT}
            step="0.05"
            value={angularSpeed}
            onChange={(event) => updateSpeed(linearSpeed, Number(event.target.value))}
          />
        </label>
      </div>

      <div className="teleop-shortcuts">Shift+Q/Z all speed, Shift+W/X linear only, Shift+E/C turn only</div>
      <div className="teleop-status">
        Command {command.lx.toFixed(2)} m/s, {command.az.toFixed(2)} rad/s
      </div>
      <div className="teleop-boost">
        Active boost {maxActiveBoost.toFixed(2)}x
      </div>

      <div className="teleop-grid">
        <div className="teleop-row">
          <div className="teleop-spacer" />
          {directionalButton('forward', '\u25B2')}
          <div className="teleop-spacer" />
        </div>
        <div className="teleop-row">
          {directionalButton('left', '\u25C0')}
          <button className="teleop-btn teleop-stop" onClick={stopAll}>STOP</button>
          {directionalButton('right', '\u25B6')}
        </div>
        <div className="teleop-row">
          <div className="teleop-spacer" />
          {directionalButton('backward', '\u25BC')}
          <div className="teleop-spacer" />
        </div>
      </div>
    </div>
  )
}
