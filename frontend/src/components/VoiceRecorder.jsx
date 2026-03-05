import { useState, useRef } from 'react'

export default function VoiceRecorder({ onRecorded }) {
  const [recording, setRecording] = useState(false)
  const mediaRecorder = useRef(null)
  const chunks = useRef([])

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mediaRecorder.current = recorder
      chunks.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data)
      }

      recorder.onstop = () => {
        const blob = new Blob(chunks.current, { type: 'audio/webm' })
        stream.getTracks().forEach(t => t.stop())
        if (onRecorded) onRecorded(blob)
      }

      recorder.start()
      setRecording(true)
    } catch (err) {
      console.error('Mic access failed:', err)
      alert('Microphone access denied. Please allow microphone access.')
    }
  }

  const stopRecording = () => {
    if (mediaRecorder.current && mediaRecorder.current.state === 'recording') {
      mediaRecorder.current.stop()
    }
    setRecording(false)
  }

  return (
    <button
      onClick={recording ? stopRecording : startRecording}
      style={{
        width: 80,
        height: 80,
        borderRadius: '50%',
        border: 'none',
        background: recording
          ? 'linear-gradient(135deg, #f87171, #ef4444)'
          : 'linear-gradient(135deg, var(--orange), #e55a28)',
        color: 'white',
        fontSize: 28,
        cursor: 'pointer',
        boxShadow: recording
          ? '0 0 0 8px rgba(248,113,113,0.2), 0 0 24px rgba(248,113,113,0.3)'
          : '0 0 0 4px rgba(255,107,53,0.15)',
        transition: 'all 0.2s',
        animation: recording ? 'pulse 1.5s ease-in-out infinite' : 'none',
      }}
    >
      {recording ? '⏹' : '🎤'}

      <style>{`
        @keyframes pulse {
          0%, 100% { box-shadow: 0 0 0 8px rgba(248,113,113,0.2); }
          50% { box-shadow: 0 0 0 16px rgba(248,113,113,0.1), 0 0 32px rgba(248,113,113,0.2); }
        }
      `}</style>
    </button>
  )
}
