import { useState } from 'react'
import { submitTextOrder, submitVoiceOrder } from '../api/client'
import VoiceRecorder from '../components/VoiceRecorder'
import OrderSummary from '../components/OrderSummary'
import KOTTicket from '../components/KOTTicket'

export default function VoiceOrder() {
  const [result, setResult] = useState(null)
  const [textInput, setTextInput] = useState('')
  const [loading, setLoading] = useState(false)

  const handleTextOrder = async () => {
    if (!textInput.trim()) return
    setLoading(true)
    try {
      const data = await submitTextOrder(textInput)
      setResult(data)
    } catch (err) {
      console.error('Order failed:', err)
    }
    setLoading(false)
  }

  const handleAudioRecorded = async (audioBlob) => {
    setLoading(true)
    try {
      const data = await submitVoiceOrder(audioBlob)
      setResult(data)
    } catch (err) {
      console.error('Voice order failed:', err)
    }
    setLoading(false)
  }

  return (
    <div>
      <div className="page-header">
        <h1>Voice Order</h1>
        <p>Speak or type an order in English, Hindi, or Hinglish</p>
      </div>

      <div className="grid-2" style={{ marginBottom: 24 }}>
        {/* Voice Input */}
        <div className="card">
          <div className="card-header">🎙️ Voice Input</div>
          <div className="card-body" style={{ textAlign: 'center', padding: 32 }}>
            <VoiceRecorder onRecorded={handleAudioRecorded} />
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 12 }}>
              Click to record, click again to stop
            </p>
          </div>
        </div>

        {/* Text Input */}
        <div className="card">
          <div className="card-header">⌨️ Text Input</div>
          <div className="card-body">
            <textarea
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              placeholder="e.g. ek paneer tikka aur do butter naan, extra spicy"
              style={{
                width: '100%',
                height: 80,
                padding: 12,
                background: 'var(--surface2)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text)',
                fontFamily: 'var(--font)',
                fontSize: 13,
                resize: 'vertical',
              }}
            />
            <button
              className="btn btn-primary"
              onClick={handleTextOrder}
              disabled={loading || !textInput.trim()}
              style={{ marginTop: 12, width: '100%' }}
            >
              {loading ? 'Processing...' : 'Process Order'}
            </button>
          </div>
        </div>
      </div>

      {/* Results */}
      {result && (
        <>
          {/* Parsed info */}
          {result.raw_text && (
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-header">📝 Parsed Input</div>
              <div className="card-body">
                <div style={{ marginBottom: 8 }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>Raw text: </span>
                  <span style={{ fontSize: 13 }}>{result.raw_text}</span>
                </div>
                <div style={{ marginBottom: 8 }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>Normalized: </span>
                  <span style={{ fontSize: 13 }}>{result.normalized_text}</span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>Intent: </span>
                  <span className={`tag tag-${result.intent === 'order' ? 'star' : 'puzzle'}`}>
                    {result.intent}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Errors */}
          {result.errors?.length > 0 && (
            <div className="card" style={{ marginBottom: 16, borderColor: 'var(--red)' }}>
              <div className="card-body">
                {result.errors.map((err, i) => (
                  <p key={i} style={{ color: 'var(--red)', fontSize: 13 }}>⚠️ {err}</p>
                ))}
              </div>
            </div>
          )}

          <div className="grid-2">
            {/* Order Summary */}
            {result.order && <OrderSummary order={result.order} />}

            {/* KOT Ticket */}
            {result.kot && <KOTTicket kot={result.kot} />}
          </div>

          {/* Upsell suggestions */}
          {result.upsells?.length > 0 && (
            <div className="card" style={{ marginTop: 16 }}>
              <div className="card-header">⬆️ Upsell Suggestions</div>
              <div className="card-body">
                {result.upsells.map(u => (
                  <div key={u.item_id} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                    <span style={{ fontSize: 13 }}>{u.suggestion_text}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>
                      (margin: {u.margin_pct}%)
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
