"""LLM guest responder (STUB - interface only).

Design (when enabled): active when the ring goes unanswered and nobody is
home (presence/person entities decide). Pipelines visitor speech (P4 mic ->
/ws-audio, planned) into an LLM conversation (HA Assist / conversation agent)
and speaks replies through the doorbell speaker (/api/play). Shares the
call-takeover mechanics with answering_machine; the difference is a
multi-turn conversation loop instead of a single canned message.
"""
from __future__ import annotations


class LlmGuestResponder:
    name = "llm_guest"

    def __init__(self, hass, entry_data) -> None:
        self.hass = hass
        self.entry_data = entry_data

    async def on_ring(self, call) -> None:
        return

    async def on_answered(self, call) -> None:
        return

    async def on_ended(self, call) -> None:
        return
