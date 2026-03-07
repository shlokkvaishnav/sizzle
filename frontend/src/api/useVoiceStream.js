import { useRef, useCallback, useState, useEffect } from 'react'

/**
 * useVoiceStream — WebSocket-based real-time voice streaming hook.
 *
 * Connects to the backend WebSocket at /api/voice/stream and streams
 * audio chunks in real-time. Receives partial transcripts and
 * pipeline results as they arrive.
 *
 * IMPORTANT: pass `sessionIdRef`, `languageRef`, and `restaurantIdRef`
 * as React ref objects (not plain values). This ensures sendConfig()
 * always reads the freshest values at call-time, avoiding stale-closure
 * and race-condition bugs when startCall() regenerates the session ID
 * just before calling connect().
 *
 * Usage:
 *   const sessionId  = useRef(generateSessionId())
 *   const { connect, disconnect, sendAudioChunk, sendEnd,
 *           partialTranscript, isConnected } = useVoiceStream({
 *     sessionIdRef: sessionId,       // ← pass the ref, not .current
 *     languageRef,
 *     restaurantIdRef,
 *     onPipelineResult: (result) => { ... },
 *     onTTSChunk: (audio_b64, payload) => { ... },
 *     onError: (detail) => { ... },
 *   })
 */

const WS_BASE = (() => {
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_WS_BASE_URL) {
    return import.meta.env.VITE_WS_BASE_URL.replace(/\/$/, '')
  }
  if (typeof window !== 'undefined' && window.location) {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${window.location.host}/api/voice`
  }
  return 'ws://localhost:3000/api/voice'
})()

export default function useVoiceStream({
  onPipelineResult,
  onTTSChunk,
  onError,
  // Accept ref objects so we always read the latest value at call-time.
  // Falls back gracefully if a plain value is passed (for backward compat).
  sessionIdRef,
  languageRef,
  restaurantIdRef,
} = {}) {
  const wsRef = useRef(null)
  const connectPromiseRef = useRef(null)
  const [isConnected, setIsConnected] = useState(false)
  const [partialTranscript, setPartialTranscript] = useState('')
  const [finalTranscript, setFinalTranscript] = useState('')
  const callbacksRef = useRef({ onPipelineResult, onTTSChunk, onError })

  // Keep callbacks fresh without re-creating connect/disconnect closures
  useEffect(() => {
    callbacksRef.current = { onPipelineResult, onTTSChunk, onError }
  })

  /**
   * Read the current values from the refs at call-time.
   * Supports both ref objects ({ current: value }) and plain values.
   */
  const readSessionId = useCallback(
    () => (sessionIdRef && typeof sessionIdRef === 'object' && 'current' in sessionIdRef
      ? sessionIdRef.current
      : sessionIdRef),
    [sessionIdRef],
  )
  const readLanguage = useCallback(
    () => {
      const lang = languageRef && typeof languageRef === 'object' && 'current' in languageRef
        ? languageRef.current
        : languageRef
      return lang !== 'auto' ? lang : null
    },
    [languageRef],
  )
  const readRestaurantId = useCallback(
    () => (restaurantIdRef && typeof restaurantIdRef === 'object' && 'current' in restaurantIdRef
      ? restaurantIdRef.current
      : restaurantIdRef),
    [restaurantIdRef],
  )

  /**
   * Send the config frame over the open WebSocket.
   * Reads live ref values — never stale.
   */
  const sendConfig = useCallback(() => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) return false
    wsRef.current.send(JSON.stringify({
      type: 'config',
      session_id: readSessionId(),
      language: readLanguage(),
      restaurant_id: readRestaurantId(),
    }))
    return true
  }, [readSessionId, readLanguage, readRestaurantId])

  /**
   * Open a WebSocket connection (idempotent — reuses an open socket).
   * Returns a promise that resolves to true on success, false on failure.
   */
  const connect = useCallback(async () => {
    // Already open — just refresh config and return
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      sendConfig()
      return true
    }

    // Already connecting — reuse the pending promise
    if (connectPromiseRef.current) {
      return connectPromiseRef.current
    }

    connectPromiseRef.current = new Promise((resolve) => {
      const ws = new WebSocket(`${WS_BASE}/stream`)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        // sendConfig reads fresh ref values right now — no stale closure
        sendConfig()
        connectPromiseRef.current = null
        resolve(true)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          switch (data.type) {
            case 'partial_transcript':
              setPartialTranscript(data.text || '')
              break

            case 'final_transcript':
              setPartialTranscript('')
              setFinalTranscript(data.text || '')
              break

            case 'pipeline_result':
              setPartialTranscript('')
              if (callbacksRef.current.onPipelineResult) {
                callbacksRef.current.onPipelineResult(data)
              }
              break

            case 'tts_chunk':
              if (callbacksRef.current.onTTSChunk && data.audio_b64) {
                callbacksRef.current.onTTSChunk(data.audio_b64, data)
              }
              break

            case 'error':
              if (callbacksRef.current.onError) {
                callbacksRef.current.onError(data.detail || 'Stream error')
              }
              break

            case 'config_ack':
            case 'interrupted':
              // Acknowledged — no action needed
              break

            default:
              break
          }
        } catch {
          // Non-JSON frame — ignore
        }
      }

      ws.onclose = () => {
        connectPromiseRef.current = null
        setIsConnected(false)
      }

      ws.onerror = () => {
        connectPromiseRef.current = null
        setIsConnected(false)
        if (callbacksRef.current.onError) {
          callbacksRef.current.onError('WebSocket connection failed')
        }
        resolve(false)
      }
    })

    return connectPromiseRef.current
  }, [sendConfig])

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    connectPromiseRef.current = null
    setIsConnected(false)
    setPartialTranscript('')
  }, [])

  const sendAudioChunk = useCallback((chunk) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(chunk)
    }
  }, [])

  const sendEnd = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'end' }))
    }
  }, [])

  const sendInterrupt = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'interrupt' }))
    }
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [])

  return {
    connect,
    disconnect,
    sendConfig,
    sendAudioChunk,
    sendEnd,
    sendInterrupt,
    isConnected,
    partialTranscript,
    finalTranscript,
  }
}
