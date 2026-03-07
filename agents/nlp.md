# Upgrading Petpooja Voice Agent to Gemini-Level Experience

---

## The Core Problem: Batch vs. Stream

Your current flow is:

```
Record → Stop → Upload → Whisper → NLP → TTS → Play
```

Gemini's flow is:

```
Audio chunks stream in real-time → LLM processes as you speak →
TTS starts before you finish → Barge-in interrupts anytime
```

That's the entire difference in "feel."

---

## 1. Replace Batch Recording with WebSocket Streaming

**Current:** User presses record, stops, uploads full audio file.

**What to build:**

```python
# backend: new websocket endpoint
@app.websocket("/api/voice/stream")
async def voice_stream(websocket: WebSocket):
    await websocket.accept()
    audio_buffer = AudioBuffer()

    async for chunk in websocket.iter_bytes():
        audio_buffer.append(chunk)

        # VAD: detect if user paused (300ms silence)
        if voice_activity_detector.is_end_of_utterance(audio_buffer):
            transcript = await whisper.transcribe_stream(audio_buffer.flush())
            response = await pipeline.process(transcript)

            # Stream TTS back chunk by chunk
            async for audio_chunk in tts.stream(response.text):
                await websocket.send_bytes(audio_chunk)
```

```javascript
// frontend: replace file upload with WebSocket
const ws = new WebSocket('ws://localhost:8000/api/voice/stream');
const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

mediaRecorder.ondataavailable = (e) => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(e.data); // send chunks every 250ms
  }
};

// timeslice = send chunk every 250ms, don't wait for stop
mediaRecorder.start(250);
```

---

## 2. Add Barge-In (Interruption Handling)

This is what makes Gemini feel alive. The user can speak *while* the AI is talking.

```javascript
// frontend
class VoiceSession {
  constructor() {
    this.currentAudio = null;
    this.isAISpeaking = false;
  }

  onUserSpeechDetected() {
    if (this.isAISpeaking) {
      // interrupt immediately
      this.currentAudio.pause();
      this.currentAudio = null;
      this.isAISpeaking = false;
      this.ws.send(JSON.stringify({ type: 'interrupt' }));
    }
  }
}
```

```python
# backend: handle interrupt signal
async def handle_message(websocket, message):
    if message.get('type') == 'interrupt':
        # cancel any in-progress TTS generation
        await tts_task.cancel()
        await pipeline.reset_turn()
```

---

## 3. Swap Whisper Batch for a Streaming-Friendly STT

Local Whisper is great for accuracy but terrible for latency. Options:

| Option | Latency | Cost | Notes |
|---|---|---|---|
| `whisper-live` (open source) | ~300ms | Free | Drop-in for your stack |
| Deepgram Nova-2 | ~150ms | ~$0.0043/min | Best for demo wow-factor |
| Google STT Streaming | ~200ms | Low | Familiar API |
| `faster-whisper` streaming | ~400ms | Free | Easiest migration |

For a hackathon, **Deepgram** gives you the best demo wow-factor with minimal code:

```python
from deepgram import Deepgram

dg = Deepgram(DEEPGRAM_API_KEY)

async def stream_transcribe(audio_stream):
    connection = await dg.transcription.live({
        'language': 'hi',  # supports Hinglish
        'model': 'nova-2',
        'interim_results': True,  # show words as they're spoken
    })

    connection.registerHandler('transcript', lambda t:
        pipeline.process_partial(t['channel']['alternatives'][0]['transcript'])
    )
```

---

## 4. Add Interim / Partial Transcripts to UI

This is the visual element that makes it *feel* like Gemini — text appearing as you speak.

```javascript
// Show partial transcript in real-time
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'partial_transcript') {
    // show greyed-out text while user is still speaking
    setTranscript({ text: data.text, isFinal: false });
  }

  if (data.type === 'final_transcript') {
    setTranscript({ text: data.text, isFinal: true });
  }

  if (data.type === 'ai_response_chunk') {
    // stream AI text response token by token
    setAiResponse(prev => prev + data.token);
  }
};
```

---

## 5. Replace Parler TTS with a Lower-Latency Option

Parler is high quality but slow to start. For Gemini-like responsiveness you need **first-chunk latency under 500ms**.

```python
# Option A: ElevenLabs streaming (best quality)
import elevenlabs
elevenlabs.set_api_key(key)

async def stream_tts(text):
    async for chunk in elevenlabs.generate_stream(
        text=text,
        voice="Rachel",
        stream=True
    ):
        yield chunk  # send to websocket as it generates

# Option B: Coqui XTTS locally (free, decent latency)
# Option C: OpenAI TTS with streaming (good balance)
```

---

## 6. Add LLM as the Brain (The Real Gemini Difference)

Your current NLP is rule-based FAISS + intent classification. Gemini uses an LLM for *everything*. This is the biggest upgrade:

```python
# Replace your intent classifier + item matcher with a single LLM call
SYSTEM_PROMPT = """
You are a restaurant voice ordering assistant for {restaurant_name}.
Current menu: {menu_json}
Current cart: {cart_json}

Extract orders, modifications, and confirmations.
Always respond in the same language the customer uses.
Be conversational, suggest combos, upsell naturally.

Respond ONLY in JSON:
{
  "intent": "ORDER|MODIFY|CANCEL|CONFIRM|QUERY",
  "items": [{"name": str, "qty": int, "modifiers": []}],
  "cart_action": "add|remove|replace|clear",
  "tts_response": "what to say back to customer",
  "upsell": "optional upsell suggestion or null"
}
"""

async def llm_process(transcript, cart, menu):
    response = await openai.chat.completions.create(
        model="gpt-4o-mini",  # fast + cheap
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(...)},
            {"role": "user", "content": transcript}
        ],
        response_format={"type": "json_object"},
        stream=True  # stream the JSON back
    )
```

`gpt-4o-mini` costs almost nothing and handles Hinglish, ambiguity, and context natively — replacing hundreds of lines of your existing NLP code.

---

## Priority Order for Hackathon

Given time constraints, do these in order:

| Priority | Change | Effort | Impact |
|---|---|---|---|
| 1 | WebSocket streaming + VAD | ~1 day | Biggest perceived improvement |
| 2 | LLM brain (gpt-4o-mini) | ~4 hours | Kills NLP complexity, improves accuracy |
| 3 | Partial transcripts in UI | ~2 hours | Pure frontend, looks incredible |
| 4 | Barge-in interruption | ~4 hours | Impressive but tricky, do if time permits |
| 5 | Streaming TTS swap | ~2 hours | Polish layer, do last |

The **WebSocket + LLM combo** alone will make your voice agent feel like a completely different product to judges.

---

## Architecture: Before vs After

### Before
```
[User holds button] → [Full audio file] → [Whisper batch] → 
[FAISS match] → [Rule-based intent] → [Parler TTS batch] → [Play]

Total latency: 3–6 seconds
```

### After
```
[User speaks] → [250ms audio chunks via WebSocket] → 
[Streaming STT (partial results)] → [LLM processes in parallel] → 
[TTS first chunk streams back] → [Audio plays while LLM still generating]

Total latency: 0.8–1.5 seconds
```

---