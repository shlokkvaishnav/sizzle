import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { MicOff, PhoneCall, PhoneOff, Volume2 } from 'lucide-react'
import { confirmOrder, speakText, submitTextOrder } from '../api/client'
import useVoiceStream from '../api/useVoiceStream'
import VoiceRecorder from '../components/VoiceRecorder'
import OrderSummary from '../components/OrderSummary'
import { playAudioWithFallback, stopBrowserSpeech } from '../utils/ttsPlayback'
import { VOICE_AUTO_LISTEN_DELAY_MS } from '../config'

function generateSessionId() {
  return 'call-' + Math.random().toString(36).slice(2, 10)
}

function getRestaurantId() {
  try {
    const saved = JSON.parse(localStorage.getItem('sizzle_restaurant') || '{}')
    return saved.restaurant_id || null
  } catch {
    return null
  }
}

const OPENING_PROMPTS = {
  en: 'Hello, thanks for calling Sizzle. What would you like to order today?',
  hi: 'Namaste, Sizzle mein aapka swagat hai. Aaj aap kya order karna chahenge?',
  gu: 'નમસ્તે, Sizzle માં આપનું સ્વાગત છે. આજે તમે શું ઓર્ડર કરશો?',
  mr: 'नमस्कार, Sizzle मध्ये तुमचं स्वागत आहे. आज तुम्हाला काय ऑर्डर करायचं आहे?',
  kn: 'ನಮಸ್ಕಾರ, Sizzle ಗೆ ಸ್ವಾಗತ. ಇಂದು ನೀವು ಏನು order ಮಾಡುತ್ತೀರಿ?',
}

const SILENCE_PROMPTS = {
  en: 'I did not hear anything. Would you like to add anything else, or should I place the order?',
  hi: 'Mujhe kuch sunai nahi diya. Aur kuch add karna hai, ya main order place kar doon?',
  gu: 'મને કંઈ સંભળાયું નહીં. બીજું કંઈ ઉમેરવું છે કે હું ઓર્ડર મૂકી દઉં?',
  mr: 'मला काही ऐकू आलं नाही. अजून काही जोडायचं आहे का, की मी ऑर्डर लावू?',
  kn: 'ನನಗೆ ಏನೂ ಕೇಳಿಸಲಿಲ್ಲ. ಇನ್ನೇನಾದರೂ ಸೇರಿಸಬೇಕೇ, ಇಲ್ಲವೇ ನಾನು order ಮಾಡಲೇ?',
}

const NO_CART_SILENCE_PROMPTS = {
  en: 'I did not hear anything. What would you like to order?',
  hi: 'Mujhe kuch sunai nahi diya. Aap kya order karna chahenge?',
  gu: 'મને કંઈ સંભળાયું નહીં. તમે શું ઓર્ડર કરશો?',
  mr: 'मला काही ऐकू आलं नाही. तुम्हाला काय ऑर्डर करायचं आहे?',
  kn: 'ನನಗೆ ಏನೂ ಕೇಳಿಸಲಿಲ್ಲ. ನೀವು ಏನು order ಮಾಡುತ್ತೀರಿ?',
}

const STATUS_COPY = {
  idle: 'Ready to start',
  connecting: 'Connecting call',
  active: 'Call in progress',
  listening: 'Customer speaking',
  processing: 'Agent processing',
  speaking: 'Agent speaking',
  ended: 'Call ended',
}

const SILENCE_REPROMPT_LIMIT = 2

function getVoiceLanguage(selectedLanguage, result) {
  const candidate = result?.tts_language || result?.detected_language
  if (candidate && OPENING_PROMPTS[candidate]) return candidate
  if (selectedLanguage !== 'auto' && OPENING_PROMPTS[selectedLanguage]) return selectedLanguage
  return 'en'
}

function formatDuration(seconds) {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

function normalizeOrder(order) {
  if (!order) return null
  return {
    ...order,
    items: (order.items || []).map((item) => ({
      ...item,
      name: item.name || item.item_name,
    })),
  }
}

export default function WebCall() {
  const [result, setResult] = useState(null)
  const [conversation, setConversation] = useState([])
  const [status, setStatus] = useState('idle')
  const [callActive, setCallActive] = useState(false)
  const [micPaused, setMicPaused] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [selectedLanguage, setSelectedLanguage] = useState('auto')
  const [error, setError] = useState(null)
  const [manualText, setManualText] = useState('')
  const [seconds, setSeconds] = useState(0)
  const [orderPlaced, setOrderPlaced] = useState(false)     // shows ✓ toast
  const [ordersRefreshKey, setOrdersRefreshKey] = useState(0) // increments to trigger orders re-fetch
  const [quickOptions, setQuickOptions] = useState([])        // tap-to-speak option buttons
  // Keep refs in sync so useVoiceStream always reads the latest values
  // without needing to re-create the WebSocket on every state change.
  const sessionId = useRef(generateSessionId())
  const selectedLanguageRef = useRef('auto')
  const restaurantIdRef = useRef(getRestaurantId())
  useEffect(() => { selectedLanguageRef.current = selectedLanguage }, [selectedLanguage])
  const currentAudioRef = useRef(null)
  const recorderRef = useRef(null)
  const callActiveRef = useRef(false)
  const micPausedRef = useRef(false)
  const lastIntentRef = useRef(null)
  const sendInterruptRef = useRef(() => { })
  const silenceRepromptCountRef = useRef(0)
  // Timer used to defer browser-TTS fallback: cancelled if real TTS audio arrives first
  const ttsTextFallbackTimerRef = useRef(null)
  // Buffer for streaming TTS chunks — accumulate then play when is_last=true
  const ttsChunkBufferRef = useRef([])
  const ttsChunkTimeoutRef = useRef(null)   // safety: flush buffer if is_last never arrives
  const lastSpokenTextRef = useRef(null)     // track last spoken text for fallback
  const restaurantId = restaurantIdRef.current

  const appendMessage = useCallback((role, text, language = 'en') => {
    if (!text) return
    setConversation((prev) => {
      const last = prev[prev.length - 1]
      if (last && last.role === role && last.text === text) return prev
      return [...prev, {
        id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        role,
        text,
        language,
        time: new Date().toLocaleTimeString(),
      }]
    })
  }, [])

  const playVoiceResponse = useCallback((base64Audio, spokenText = null, language = null) => {
    const resolvedLanguage = language || (selectedLanguage !== 'auto' ? selectedLanguage : 'en')

    if (currentAudioRef.current) {
      currentAudioRef.current.pause()
      currentAudioRef.current.src = ''
      currentAudioRef.current = null
    }

    playAudioWithFallback({
      base64Audio,
      text: spokenText,
      language: resolvedLanguage,
      currentAudioRef,
      onStart: () => {
        setIsSpeaking(true)
        setStatus('speaking')
      },
      onEnd: () => {
        setIsSpeaking(false)
        if (callActiveRef.current && !micPausedRef.current && lastIntentRef.current !== 'CONFIRM') {
          setTimeout(() => recorderRef.current?.startRecording(), VOICE_AUTO_LISTEN_DELAY_MS)
        }
      },
      onError: () => setIsSpeaking(false),
    })
  }, [selectedLanguage])

  const stopAudio = useCallback(() => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause()
      currentAudioRef.current.src = ''
      currentAudioRef.current = null
    }
    stopBrowserSpeech()
    setIsSpeaking(false)
  }, [])

  const handleInterruptAudio = useCallback(() => {
    stopAudio()
    sendInterruptRef.current()
  }, [stopAudio])

  const activeLanguage = useMemo(
    () => getVoiceLanguage(selectedLanguage, result),
    [result, selectedLanguage],
  )

  // Keep track of the last valid order so QUERY / UNKNOWN turns don't wipe the cart
  const lastKnownOrderRef = useRef(null)
  const effectiveOrder = useMemo(() => {
    const newOrder = normalizeOrder(result?.session_order || result?.order)
    if (newOrder) {
      lastKnownOrderRef.current = newOrder
      return newOrder
    }
    // No order in this response — keep showing the previous one
    return lastKnownOrderRef.current
  }, [result])
  const hasCart = (result?.session_items || result?.items || []).length > 0 || !!effectiveOrder

  const speakAgentPrompt = useCallback(async (text, language) => {
    appendMessage('agent', text, language)
    try {
      const tts = await speakText(text, language)
      playVoiceResponse(tts?.audio_b64, tts?.text || text, language)
    } catch {
      playVoiceResponse(null, text, language)
    }
  }, [appendMessage, playVoiceResponse])

  const {
    connect,
    disconnect,
    sendAudioChunk,
    sendEnd,
    sendInterrupt,
    isConnected,
    partialTranscript,
  } = useVoiceStream({
    // Pass ref objects — the hook reads .current at call-time, so it always
    // gets the freshest session ID / language even after startCall() regenerates.
    sessionIdRef: sessionId,
    languageRef: selectedLanguageRef,
    restaurantIdRef: restaurantIdRef,
    onPipelineResult: (data) => {
      setError(null)
      setResult(data)
      setStatus('active')
      silenceRepromptCountRef.current = 0
      lastIntentRef.current = data.intent
      if (data.transcript) {
        appendMessage('customer', data.transcript, data.detected_language || activeLanguage)
      }
      // If the backend already embedded tts_audio_b64 in the pipeline result, play it now.
      // Otherwise, if there's tts_text, defer browser-TTS by up to 1500ms so that the
      // tts_chunk (real Edge TTS audio) can arrive first and preempt the fallback.
      if (data.tts_audio_b64) {
        appendMessage('agent', data.tts_text || '', data.tts_language || data.detected_language || activeLanguage)
        playVoiceResponse(data.tts_audio_b64, data.tts_text, data.tts_language || data.detected_language || activeLanguage)
      } else if (data.tts_text) {
        // Don't play immediately — wait to see if tts_chunk with real audio arrives first
        const lang = data.tts_language || data.detected_language || activeLanguage
        const text = data.tts_text
        clearTimeout(ttsTextFallbackTimerRef.current)
        ttsTextFallbackTimerRef.current = setTimeout(() => {
          appendMessage('agent', text, lang)
          playVoiceResponse(null, text, lang)
          ttsTextFallbackTimerRef.current = null
        }, 1500)
      }
      if (data.intent === 'CONFIRM' && data.session_items?.length > 0) {
        void handleConfirmOrder(data)
      }

      // Build quick-option buttons for variant clarification & dessert/beverage upsell
      const newOptions = []

      // 1. Variant picks: e.g. 4 biryani types
      const disambig = data.disambiguation || []
      for (const entry of disambig) {
        if (entry.variant_query && entry.alternatives?.length > 0) {
          // All choices = the primary item + alternatives
          const choices = [
            { label: entry.item_name, text: entry.item_name },
            ...entry.alternatives.map(a => ({ label: a.item_name || a.matched_as, text: a.item_name || a.matched_as }))
          ].filter(c => c.label)
          newOptions.push(...choices.slice(0, 4))
          break // one disambiguation group at a time
        }
      }

      // 2. Dessert / beverage upsell: Yes / No buttons
      if (!newOptions.length && data.dessert_beverage_upsell?.length > 0) {
        const lang = data.detected_language || 'en'
        const YES_LABELS = { en: 'Yes, add some!', hi: 'Haan, add karo', gu: 'હા, ઉમેરો', mr: 'हो, जोडा', kn: 'ಹೌದು, ಸೇರಿಸಿ' }
        const NO_LABELS = { en: 'No thanks, place order', hi: 'Nahi, order karo', gu: 'ના, order કરો', mr: 'नाही, order करा', kn: 'ಬೇಡ, order ಮಾಡಿ' }
        const yesItems = data.dessert_beverage_upsell.map(s => s.item_name).join(', ')
        newOptions.push(
          { label: YES_LABELS[lang] || YES_LABELS.en, text: `Yes, add ${yesItems}` },
          { label: NO_LABELS[lang] || NO_LABELS.en, text: 'No, please confirm the order as is' }
        )
      }

      setQuickOptions(newOptions)
    },
    onTTSChunk: (audioB64, payload) => {
      // Real Edge TTS audio arrived — cancel any pending browser-TTS fallback
      if (ttsTextFallbackTimerRef.current) {
        clearTimeout(ttsTextFallbackTimerRef.current)
        ttsTextFallbackTimerRef.current = null
      }

      // Track spoken text for fallback
      if (payload?.spoken_text) {
        lastSpokenTextRef.current = payload.spoken_text
        appendMessage('agent', payload.spoken_text, payload.language || activeLanguage)
      }

      // Buffer chunks — MP3 fragments can't play individually
      if (audioB64 && audioB64.length > 0) {
        ttsChunkBufferRef.current.push(audioB64)
      }

      // Safety timeout: if is_last never arrives within 8s, flush buffer
      clearTimeout(ttsChunkTimeoutRef.current)
      if (!payload?.is_last) {
        ttsChunkTimeoutRef.current = setTimeout(() => {
          const chunks = ttsChunkBufferRef.current
          ttsChunkBufferRef.current = []
          if (chunks.length > 0) {
            // Play whatever we have
            const binaryChunks = chunks.map(b64 => {
              const binary = atob(b64)
              const bytes = new Uint8Array(binary.length)
              for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
              return bytes
            })
            const totalLen = binaryChunks.reduce((sum, c) => sum + c.length, 0)
            const combined = new Uint8Array(totalLen)
            let offset = 0
            for (const chunk of binaryChunks) { combined.set(chunk, offset); offset += chunk.length }
            const combinedB64 = btoa(String.fromCharCode(...combined))
            playVoiceResponse(combinedB64, lastSpokenTextRef.current, activeLanguage)
          } else if (lastSpokenTextRef.current) {
            // No audio chunks at all — browser TTS fallback
            playVoiceResponse(null, lastSpokenTextRef.current, activeLanguage)
          }
          ttsChunkTimeoutRef.current = null
        }, 8000)
      }

      // When the backend signals is_last=true, concatenate and play full audio
      if (payload?.is_last) {
        clearTimeout(ttsChunkTimeoutRef.current)
        ttsChunkTimeoutRef.current = null
        const chunks = ttsChunkBufferRef.current
        ttsChunkBufferRef.current = []  // reset buffer for next response

        if (chunks.length > 0) {
          // Decode all base64 chunks and concatenate into one Uint8Array
          const binaryChunks = chunks.map(b64 => {
            const binary = atob(b64)
            const bytes = new Uint8Array(binary.length)
            for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
            return bytes
          })
          const totalLen = binaryChunks.reduce((sum, c) => sum + c.length, 0)
          const combined = new Uint8Array(totalLen)
          let offset = 0
          for (const chunk of binaryChunks) { combined.set(chunk, offset); offset += chunk.length }

          const blob = new Blob([combined], { type: 'audio/mpeg' })
          const url = URL.createObjectURL(blob)
          // Reuse playVoiceResponse with the fully assembled audio
          const combinedB64 = btoa(String.fromCharCode(...combined))
          playVoiceResponse(combinedB64, payload?.spoken_text, payload?.language || activeLanguage)
        } else if (payload?.spoken_text) {
          // Sentinel with no accumulated chunks — fall back to browser TTS
          playVoiceResponse(null, payload.spoken_text, payload.language || activeLanguage)
        }
      }
    },
    onError: (detail) => {
      setError(detail || 'Call connection failed')
      setStatus('active')
    },
  })

  sendInterruptRef.current = sendInterrupt

  const handleConfirmOrder = useCallback(async (data = result) => {
    const orderToConfirm = data?.session_order || data?.order
    if (!orderToConfirm) return

    try {
      await confirmOrder(orderToConfirm, data?.kot)
      lastIntentRef.current = 'CONFIRM'
      setStatus('active')
      setOrderPlaced(true)            // show success toast
      setOrdersRefreshKey(k => k + 1) // trigger orders list refresh

      // Speak the closing message, then auto-reset the call
      await speakAgentPrompt(
        activeLanguage === 'en'
          ? 'Your order has been placed. Thank you for calling Sizzle.'
          : activeLanguage === 'hi'
            ? 'Aapka order place ho gaya. Sizzle ko call karne ke liye dhanyavaad.'
            : activeLanguage === 'gu'
              ? 'તમારો ઓર્ડર મૂકી દીધો છે. Sizzle ને call કરવા બદલ આભાર.'
              : activeLanguage === 'mr'
                ? 'तुमचा ऑर્डर लावला आहे. Sizzle ला call केल्याबद्दल धन्यवाद.'
                : 'ನಿಮ್ಮ order place ಆಗಿದೆ. Sizzle ಗೆ call ಮಾಡಿದಕ್ಕಾಗಿ ಧನ್ಯವಾದ.',
        activeLanguage,
      )

      // Auto-reset: give the user 2.5s to hear the closing, then hang up
      setTimeout(() => {
        // Stop recording + audio
        recorderRef.current?.stopRecording()
        handleInterruptAudio()
        disconnect()

        // Reset all call UI state
        callActiveRef.current = false
        micPausedRef.current = false
        setCallActive(false)
        setMicPaused(false)
        setStatus('idle')
        setResult(null)
        setConversation([])
        setSeconds(0)
        setError(null)
        silenceRepromptCountRef.current = 0
        lastIntentRef.current = null
        lastKnownOrderRef.current = null
        // Fresh session ID for the next call
        sessionId.current = generateSessionId()
        // Hide the toast after the reset
        setTimeout(() => setOrderPlaced(false), 2000)
      }, 2500)

    } catch (err) {
      setError(err.response?.data?.detail || err.detail || 'Order confirmation failed')
    }
  }, [activeLanguage, result, speakAgentPrompt, handleInterruptAudio, disconnect])

  const handleStreamStart = useCallback(async () => {
    if (!callActiveRef.current || micPausedRef.current) return false
    setStatus('listening')
    setError(null)
    return connect()
  }, [connect])

  const handleStreamEnd = useCallback(() => {
    setStatus('processing')
    sendEnd()
  }, [sendEnd])

  const handleStreamDiscard = useCallback(() => {
    sendInterrupt()
  }, [sendInterrupt])

  const handleAutoListenSilence = useCallback(() => {
    if (!callActiveRef.current || micPausedRef.current) return
    if (silenceRepromptCountRef.current >= SILENCE_REPROMPT_LIMIT) return

    silenceRepromptCountRef.current += 1
    const prompt = hasCart ? SILENCE_PROMPTS[activeLanguage] : NO_CART_SILENCE_PROMPTS[activeLanguage]
    void speakAgentPrompt(prompt, activeLanguage)
  }, [activeLanguage, hasCart, speakAgentPrompt])

  const startCall = useCallback(async () => {
    setError(null)
    setConversation([])
    setResult(null)
    setSeconds(0)
    setStatus('connecting')
    setCallActive(true)
    callActiveRef.current = true
    micPausedRef.current = false
    setMicPaused(false)
    silenceRepromptCountRef.current = 0
    lastKnownOrderRef.current = null
    sessionId.current = generateSessionId()

    // Stop any previous audio and cancel deferred TTS so only the agent (opening prompt) speaks
    stopAudio()
    if (ttsTextFallbackTimerRef.current) {
      clearTimeout(ttsTextFallbackTimerRef.current)
      ttsTextFallbackTimerRef.current = null
    }
    if (ttsChunkTimeoutRef.current) {
      clearTimeout(ttsChunkTimeoutRef.current)
      ttsChunkTimeoutRef.current = null
    }
    ttsChunkBufferRef.current = []

    const connected = await connect()
    if (!connected) {
      setStatus('idle')
      setCallActive(false)
      callActiveRef.current = false
      setError('Unable to start the call')
      return
    }

    lastIntentRef.current = 'GREETING'
    setStatus('active')
    await speakAgentPrompt(OPENING_PROMPTS[activeLanguage], activeLanguage)
  }, [activeLanguage, connect, speakAgentPrompt, stopAudio])

  const endCall = useCallback(() => {
    callActiveRef.current = false
    micPausedRef.current = false
    setCallActive(false)
    setMicPaused(false)
    setStatus('ended')
    recorderRef.current?.stopRecording()
    // Cancel any deferred TTS so they don't play after we start the next call
    if (ttsTextFallbackTimerRef.current) {
      clearTimeout(ttsTextFallbackTimerRef.current)
      ttsTextFallbackTimerRef.current = null
    }
    if (ttsChunkTimeoutRef.current) {
      clearTimeout(ttsChunkTimeoutRef.current)
      ttsChunkTimeoutRef.current = null
    }
    ttsChunkBufferRef.current = []
    handleInterruptAudio()
    disconnect()
    setQuickOptions([])   // clear option buttons on hang-up
  }, [disconnect, handleInterruptAudio])

  const toggleMicPause = useCallback(() => {
    const next = !micPausedRef.current
    micPausedRef.current = next
    setMicPaused(next)
    if (next) {
      recorderRef.current?.stopRecording()
      setStatus('active')
    } else if (callActiveRef.current && !isSpeaking) {
      recorderRef.current?.startRecording()
    }
  }, [isSpeaking])

  const handleManualText = useCallback(async () => {
    if (!manualText.trim()) return
    try {
      const data = await submitTextOrder(manualText, sessionId.current)
      setManualText('')
      setResult(data)
      setQuickOptions([])   // clear option buttons after user typed something
      appendMessage('customer', manualText, activeLanguage)
      if (data.tts_text) {
        appendMessage('agent', data.tts_text, data.tts_language || data.detected_language || activeLanguage)
      }
      if (data.tts_audio_b64 || data.tts_text) {
        playVoiceResponse(
          data.tts_audio_b64,
          data.tts_text,
          data.tts_language || data.detected_language || activeLanguage,
        )
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.detail || 'Could not send the fallback text')
    }
  }, [activeLanguage, appendMessage, manualText, playVoiceResponse])

  // Send a quick-option tap as a text order through the pipeline
  const handleQuickOption = useCallback(async (text) => {
    setQuickOptions([])
    try {
      stopAudio()
      appendMessage('customer', text, activeLanguage)
      const data = await submitTextOrder(text, sessionId.current)
      setResult(data)
      if (data.tts_text) {
        appendMessage('agent', data.tts_text, data.tts_language || data.detected_language || activeLanguage)
      }
      if (data.tts_audio_b64 || data.tts_text) {
        playVoiceResponse(
          data.tts_audio_b64,
          data.tts_text,
          data.tts_language || data.detected_language || activeLanguage,
        )
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Option selection failed')
    }
  }, [activeLanguage, appendMessage, playVoiceResponse, stopAudio])


  useEffect(() => {
    let intervalId
    if (callActive) {
      intervalId = setInterval(() => setSeconds((value) => value + 1), 1000)
    }
    return () => clearInterval(intervalId)
  }, [callActive])

  useEffect(() => {
    return () => {
      stopAudio()
      disconnect()
    }
  }, [disconnect, stopAudio])

  return (
    <motion.div
      className="app-page"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <div className="app-hero">
        <div>
          <div className="app-hero-eyebrow">Voice Ops</div>
          <h1 className="app-hero-title">Web Calling</h1>
          <p className="app-hero-sub">Browser-based ordering calls on the live voice pipeline, without PSTN billing.</p>
        </div>
        <div className="app-hero-metrics">
          <div className="app-kpi">
            <div className="app-kpi-label">Status</div>
            <div className="app-kpi-value" style={{ fontSize: 18 }}>{STATUS_COPY[status]}</div>
          </div>
          <div className="app-kpi">
            <div className="app-kpi-label">Call Timer</div>
            <div className="app-kpi-value">{formatDuration(seconds)}</div>
          </div>
          <div className="app-kpi">
            <div className="app-kpi-label">Channel</div>
            <div className="app-kpi-value" style={{ color: isConnected ? 'var(--success)' : 'var(--danger)' }}>
              {isConnected ? 'Connected' : 'Offline'}
            </div>
          </div>
        </div>
      </div>

      <div className="grid-2" style={{ alignItems: 'start' }}>
        <motion.div
          className="card"
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
        >
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>Call Console</span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {partialTranscript ? `Listening: "${partialTranscript}"` : STATUS_COPY[status]}
            </span>
          </div>
          <div className="card-body">
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
              {!callActive ? (
                <button className="btn btn-primary" onClick={startCall}>
                  <PhoneCall size={16} /> Start Call
                </button>
              ) : (
                <>
                  <button className="btn btn-primary" onClick={toggleMicPause}>
                    {micPaused ? <Volume2 size={16} /> : <MicOff size={16} />}
                    {micPaused ? 'Resume Mic' : 'Pause Mic'}
                  </button>
                  <button className="btn btn-ghost" onClick={endCall}>
                    <PhoneOff size={16} /> End Call
                  </button>
                </>
              )}
            </div>

            <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
              {[
                { code: 'auto', label: 'Auto' },
                { code: 'en', label: 'EN' },
                { code: 'hi', label: 'HI' },
                { code: 'gu', label: 'GU' },
                { code: 'mr', label: 'MR' },
                { code: 'kn', label: 'KN' },
              ].map(({ code, label }) => (
                <button
                  key={code}
                  className={selectedLanguage === code ? 'btn btn-primary' : 'btn btn-ghost'}
                  style={{ fontSize: 11, padding: '6px 10px' }}
                  onClick={() => setSelectedLanguage(code)}
                >
                  {label}
                </button>
              ))}
            </div>

            <div style={{
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              background: 'var(--bg-elevated)',
              padding: 16,
              minHeight: 360,
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}>
              <AnimatePresence initial={false}>
                {conversation.length === 0 ? (
                  <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>
                    Start the call and the transcript will appear here.
                  </div>
                ) : conversation.map((entry) => (
                  <motion.div
                    key={entry.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    style={{
                      alignSelf: entry.role === 'agent' ? 'flex-start' : 'flex-end',
                      maxWidth: '85%',
                      padding: '10px 12px',
                      borderRadius: 16,
                      background: entry.role === 'agent'
                        ? 'color-mix(in srgb, var(--accent) 10%, transparent)'
                        : 'color-mix(in srgb, var(--success) 10%, transparent)',
                      border: `1px solid ${entry.role === 'agent'
                        ? 'color-mix(in srgb, var(--accent) 35%, transparent)'
                        : 'color-mix(in srgb, var(--success) 35%, transparent)'}`,
                    }}
                  >
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                      {entry.role === 'agent' ? 'Agent' : 'Customer'} • {entry.time}
                    </div>
                    <div style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.5 }}>
                      {entry.text}
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>

            <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
              {/* Quick-option tap buttons — variant picks or dessert/beverage upsell */}
              <AnimatePresence>
                {quickOptions.length > 0 && (
                  <motion.div
                    key="quick-options"
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.22 }}
                    style={{
                      width: '100%',
                      display: 'flex',
                      gap: 8,
                      flexWrap: 'wrap',
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-md)',
                      background: 'color-mix(in srgb, var(--accent) 10%, transparent)',
                      border: '1px solid color-mix(in srgb, var(--accent) 30%, transparent)',
                    }}
                  >
                    {quickOptions.map((opt, i) => (
                      <button
                        key={i}
                        className="btn btn-ghost"
                        style={{
                          fontSize: 13,
                          padding: '7px 14px',
                          borderColor: 'color-mix(in srgb, var(--accent) 50%, transparent)',
                          color: 'var(--accent)',
                          fontWeight: 500,
                          flex: quickOptions.length === 2 ? '1' : undefined,
                        }}
                        onClick={() => handleQuickOption(opt.text)}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>

              <VoiceRecorder
                ref={recorderRef}
                onStartRecording={handleInterruptAudio}
                autoListen={callActive && !micPaused}
                onAutoListenSilence={handleAutoListenSilence}
                onAudioChunk={sendAudioChunk}
                onStreamStart={handleStreamStart}
                onStreamEnd={handleStreamEnd}
                onStreamDiscard={handleStreamDiscard}
              />

              <div style={{ display: 'flex', gap: 8, width: '100%' }}>
                <input
                  className="input"
                  value={manualText}
                  onChange={(event) => setManualText(event.target.value)}
                  placeholder="Fallback text input if the caller wants to type instead"
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault()
                      handleManualText()
                    }
                  }}
                />
                <button className="btn btn-ghost" onClick={handleManualText} disabled={!manualText.trim()}>
                  Send
                </button>
              </div>

              {orderPlaced && (
                <motion.div
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: 'var(--radius-md)',
                    background: 'color-mix(in srgb, var(--success) 15%, transparent)',
                    border: '1px solid color-mix(in srgb, var(--success) 40%, transparent)',
                    color: 'var(--success)',
                    fontSize: 14,
                    fontWeight: 500,
                  }}
                >
                  ✓ Order placed! The call will close in a moment.
                </motion.div>
              )}

              {error && (
                <div className="error-bar" style={{ width: '100%' }}>
                  {error}
                </div>
              )}

            </div>
          </div>
        </motion.div>

        <motion.div
          className="card"
          initial={{ opacity: 0, x: 8 }}
          animate={{ opacity: 1, x: 0 }}
        >
          <div className="card-header">Live Order</div>
          <div className="card-body" style={{ display: 'grid', gap: 16 }}>
            {effectiveOrder ? (
              <OrderSummary order={effectiveOrder} />
            ) : (
              <div style={{
                border: '1px dashed var(--border-subtle)',
                borderRadius: 'var(--radius-lg)',
                padding: 18,
                color: 'var(--text-muted)',
                fontSize: 14,
              }}>
                The caller's order will build here as the conversation progresses.
              </div>
            )}

            {result?.transcript && (
              <div style={{
                padding: 12,
                borderRadius: 'var(--radius-md)',
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-subtle)',
              }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
                  Last Transcript
                </div>
                <div style={{ fontSize: 14 }}>{result.transcript}</div>
              </div>
            )}

            {effectiveOrder && (
              <button className="btn btn-primary" onClick={() => void handleConfirmOrder()}>
                Place Order
              </button>
            )}
          </div>
        </motion.div>
      </div>
    </motion.div>
  )
}
