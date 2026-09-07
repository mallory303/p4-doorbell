/* P4 Doorbell Lovelace card.
 *
 * Video priority:
 *   1. camera_entity (HA camera -> go2rtc WebRTC -> works remotely via Nabu Casa)
 *   2. iframe of the P4's own web UI (LAN only, but carries mic meter,
 *      volume slider, chime button - the full local control surface)
 * Plus call control buttons wired to the p4_doorbell services.
 *
 * config:
 *   type: custom:p4-doorbell-card
 *   camera_entity: camera.p4_doorbell_camera  (optional; preferred when set)
 *   p4_host: http://192.168.86.185            (optional iframe fallback)
 *   fullscreen: true|false                    (optional; fills the popup)
 */
class P4DoorbellCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._host = (this._config.p4_host || "").replace(/\/$/, "");
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const cam = this._camEl;
    if (cam) {
      cam.hass = hass;
      cam.stateObj = hass.states[this._config.camera_entity];
    }
  }

  _render() {
    if (this.shadowRoot) return;
    const useCam = !!this._config.camera_entity;
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { overflow: hidden; }
        .wrap { display: flex; flex-direction: column; height: 100%; }
        .video, .cam { flex: 1; min-height: 320px; width: 100%; background: #000; border: 0; }
        .cam { display: block; }
        .bar { display: flex; gap: 8px; padding: 8px; }
        button {
          flex: 1; padding: 14px; font-size: 16px; border: 0; border-radius: 8px;
          cursor: pointer; color: #fff;
        }
        .answer { background: #2e7d32; }
        .end { background: #c62828; }
        .fullscreen { position: fixed; inset: 0; z-index: 10; background: #000; }
      </style>
      <ha-card class="${this._config.fullscreen ? "fullscreen" : ""}">
        <div class="wrap">
          ${useCam
            ? `<div class="cam" id="camhost"></div>`
            : `<iframe class="video" src="${this._host}/" allow="autoplay; microphone"></iframe>`}
          <div class="bar">
            <button class="answer" id="answer">&#128222; Answer</button>
            <button class="end" id="end">End call</button>
          </div>
        </div>
      </ha-card>`;
    if (useCam) {
      const el = document.createElement("ha-camera-stream");
      el.style.width = "100%";
      el.style.height = "100%";
      el.controls = true;
      el.muted = true;
      if (this._hass) {
        el.hass = this._hass;
        el.stateObj = this._hass.states[this._config.camera_entity];
      }
      root.getElementById("camhost").appendChild(el);
      this._camEl = el;
    }
    root.getElementById("answer").addEventListener("click", () => {
      this._hass.callService("p4_doorbell", "answer", {});
      // future: browser mic -> /ws-audio talk-back starts here
    });
    root.getElementById("end").addEventListener("click", () => {
      this._hass.callService("p4_doorbell", "end_call", {});
    });
  }

  getCardSize() {
    return this._config.fullscreen ? 12 : 6;
  }

  static getStubConfig() {
    return { p4_host: "http://192.168.86.185" };
  }
}

customElements.define("p4-doorbell-card", P4DoorbellCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "p4-doorbell-card",
  name: "P4 Doorbell",
  description: "ESP32-P4 doorbell: live camera (WebRTC) + call controls",
});
