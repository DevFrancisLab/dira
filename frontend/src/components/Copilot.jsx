import { useRef, useState } from "react";
import { applyCopilotActions, commandActions, describeActions, isRiskBrief } from "../copilot/actions";
import { sampleIngest } from "../copilot/sample";
import { currentScenario, currentTier } from "../format";
import { askCopilot, downloadRiskReport, ingestDocument } from "../services/api";

const ACCEPT = ".csv,.xls,.xlsx,.pdf,.png,.jpg,.jpeg,.webp,.gif";

const SECTION_LABEL = {
  overview: "Overview",
  map: "Risk Map",
  exposure: "Exposure",
  loss: "Loss Analysis",
  reports: "Reports",
};

export function Copilot({ section, hidden, data, tier, assumption, selected, onNavigate, onIngested }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [listening, setListening] = useState(false);
  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState("Thinking...");
  const fileRef = useRef(null);
  const event = currentTier(data, tier);
  const damage = currentScenario(data, assumption);

  function push(role, text, review) {
    setMessages((current) => [...current, { role, text, review: review || null }]);
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
    const local = isRiskBrief(text) ? [] : commandActions(text, data.hotspots);
    run(local);
    if (local.length) {
      push("bot", describeActions(local));
      return;
    }
    setBusyLabel("Thinking...");
    setBusy(true);
    askCopilot(text, history, tier, assumption, selected && selected.loc_id)
      .then((answer) => {
        run(answer.actions);
        if (!local.length) push("bot", answer.reply, answer.review);
      })
      .catch((error) => push("bot", error.message || "The language model could not answer."))
      .finally(() => setBusy(false));
  }

  function settleReview(index, state) {
    setMessages((current) =>
      current.map((item, itemIndex) =>
        itemIndex === index && item.review ? { ...item, review: { ...item.review, state } } : item,
      ),
    );
  }

  function approveReport(index, review) {
    if (busy) return;
    setBusyLabel("Preparing the PDF...");
    setBusy(true);
    downloadRiskReport(review)
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "dira-extreme-risk-report.pdf";
        link.click();
        URL.revokeObjectURL(url);
        settleReview(index, "approved");
        push("bot", "PDF downloaded. Open dira-extreme-risk-report.pdf.");
      })
      .catch((error) => push("bot", error.message || "The PDF could not be created."))
      .finally(() => setBusy(false));
  }

  function upload(eventForm) {
    const file = eventForm.target.files && eventForm.target.files[0];
    eventForm.target.value = "";
    if (!file || busy) return;
    push("user", `Uploaded ${file.name}`);
    setBusyLabel("Reading the document...");
    setBusy(true);
    ingestDocument(file)
      .then((result) => {
        push("bot", result.summary || "The document was read.");
        if (onIngested) onIngested(result);
      })
      .catch((error) => {
        if (error.status === 401) {
          push("bot", error.message || "Authentication required.");
          return;
        }
        const sample = sampleIngest(file.name);
        push("bot", sample.summary);
        if (onIngested) onIngested(sample);
      })
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
          <div key={index} className={message.role === "user" ? "msg user" : "msg"}>
            <p>{message.text}</p>
            {message.review && !message.review.state ? (
              <div className="review-actions">
                <p>{message.review.detail}</p>
                <button type="button" onClick={() => approveReport(index, message.review)} disabled={busy}>
                  Approve and download
                </button>
                <button
                  type="button"
                  onClick={() => {
                    settleReview(index, "rejected");
                    push("bot", "Report left unapproved. No PDF was created.");
                  }}
                  disabled={busy}
                >
                  Reject
                </button>
              </div>
            ) : null}
          </div>
        ))}
        {busy ? <p className="msg">{busyLabel}</p> : null}
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
        <button type="button" className="mic" onClick={() => fileRef.current && fileRef.current.click()} disabled={busy}>
          Upload
        </button>
        <input ref={fileRef} type="file" accept={ACCEPT} hidden onChange={upload} />
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
