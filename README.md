# P4 Doorbell — Home Assistant integration

Custom integration for the ESP32-P4 H.264 doorbell
([firmware](https://github.com/mallory303/olimex-p4-h264-cam)).

## What it does

- **Live camera entity** (`camera.p4_doorbell_camera`): the P4 serves RTSP
  (`rtsp://<doorbell>:554/live`, H.264 passthrough, zero transcode); HA routes
  it through go2rtc → **WebRTC — works remotely via Nabu Casa**. The popup card
  uses this automatically (iframe fallback on LAN).
- Receives **ring** (button) and **presence** (mmWave radar) events from the
  doorbell via an auto-registered HTTP webhook
- **Modular responder pipeline** — modules decide what happens on a ring, in
  configurable priority order:
  - `manual` — chimes the house on your media_players, pops a fullscreen
    doorbell UI on the wall tablet (browser_mod), answers/ends the call
  - `answering_machine` — *(stub)* canned TTS message (ElevenLabs) to the
    doorbell speaker when unanswered
  - `llm_guest` — *(stub)* LLM conversation with the visitor when nobody is home
- Entities: ring **event** (device class doorbell), **presence** sensor,
  **test chime** button, **speaker volume** slider (NVS-persisted on the P4)
- Services: `p4_doorbell.answer`, `p4_doorbell.end_call`,
  `p4_doorbell.simulate_ring`
- Lovelace card `p4-doorbell-card`: embeds the doorbell's own live UI
  (camera + mic meter + controls) plus Answer / End-call buttons

## Install (HACS)

1. HACS → ⋮ → **Custom repositories** → add
   `https://github.com/mallory303/p4-doorbell` (category: **Integration**)
2. Install **P4 Doorbell**, restart Home Assistant
3. Settings → Devices & Services → **Add Integration** → "P4 Doorbell"
   - doorbell URL (default `http://192.168.86.185`), chime players,
     tablet `browser_id`, TTS entity, responder modules
4. For the tablet popup: install **browser_mod** (HACS) and note the tablet's
   browserID (it appears as a browser_mod entity on the tablet's dashboard).

## Wiring the doorbell to HA

The integration registers a webhook; the P4 firmware POSTs to it on ring:

```
POST http://<ha-host>:8123/api/webhook/p4_doorbell_<entry_id>
{"event": "ring", "source": "button"}
```

The exact webhook ID is logged at integration startup (and shown below in
Developer tools → once fired). Test the whole HA side right now, no firmware
needed — either run service `p4_doorbell.simulate_ring`, or:

```
curl -X POST http://<ha-host>:8123/api/webhook/<webhook_id> \
     -H 'Content-Type: application/json' -d '{"event":"ring"}'
```

Firmware-side auto-POST on button press is a planned firmware milestone
(along with `/ws-audio` two-way audio and `/api/snap.jpg` snapshots).

## Roadmap

- [ ] firmware: POST ring events to the HA webhook from `doorbell.c`
- [ ] answering_machine: TTS render → PCM16@16k → `POST /api/play`
- [ ] `/ws-audio`: browser mic → doorbell speaker (talk-back), doorbell mic → browser
- [ ] llm_guest: multi-turn conversation via HA conversation agent
- [ ] snapshot in notifications once `/api/snap.jpg` lands
