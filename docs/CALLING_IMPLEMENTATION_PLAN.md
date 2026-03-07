# Calling Implementation Plan

Date: 2026-03-07

## Objective

Turn the existing voice-ordering stack into a production-ready calling experience with two tracks:

1. Preferred track: browser-based calling with no carrier billing.
2. Optional track: PSTN inbound calling for real phone numbers.

The current recommendation is to ship browser calling first and treat PSTN inbound as phase two.

## Current Stack

- Frontend already has live microphone capture and WebSocket audio streaming.
- Backend already has STT, intent mapping, order building, session state, TTS, and a live `/api/voice/stream` route.
- The lowest-risk path is to reuse this stack and wrap it in a call-oriented UI instead of buying telephony first.

## Recommendation

### Best immediate option: Web-based calling

Use the browser as the call endpoint:

- Customer opens a call page.
- Browser microphone streams audio to the existing FastAPI WebSocket route.
- Backend runs STT -> voice pipeline -> TTS.
- Agent audio is played back in the browser.
- No PSTN carrier, DID, SIP, or per-minute phone billing is required.

Why this is the best first implementation:

- Reuses the existing production logic.
- Lowest cost.
- Fastest to ship.
- Easy to test internally.
- Avoids telephony compliance and carrier onboarding until the product is stable.

### PSTN inbound calling

Use this only after the web-call flow is stable.

Why:

- PSTN adds recurring cost, phone-number management, SIP setup, and call routing complexity.
- You only need it when customers must call from a regular phone.

## Cost Reality

### Twilio

Twilio inbound voice is not free in production. Official pricing pages show per-minute inbound pricing plus monthly number charges.

Sources:

- https://www.twilio.com/en-us/voice/pricing/cu
- https://www.twilio.com/docs/voice/pricing

### LiveKit

LiveKit has limited free quotas on the Build plan, including free monthly agent session minutes and free monthly SIP minutes, but this is not “free inbound calling forever” for production scale.

Sources:

- https://livekit.io/pricing
- https://docs.livekit.io/deploy/admin/quotas-and-limits/

### Daily

Daily is a strong managed WebRTC option for browser-based calling and includes free monthly WebRTC minutes, but it does not remove PSTN cost if you later need actual phone calls.

Source:

- https://www.daily.co/pricing/webrtc-infrastructure/

## Decision

### Default path

Ship browser-based calling first on the existing stack.

### PSTN path

If inbound phone numbers become necessary, prefer LiveKit SIP before Twilio for early testing because the free quotas are more useful for experimentation. For higher-volume or production-grade telephony routing, compare LiveKit SIP against Twilio Elastic SIP Trunking or Programmable Voice.

## Browser Calling Architecture

### Frontend

- Dedicated `WebCall` page.
- Start call / end call controls.
- Live transcript timeline with `agent` and `customer` roles.
- Auto-listen restart after TTS playback.
- Silence follow-up prompts.
- Manual text fallback.
- Live order summary and confirm action.

### Backend

- Reuse `/api/voice/stream` for audio streaming.
- Reuse `pipeline.process_audio()` for turn handling.
- Reuse `tts_orchestrator.get_audio_response()` for spoken responses.
- Keep `session_id` stable for the entire call.

### Audio Flow

1. Browser call starts.
2. Agent greeting is played.
3. Recorder captures caller speech.
4. Audio chunks stream over WebSocket.
5. Backend transcribes and processes the turn.
6. Backend streams TTS audio back.
7. Browser plays agent reply.
8. Auto-listen restarts.

## Production Readiness Tasks For Web Calling

### Backend

- Add structured metrics for STT, pipeline, TTS, and total turn time.
- Add server-side call session model if calls need analytics beyond order sessions.
- Add rate limiting specific to live voice streams.
- Add call audit logs for transcripts and outcomes.
- Add graceful reconnect handling for WebSocket drops.
- Add feature flags for web-call mode.

### Frontend

- Add retry and reconnect UX.
- Add device selection for microphone/output.
- Add explicit mute / hold states.
- Add call-quality indicator.
- Add transcript export for support operations.
- Add customer identity capture if calls are linked to CRM or table reservations.

### Observability

- Track call start, call end, order placed, mute toggles, silence prompts, and reconnects.
- Log language selection and final detected language.
- Alert on TTS failure rate and WebSocket error rate.

### Security

- Require authenticated sessions for internal restaurant users.
- Validate restaurant scope for every call.
- Limit max session length.
- Sanitize and redact sensitive transcript content in logs if needed.

## PSTN Inbound Calling Plan

### Option A: LiveKit SIP

Use when you want a phone number and you still want the browser / real-time agent stack to stay close to WebRTC.

Flow:

1. Customer dials a LiveKit-backed number.
2. SIP ingress routes the call into a LiveKit room.
3. A bridge service pipes room audio to the existing order agent.
4. Agent audio is sent back into the room.
5. Order results are stored the same way as web calls.

Implementation tasks:

- Provision SIP inbound number.
- Create call-room allocation service.
- Build media bridge between LiveKit room audio and agent backend.
- Add call metadata model for phone number, call SID, duration, and order result.
- Add failover when model or TTS is unavailable.

### Option B: Twilio inbound voice

Use when you need broad PSTN coverage, strong telecom tooling, or existing Twilio usage.

Flow:

1. Customer dials Twilio number.
2. Twilio webhook starts a call session.
3. Twilio Media Streams forwards audio over WebSocket.
4. Bridge service converts Twilio stream frames to the internal agent audio format.
5. Agent reply is streamed back to Twilio for playback.

Implementation tasks:

- Provision Twilio number.
- Build Twilio webhook handlers.
- Build Media Streams bridge service.
- Handle Twilio call lifecycle events and billing-safe timeout limits.
- Add DTMF fallback for confirmations if needed.

## Why Browser Calling Still Wins First

- Zero carrier billing for internal pilots.
- No phone-number setup.
- No SIP bridging work.
- No telephony vendor lock-in.
- Easiest path to fast iteration on latency, agent behavior, and ordering accuracy.

## Rollout Plan

### Phase 1

- Ship browser calling inside the dashboard.
- Use internal staff and test customers.
- Tune latency, silence prompts, TTS, and order accuracy.

### Phase 2

- Add call analytics and dashboards.
- Add reconnect handling and call recording policy.
- Add customer profile capture.

### Phase 3

- Add PSTN inbound calling if business needs justify the cost.
- Start with limited pilot traffic and call caps.

## Implementation Status In `testing`

The `testing` branch should contain:

- TTS fix for live WebSocket turns.
- Dedicated browser-call page.
- Routing and navigation for web calling.

Next recommended coding tasks after this branch:

1. Persist call transcripts and outcomes in the backend.
2. Add reconnect-safe call session handling.
3. Add microphone device selection and audio output selection.
4. Add telephony bridge only after the web flow is validated.
