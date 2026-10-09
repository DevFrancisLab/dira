import { useState } from "react";
import { applyCopilotActions, commandActions, describeActions } from "../copilot/actions";
import { currentScenario, currentTier } from "../format";
import { askCopilot } from "../services/api";

const SECTION_LABEL = {
  overview: "Overview",
  map: "Risk Map",
  exposure: "Exposure",
  loss: "Loss Analysis",
  reports: "Reports",
};

export function Copilot({ section, hidden, data, tier, assumption, selected, onNavigate }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [listening, setListening] = useState(false);
  const [busy, setBusy] = useState(false);
  const event = currentTier(data, tier);
  const damage = currentScenario(data, assumption);

  function push(role, text) {
    setMessages((current) => [...current, { role, text }]);
  }

  function chat(raw) {
    const text = raw.trim();
    if (!text || busy) return;
    setDraft("");
    push("user", text);
    const history = messages.map((item) => ({
      role: item.role === "user" ? "user" : "assistant",
      content: item.text,
    }));
    const done = new Set();
    const run = (actions) => {
      const fresh = [];
      for (const action of actions) {
        const key = JSON.stringify(action);
        if (done.has(key)) continue;
        done.add(key);
        fresh.push(action);
      }
      applyCopilotActions(fresh, { onNavigate, hotspots: data.hotspots });
    };
    const local = commandActions(text, data.hotspots);
    run(local);
    if (local.length) push("bot", describeActions(local));
    setBusy(true);
    askCopilot(text, history, tier, assumption, selected && selected.loc_id)
      .then((answer) => {
        run(answer.actions);
        if (!local.length) push("bot", answer.reply);
      })
      .catch((error) => push("bot", error.message || "The language model could not answer."))
      .finally(() => setBusy(false));
  }

  function listen() {
    const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Speech) {
      push("bot", "Voice input is not available in this browser.");
      return;
    }
    const recognition = new Speech();
    recognition.lang = "en-US";
    recognition.onstart = () => setListening(true);
    recognition.onend = () => setListening(false);
    recognition.onerror = () => {
      setListening(false);
      push("bot", "The microphone could not be used.");
    };
    recognition.onresult = (eventResult) => chat(eventResult.results[0][0].transcript);
    recognition.start();
  }

  if (hidden) return null;

  if (!open) {
    return (
      <button type="button" className={section === "map" ? "copilot-toggle on-map" : "copilot-toggle"} onClick={() => setOpen(true)}>
        CAT Copilot
      </button>
    );
  }

  return (
    <section className={section === "map" ? "copilot-panel on-map" : "copilot-panel"} aria-label="CAT Copilot">
      <header className="copilot-head">
        <div>
          <strong>CAT Copilot</strong>
          <p>
            {SECTION_LABEL[section] || "Portfolio"} · {event.assumed_return_period_years}Y · {damage.short_label}
          </p>
        </div>
        <button type="button" className="copilot-hide" onClick={() => setOpen(false)}>
          Hide
        </button>
      </header>
      <div className="transcript">
        {messages.map((message, index) => (
          <p key={index} className={message.role === "user" ? "msg user" : "msg"}>
            {message.text}
          </p>
        ))}
        {busy ? <p className="msg">Thinking...</p> : null}
      </div>
      <form
        className="composer"
        onSubmit={(eventForm) => {
          eventForm.preventDefault();
          chat(draft);
        }}
      >
        <input
          value={draft}
          placeholder="Ask about this risk..."
          aria-label="Ask about this risk"
          disabled={busy}
          onChange={(eventForm) => setDraft(eventForm.target.value)}
        />
        <button type="button" className={listening ? "mic on" : "mic"} onClick={listen} disabled={busy}>
          Mic
        </button>
        <button type="submit" className="send" disabled={busy}>
          Send
        </button>
      </form>
    </section>
  );
}
