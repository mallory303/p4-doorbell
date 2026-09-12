"""Constants for the P4 Doorbell integration."""

DOMAIN = "p4_doorbell"

CONF_P4_HOST = "p4_host"
CONF_CHIME_PLAYERS = "chime_players"
CONF_POPUP_BROWSER = "popup_browser_id"
CONF_NOTIFY_TARGETS = "notify_targets"
CONF_CHIME_NOTIFY = "chime_notify"
CONF_CHIME_VOLUME = "chime_volume"
DEFAULT_CHIME_VOLUME = 60  # percent; previous volume is restored after the chime
CONF_TTS_ENTITY = "tts_entity"
CONF_RESPONDERS = "responders"

DEFAULT_TTS_ENTITY = "tts.elevenlabs"

# Call states
STATE_IDLE = "idle"
STATE_RINGING = "ringing"
STATE_ANSWERED = "answered"
STATE_MODULE = "module_active"  # an automated responder has the call

# HA bus events (for user automations)
EVENT_RING = f"{DOMAIN}_ring"
EVENT_PRESENCE = f"{DOMAIN}_presence"

# chime library (under /config/www -> /local/)
CHIMES_SUBDIR = "p4_doorbell/chimes"
BUNDLED_CHIME_LABEL = "ding-dong (bundled)"
SIGNAL_CHIMES_UPDATED = f"{DOMAIN}_chimes_updated"

DEFAULT_ANNOUNCE_MESSAGE = "Hello! Someone will be with you shortly."
EVENT_ANSWERED = f"{DOMAIN}_answered"
EVENT_ENDED = f"{DOMAIN}_ended"

# Services
SERVICE_ANSWER = "answer"
SERVICE_END_CALL = "end_call"
SERVICE_SIMULATE_RING = "simulate_ring"

# Bundled media, served at /p4_doorbell_static/...
CHIME_URL_PATH = "/p4_doorbell_static/chime.mp3"
CARD_URL_PATH = "/p4_doorbell_static/p4-doorbell-card.js"

AVAILABLE_RESPONDERS = ["manual", "answering_machine", "llm_guest"]
