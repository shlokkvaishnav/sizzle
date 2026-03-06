import { useState, useRef, useEffect, forwardRef, useImperativeHandle } from 'react'
import { Mic } from 'lucide-react'

const VISUALIZER_BARS = 48
const SPEECH_THRESHOLD = 12       // avg freq-bin value above this = speech
const SILENCE_TIMEOUT_MS = 2500   // ms of post-speech silence → auto-stop
const MAX_WAIT_NO_SPEECH_MS = 6000 // ms with no speech → auto-stop
const MAX_RECORD_MS = 15000       // hard cap on recording length

const VoiceRecorder = forwardRef(function VoiceRecorder(props, ref) {
  const { onRecorded, onStartRecording, autoListen, onAutoListenSilence } = props

  const [state, setState] = useState('idle') // idle | recording | processing
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const analyserCtxRef = useRef(null)
  const animFrameRef = useRef(null)
  const streamRef = useRef(null)
  const [time, setTime] = useState(0)
  const [barHeights, setBarHeights] = useState(
    Array.from({ length: VISUALIZER_BARS }, () => 4)
  )

  // Stable refs for props (avoids stale closures in async / RAF callbacks)
  const propsRef = useRef({})
  propsRef.current = { onRecorded, onStartRecording, autoListen, onAutoListenSilence }

  // Silence-detection refs
  const silenceStartRef = useRef(null)
  const speechDetectedRef = useRef(false)
  const recordingStartRef = useRef(null)
  const stoppedRef = useRef(false)

  const isRecording = state === 'recording'
  const isProcessing = state === 'processing'

  // ── Stable function refs (always latest closure) ──
  const fnRef = useRef({})

  fnRef.current.stopRecording = () => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop()
    }
  }

  fnRef.current.startRecording = async (interrupt = true) => {
    try {
      // Interrupt TTS only on manual click (not auto-listen restart)
      if (interrupt && propsRef.current.onStartRecording) {
        propsRef.current.onStartRecording()
      }

      // Reset silence-detection state
      silenceStartRef.current = null
      speechDetectedRef.current = false
      recordingStartRef.current = Date.now()
      stoppedRef.current = false

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const audioCtx = new AudioContext()
      const source = audioCtx.createMediaStreamSource(stream)
      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 256
      source.connect(analyser)
      analyserCtxRef.current = { audioCtx, analyser }

      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mediaRecorderRef.current = recorder
      chunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        stream.getTracks().forEach(t => t.stop())
        streamRef.current = null
        if (analyserCtxRef.current?.audioCtx) analyserCtxRef.current.audioCtx.close()
        if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)

        // Auto-listen mode + no speech detected → skip processing, go idle
        if (propsRef.current.autoListen && !speechDetectedRef.current) {
          setState('idle')
          if (propsRef.current.onAutoListenSilence) propsRef.current.onAutoListenSilence()
          return
        }

        setState('processing')
        if (propsRef.current.onRecorded) {
          Promise.resolve(propsRef.current.onRecorded(blob)).finally(() => setState('idle'))
        } else {
          setState('idle')
        }
      }

      recorder.start()
      setState('recording')

      // ── Analysis loop (visualizer + silence detection) ──
      const data = new Uint8Array(analyser.frequencyBinCount)
      const tick = () => {
        if (!mediaRecorderRef.current || mediaRecorderRef.current.state !== 'recording') return
        analyser.getByteFrequencyData(data)
        const sum = data.reduce((a, b) => a + b, 0)
        const avg = sum / data.length

        // Silence detection (only when auto-listen is on)
        if (propsRef.current.autoListen && !stoppedRef.current) {
          const now = Date.now()
          const elapsed = now - (recordingStartRef.current || now)

          if (avg > SPEECH_THRESHOLD) {
            speechDetectedRef.current = true
            silenceStartRef.current = null
          } else if (speechDetectedRef.current) {
            // Had speech, now silent
            if (!silenceStartRef.current) {
              silenceStartRef.current = now
            } else if (now - silenceStartRef.current > SILENCE_TIMEOUT_MS) {
              stoppedRef.current = true
              fnRef.current.stopRecording()
              return
            }
          } else if (elapsed > MAX_WAIT_NO_SPEECH_MS) {
            // Never heard speech — give up
            stoppedRef.current = true
            fnRef.current.stopRecording()
            return
          }

          if (elapsed > MAX_RECORD_MS) {
            stoppedRef.current = true
            fnRef.current.stopRecording()
            return
          }
        }

        animFrameRef.current = requestAnimationFrame(tick)
      }
      animFrameRef.current = requestAnimationFrame(tick)
    } catch (err) {
      console.error('Mic access failed:', err)
      alert('Microphone access denied. Please allow microphone access.')
    }
  }

  // Expose start/stop to parent via ref
  useImperativeHandle(ref, () => ({
    startRecording: () => fnRef.current.startRecording(false),
    stopRecording: () => fnRef.current.stopRecording(),
  }))

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop())
    }
  }, [])

  // Timer: count seconds while recording
  useEffect(() => {
    let intervalId
    if (isRecording) {
      intervalId = setInterval(() => setTime(t => t + 1), 1000)
    } else {
      setTime(0)
    }
    return () => clearInterval(intervalId)
  }, [isRecording])

  // Randomise bars while recording for visual effect
  useEffect(() => {
    let frameId
    if (isRecording) {
      const animate = () => {
        setBarHeights(
          Array.from({ length: VISUALIZER_BARS }, () => 20 + Math.random() * 80)
        )
        frameId = requestAnimationFrame(animate)
      }
      frameId = requestAnimationFrame(animate)
    } else {
      setBarHeights(Array.from({ length: VISUALIZER_BARS }, () => 4))
    }
    return () => { if (frameId) cancelAnimationFrame(frameId) }
  }, [isRecording])

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  const handleClick = () => {
    if (isProcessing) return
    if (isRecording) {
      fnRef.current.stopRecording()
    } else {
      fnRef.current.startRecording(true) // true = interrupt TTS
    }
  }

  return (
    <div className="ai-voice-wrap">
      {/* Mic / Stop button */}
      <button
        className={`ai-voice-btn${isRecording ? ' ai-voice-btn--active' : ''}`}
        type="button"
        onClick={handleClick}
        disabled={isProcessing}
      >
        {isProcessing ? (
          <div className="spinner" style={{ width: 20, height: 20, borderWidth: 2 }} />
        ) : isRecording ? (
          <div className="ai-voice-stop" />
        ) : (
          <Mic size={24} />
        )}
      </button>

      {/* Timer */}
      <span
        className="ai-voice-timer"
        style={{ opacity: isRecording ? 0.7 : 0.3 }}
      >
        {formatTime(time)}
      </span>

      {/* Visualizer bars */}
      <div className="ai-voice-bars">
        {Array.from({ length: VISUALIZER_BARS }).map((_, i) => (
          <div
            key={i}
            className={`ai-voice-bar${isRecording ? ' ai-voice-bar--active' : ''}`}
            style={
              isRecording
                ? { height: `${barHeights[i]}%`, animationDelay: `${i * 0.05}s` }
                : { height: 4 }
            }
          />
        ))}
      </div>

      {/* Status label */}
      <p className="ai-voice-status">
        {isProcessing
          ? 'Processing…'
          : isRecording
            ? 'Listening...'
            : autoListen ? 'Speak anytime…' : 'Click to speak'}
      </p>
    </div>
  )
})

VoiceRecorder.displayName = 'VoiceRecorder'
export default VoiceRecorder
