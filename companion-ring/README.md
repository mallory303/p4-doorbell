# companion-ring — Ring the HA Companion app (Lenovo Smart Display)

Companion folder to the P4 Doorbell integration: makes a **Lenovo Smart Display
(CD-18781 "StarView", custom Android)** ring / speak when the doorbell is pressed,
using only a Home Assistant automation — no custom integration code.

## The original problem

> "Home Assistant is unable to push a media to a companion app."

Half true. What HA genuinely **cannot** do on this device:

- Upload/play an **arbitrary audio file** on the device — notification sounds must
  live on the phone (Android restriction, not HA).
- Use the companion app's `media_player` entity as a playback target — on the
  Lenovo it is only a **remote control** for media sessions already playing on the
  device (`supported_features` = play/pause/stop/next/prev/select_source; no
  `play_media`, no `volume_set`). `media_player.play_media` → `400 Bad Request`.
- Deliver pushes at all if FCM (Google Play services) is missing/broken on the
  custom ROM.

What it **can** do — and what this folder implements — is the TTS channel:

```
notify.mobile_app_<device>  with  message: TTS  +  media_stream: alarm_stream
```

The companion app speaks the text at **alarm volume**, even in silent/DND mode.

## Root causes found while debugging (2026-10-22)

1. **Wrong service name → silent failure.**
   `notify.lenovo_starview` does **not** exist as a service; calling it returns a
   bare `400 Bad Request`. The correct service is `notify.mobile_app_lenovo_starview`
   (entities are named `notify.lenovo_starview`, but legacy services keep the
   `mobile_app_` prefix). An automation using the short name fails at HA itself —
   nothing ever leaves the server. This is what made the feature look impossible.
2. **DHCP drift.** The HA host moved from `192.168.86.62` to `192.168.86.171`.
   Any absolute internal URL pointing at the old IP is dead. Fix: DHCP reservation
   for the Pi's MAC in the router.
3. **Companion media player is not a speaker.** See above.

## Files

| Path | Purpose |
|---|---|
| `automations/doorbell_ring.yaml` | Doorbell trigger → TTS ring at alarm volume (+ optional ringtone channel, camera snapshot, iOS critical alert) |
| `scripts/doorbell_test.sh` | Fire a test ring from any shell (uses `HASS_URL`/`HASS_TOKEN`) |
| `sounds/doorbell.wav` | Generated ding-dong (E5→C5) for devices that *can* play files (cast targets etc.) |

## Setup

1. **Companion app on the Lenovo** must be logged in and registered
   (Settings → Companion App shows `Lenovo StarView`). FCM must work for push
   delivery — on a custom ROM, verify the device gets *any* HA notification first
   (run `scripts/doorbell_test.sh`).
2. **Import the automation:** copy `automations/doorbell_ring.yaml` into your
   `automations.yaml` (or via UI), then adjust:
   - the trigger — wire it to the P4 doorbell ring event
     (`event.p4_doorbell_ring`, or `p4_doorbell.simulate_ring` for testing)
   - `notify.mobile_app_lenovo_starview` → your device's notify service
3. **Optional — real ringtone instead of speech:** send one notification with
   `channel: doorbell` + `importance: high`, then on the device set that channel's
   sound in Android settings (one-time). Uncomment the block in the automation.
4. **iOS variant** (critical alert, plays in silent/DND) is included, commented.

## Verifying delivery

```bash
export HASS_URL=http://192.168.86.171:8123
export HASS_TOKEN=<long-lived-token>
./scripts/doorbell_test.sh
```

Expected: the display immediately says *"Ding dong. Someone is at the front door."*
at alarm volume. HTTP 200 means HA accepted the push; silence on the device after
a 200 means FCM delivery is broken on the ROM — fix that first (re-register the
app, check microG/Play services).

## References

- [HA Companion — Android notifications](https://companion.home-assistant.io/docs/notifications/notifications-basic)
- [HA Companion — notification TTS](https://companion.home-assistant.io/docs/notifications/notification-tts)
- [HA Companion — critical notifications (iOS)](https://companion.home-assistant.io/docs/notifications/critical-notificationss)
