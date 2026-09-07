/* P4 Doorbell Lovelace card.
 *
 * Shows the P4's own web UI (live H.264 camera, mic meter, volume, chime)
 * in an iframe - zero firmware duplication - plus call control buttons that
 * call the p4_doorbell services. Use with browser_mod popup (fullscreen)
 * or as a normal dashboard card.
 *
 * config:
 *   type: custom:p4-doorbell-card
 *   p4_host: http://192.168.86.185   (optional; default below)
 *   fullscreen: true|false           (optional; fills the popup)
 */
class P4DoorbellCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._host = (this._config.p4_host || "http://192.168.86.185").replace(/\/$/, "");
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
  }

  _render() {
    if (this.shadowRoot) return;
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { overflow: hidden; }
        .wrap { display: flex; flex-direction: column; height: 100%; }
        .video { flex: 1; min-height: 320px; border: 0; width: 100%; background: #000; }
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
          <iframe class="video" src="${this._host}/" allow="autoplay; microphone"></iframe>
          <div class="bar">
            <button class="answer" id="answer">&#128222; Answer</button>
            <button class="end" id="end">End call</button>
          </div>
        </div>
      </ha-card>`;
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
  description: "ESP32-P4 doorbell: live camera/mic UI + call controls",
});
