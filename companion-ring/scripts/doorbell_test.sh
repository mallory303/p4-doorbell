#!/usr/bin/env bash
# Fire a test ring at the Lenovo display.
#   export HASS_URL=http://192.168.86.171:8123
#   export HASS_TOKEN=<long-lived-access-token>
#   ./doorbell_test.sh
set -euo pipefail

: "${HASS_URL:?set HASS_URL}" "${HASS_TOKEN:?set HASS_TOKEN}"
SERVICE="${NOTIFY_SERVICE:-mobile_app_lenovo_starview}"

curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST \
  -H "Authorization: Bearer ${HASS_TOKEN}" \
  -H "Content-Type: application/json" \
  "${HASS_URL}/api/services/notify/${SERVICE}" \
  -d '{
    "title": "Doorbell",
    "message": "TTS",
    "data": {
      "tts_text": "Ding dong. Someone is at the front door.",
      "media_stream": "alarm_stream"
    }
  }'

echo "HTTP 200 = HA accepted the push. No sound on the device = FCM delivery broken."
echo "A 400 here usually means the service name is wrong — list valid names with:"
echo "  curl -s -H \"Authorization: Bearer \$HASS_TOKEN\" \$HASS_URL/api/services | jq '.[] | select(.domain==\"notify\") | .services | keys'"
