const LANGUAGE_MAP = {
  en: 'en-IN',
  hi: 'hi-IN',
  gu: 'gu-IN',
  mr: 'mr-IN',
  kn: 'kn-IN',
}

function decodeBase64Audio(base64Audio) {
  const binary = atob(base64Audio)
  const bytes = new Uint8Array(binary.length)

  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }

  return bytes
}

export function stopBrowserSpeech() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  window.speechSynthesis.cancel()
}

/** Prefer a female voice for the agent (lady) when using browser TTS fallback. */
function getAgentVoice(langTag) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return null
  const voices = window.speechSynthesis.getVoices()
  const want = (langTag || 'en-IN').toLowerCase()
  const female = voices.filter((v) => v.lang.toLowerCase().startsWith(want.split('-')[0]) && v.name.toLowerCase().includes('female'))
  if (female.length > 0) return female[0]
  const byLang = voices.filter((v) => v.lang.toLowerCase().startsWith(want.split('-')[0]))
  return byLang.length > 0 ? byLang[0] : null
}

export function speakWithBrowserTTS(text, language, { onStart, onEnd, onError } = {}) {
  if (typeof window === 'undefined' || !window.speechSynthesis || !text?.trim()) {
    onError?.()
    return false
  }

  stopBrowserSpeech()

  const langTag = LANGUAGE_MAP[language] || LANGUAGE_MAP.en
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = langTag
  const voice = getAgentVoice(langTag)
  if (voice) utterance.voice = voice
  utterance.onstart = () => onStart?.()
  utterance.onend = () => onEnd?.()
  utterance.onerror = () => onError?.()

  window.speechSynthesis.speak(utterance)
  return true
}

export function playAudioWithFallback({
  base64Audio,
  text,
  language,
  currentAudioRef,
  onStart,
  onEnd,
  onError,
}) {
  const finishWithBrowserTTS = () => {
    const spoke = speakWithBrowserTTS(text, language, { onStart, onEnd, onError })
    if (!spoke) onError?.()
  }

  if (!base64Audio) {
    finishWithBrowserTTS()
    return
  }

  try {
    const bytes = decodeBase64Audio(base64Audio)
    const blob = new Blob([bytes], { type: 'audio/mpeg' })
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)
    currentAudioRef.current = audio

    audio.onended = () => {
      URL.revokeObjectURL(url)
      currentAudioRef.current = null
      onEnd?.()
    }

    audio.onerror = () => {
      URL.revokeObjectURL(url)
      currentAudioRef.current = null
      finishWithBrowserTTS()
    }

    onStart?.()
    audio.play().catch(() => {
      URL.revokeObjectURL(url)
      currentAudioRef.current = null
      finishWithBrowserTTS()
    })
  } catch {
    currentAudioRef.current = null
    finishWithBrowserTTS()
  }
}
