"""Answering-machine responder (STUB - interface only).

Design (when enabled): if the call stays RINGING for `answer_timeout_s`,
take over the call (state -> module_active), synthesize a canned message via
the configured TTS entity (tts.elevenlabs), fetch the rendered audio, convert
to PCM16 @16 kHz and stream it to the doorbell speaker with POST /api/play
(the endpoint already exists and is HW-verified on the P4).

TODO(module author):
  - tts render: hass.components.tts -> media source -> audio bytes
  - transcode to PCM16 mono @16 kHz (ffmpeg pipe or pymedia)
  - POST bytes to {p4_host}/api/play
  - optionally record the visitor's reply once the P4 mic is wired
"""
from __future__ import annotations

from ..const import STATE_IDLE, STATE_MODULE


class AnsweringMachineResponder:
    name = "answering_machine"

    def __init__(self, hass, entry_data) -> None:
        self.hass = hass
        self.entry_data = entry_data

    async def on_ring(self, call) -> None:
        # stub: not taking calls yet - see module docstring for the plan
        return

    async def on_answered(self, call) -> None:
        return

    async def on_ended(self, call) -> None:
        if call.state == STATE_MODULE:
            call.state = STATE_IDLE
