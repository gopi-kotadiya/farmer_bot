import { useCallback, useEffect, useRef, useState } from "react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";
const CHAT_TIMEOUT_MS = 360_000;

function stripGraphFileLine(text) {
  return String(text || "").replace(/\n?GRAPH_FILE=[^\n\r]+/g, "").trim();
}

function sessionKey() {
  const k = "kisanbot_session_id";
  let id = localStorage.getItem(k);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(k, id);
  }
  return id;
}

/**
 * Avoid empty-body + JSON.parse failures (common when proxy times out during long LLM calls).
 */
async function postJson(path, payload, { timeoutMs = CHAT_TIMEOUT_MS } = {}) {
  const url = `${API_BASE}${path}`;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    });
    const raw = await res.text();
    if (!raw || !raw.trim()) {
      return {
        ok: false,
        message: `Empty response (HTTP ${res.status}). Start backend: uv run python main.py api — and use npm run dev with proxy, or set VITE_API_BASE=http://127.0.0.1:8000`,
      };
    }
    let data;
    try {
      data = JSON.parse(raw);
    } catch {
      return {
        ok: false,
        message: `Invalid JSON (HTTP ${res.status}): ${raw.slice(0, 280)}`,
      };
    }
    if (data.response != null) {
      return { ok: true, status: res.status, data, message: String(data.response) };
    }
    const detail = data.detail;
    const detailStr = Array.isArray(detail)
      ? detail.map((d) => d.msg || d).join(", ")
      : detail
        ? String(detail)
        : "";
    return {
      ok: res.ok && res.status < 400,
      status: res.status,
      data,
      message: detailStr || `HTTP ${res.status}`,
    };
  } catch (e) {
    if (e.name === "AbortError") {
      return { ok: false, message: `Request timed out after ${timeoutMs / 1000}s. Try again or check backend logs.` };
    }
    return { ok: false, message: `Network error: ${e.message}` };
  } finally {
    clearTimeout(timer);
  }
}

const SIDEBAR = [
  { id: "general", label: "General chat", hint: "Ask anything about farming in Hinglish." },
  { id: "weather", label: "Weather", hint: "Live weather — mention a city (e.g. Ahmedabad)." },
  { id: "mandi", label: "Mandi prices", hint: "Latest mandi modal prices — commodity + state." },
  { id: "mandi_trend", label: "Mandi trend & ML", hint: "Price trend / next days forecast." },
  { id: "schemes", label: "Government schemes", hint: "Search or list government agriculture schemes." },
  { id: "fasal", label: "Crop advisory (RAG)", hint: "Sowing, irrigation, fertilizer, harvest schedules." },
  { id: "pest", label: "Pest & disease (RAG)", hint: "Pests, diseases, sprays (knowledge base)." },
  { id: "soil", label: "Soil health (RAG)", hint: "Soil type, pH, nutrients, improvement." },
  { id: "farming", label: "Farming tips (RAG)", hint: "Seasonal and general farming guidance." },
  { id: "profile", label: "Profile", hint: "Save or view your saved farmer profile." },
];

function LogoMark() {
  return (
    <svg className="logo-mark" viewBox="0 0 48 48" fill="none" aria-hidden>
      <circle cx="24" cy="24" r="22" stroke="currentColor" strokeWidth="1.5" opacity="0.35" />
      <path
        d="M24 8c-2 8-8 14-8 22 0 4 3 7 8 7s8-3 8-7c0-8-6-14-8-22z"
        fill="currentColor"
        opacity="0.9"
      />
      <path
        d="M16 28c4 2 8 2 16-2-2 6-6 10-8 12-4-2-6-6-8-10z"
        fill="currentColor"
        opacity="0.55"
      />
      <ellipse cx="24" cy="36" rx="10" ry="3" fill="currentColor" opacity="0.2" />
    </svg>
  );
}

export default function App() {
  const [mainView, setMainView] = useState("chat");
  const [activeTool, setActiveTool] = useState("general");
  const [sessionId] = useState(() => sessionKey());
  const [messages, setMessages] = useState(() => [
    {
      role: "assistant",
      text: "Hi — I am KisanBot. Pick a tool on the left, or type your question below.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loadingChat, setLoadingChat] = useState(false);
  const [backendOk, setBackendOk] = useState(null);

  const [weatherCity, setWeatherCity] = useState("Ahmedabad");
  const [mandiCommodity, setMandiCommodity] = useState("Wheat");
  const [mandiState, setMandiState] = useState("Gujarat");
  const [mandiDistrict, setMandiDistrict] = useState("Ahmedabad");
  const [trendDays, setTrendDays] = useState(7);
  const [schemeQuery, setSchemeQuery] = useState("agriculture subsidy");

  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState("");
  const [caption, setCaption] = useState("");
  const [diseaseResult, setDiseaseResult] = useState("");
  const [loadingImage, setLoadingImage] = useState(false);
  const fileInputRef = useRef(null);
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/health`)
      .then((r) => r.text())
      .then((t) => {
        if (cancelled) return;
        try {
          const j = t ? JSON.parse(t) : null;
          setBackendOk(!!j?.ok);
        } catch {
          setBackendOk(false);
        }
      })
      .catch(() => {
        if (!cancelled) setBackendOk(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  const sendRaw = useCallback(
    async (text) => {
      const t = (text || "").trim();
      if (!t || loadingChat) return;
      setMessages((m) => [...m, { role: "user", text: t }]);
      setLoadingChat(true);
      try {
        const out = await postJson("/v1/kisan/chat", { message: t, session_id: sessionId });
        const raw = out.data?.response != null ? String(out.data.response) : out.message;
        const assistantText = stripGraphFileLine(raw || "No reply.");
        setMessages((m) => [...m, { role: "assistant", text: assistantText }]);
      } finally {
        setLoadingChat(false);
      }
    },
    [loadingChat, sessionId]
  );

  const sendChat = useCallback(() => {
    const t = input.trim();
    if (!t || loadingChat) return;
    setInput("");
    sendRaw(t);
  }, [input, loadingChat, sendRaw]);

  const onPickFile = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (preview) URL.revokeObjectURL(preview);
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setDiseaseResult("");
  };

  const analyzeImage = async () => {
    if (!file || loadingImage) return;
    setLoadingImage(true);
    setDiseaseResult("");
    const fd = new FormData();
    fd.append("image", file);
    if (caption.trim()) fd.append("caption", caption.trim());
    fd.append("session_id", sessionId);
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 180_000);
    try {
      const res = await fetch(`${API_BASE}/v1/kisan/crop-disease`, {
        method: "POST",
        body: fd,
        signal: ctrl.signal,
      });
      const raw = await res.text();
      if (!raw.trim()) {
        setDiseaseResult("Empty response from server. Check API on port 8000.");
        return;
      }
      let data;
      try {
        data = JSON.parse(raw);
      } catch {
        setDiseaseResult(`Invalid JSON: ${raw.slice(0, 400)}`);
        return;
      }
      setDiseaseResult(data.response ?? JSON.stringify(data));
    } catch (e) {
      setDiseaseResult(e.name === "AbortError" ? "Request timed out." : `Error: ${e.message}`);
    } finally {
      clearTimeout(timer);
      setLoadingImage(false);
    }
  };

  const clearImage = () => {
    if (preview) URL.revokeObjectURL(preview);
    setFile(null);
    setPreview("");
    setCaption("");
    setDiseaseResult("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const active = SIDEBAR.find((s) => s.id === activeTool) ?? SIDEBAR[0];

  return (
    <div className="app">
      <div className="bg-pattern" aria-hidden />

      <div className="app-shell">
        <aside className="sidebar" aria-label="Tools">
          <div className="sidebar-brand">
            <LogoMark />
            <div>
              <div className="sidebar-title">KisanBot</div>
              <div className="sidebar-tag">Tools</div>
            </div>
          </div>

          <nav className="sidebar-nav">
            {SIDEBAR.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`sidebar-link ${activeTool === item.id ? "active" : ""}`}
                onClick={() => {
                  setActiveTool(item.id);
                  setMainView("chat");
                }}
              >
                <span className="sidebar-link-label">{item.label}</span>
              </button>
            ))}
            <button
              type="button"
              className={`sidebar-link sidebar-link-special ${mainView === "crop" ? "active" : ""}`}
              onClick={() => setMainView("crop")}
            >
              <span className="sidebar-link-label">Crop image scan</span>
            </button>
          </nav>
        </aside>

        <div className="main-column">
          <header className="topbar">
            <div>
              <h1 className="page-title">{mainView === "crop" ? "Crop health" : active.label}</h1>
              <p className="page-desc">
                {mainView === "crop"
                  ? "Upload any crop image (JPEG, PNG, WebP, …). Optional symptoms in English."
                  : active.hint}
              </p>
            </div>
            <div className="topbar-meta">
              <span className={`pill ${backendOk === true ? "pill-ok" : backendOk === false ? "pill-bad" : ""}`}>
                API: {backendOk === null ? "checking…" : backendOk ? "connected" : "offline"}
              </span>
            </div>
          </header>

          <main className="main">
            {mainView === "chat" && (
              <>
                {activeTool === "weather" && (
                  <div className="tool-panel">
                    <label className="field-row">
                      <span>City</span>
                      <input
                        value={weatherCity}
                        onChange={(e) => setWeatherCity(e.target.value)}
                        placeholder="Ahmedabad"
                      />
                    </label>
                    <button type="button" className="btn-secondary" onClick={() => sendRaw(`What is the weather in ${weatherCity.trim() || "Ahmedabad"}?`)}>
                      Ask weather
                    </button>
                  </div>
                )}

                {activeTool === "mandi" && (
                  <div className="tool-panel tool-panel-grid">
                    <label>
                      Commodity
                      <input value={mandiCommodity} onChange={(e) => setMandiCommodity(e.target.value)} />
                    </label>
                    <label>
                      State
                      <input value={mandiState} onChange={(e) => setMandiState(e.target.value)} />
                    </label>
                    <label>
                      District (optional)
                      <input value={mandiDistrict} onChange={(e) => setMandiDistrict(e.target.value)} />
                    </label>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() =>
                        sendRaw(
                          `Mandi prices for ${mandiCommodity} in ${mandiState}${mandiDistrict.trim() ? ` district ${mandiDistrict.trim()}` : ""}`
                        )
                      }
                    >
                      Get mandi prices
                    </button>
                  </div>
                )}

                {activeTool === "mandi_trend" && (
                  <div className="tool-panel tool-panel-grid">
                    <label>
                      Commodity
                      <input value={mandiCommodity} onChange={(e) => setMandiCommodity(e.target.value)} />
                    </label>
                    <label>
                      State
                      <input value={mandiState} onChange={(e) => setMandiState(e.target.value)} />
                    </label>
                    <label>
                      District (optional)
                      <input value={mandiDistrict} onChange={(e) => setMandiDistrict(e.target.value)} />
                    </label>
                    <label>
                      Days ahead
                      <input
                        type="number"
                        min={1}
                        max={14}
                        value={trendDays}
                        onChange={(e) => setTrendDays(Number(e.target.value) || 7)}
                      />
                    </label>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() =>
                        sendRaw(
                          `Mandi price trend next ${trendDays} days for ${mandiCommodity} in ${mandiState}${mandiDistrict.trim() ? ` district ${mandiDistrict.trim()}` : ""}, show graph`
                        )
                      }
                    >
                      Get trend
                    </button>
                  </div>
                )}

                {activeTool === "schemes" && (
                  <div className="tool-panel">
                    <label className="field-row">
                      <span>Search topic</span>
                      <input
                        value={schemeQuery}
                        onChange={(e) => setSchemeQuery(e.target.value)}
                        placeholder="loan, subsidy, PM-KISAN..."
                      />
                    </label>
                    <button type="button" className="btn-secondary" onClick={() => sendRaw(`Government schemes: ${schemeQuery}`)}>
                      Search schemes
                    </button>
                  </div>
                )}

                {activeTool === "profile" && (
                  <div className="tool-panel tool-panel-stack">
                    <button type="button" className="btn-secondary" onClick={() => sendRaw("Show my saved profile")}>
                      Show my profile
                    </button>
                    <p className="muted tiny">
                      To save profile, type in chat, e.g.: &quot;My name is Ravi, location is Ahmedabad, Gujarat, crops Wheat, email me@example.com&quot;
                    </p>
                  </div>
                )}

                <section className="panel chat-panel" aria-label="Chat">
                  <div className="messages">
                    {messages.map((msg, i) => (
                      <div key={i} className={`msg msg-${msg.role}`}>
                        <span className="msg-label">{msg.role === "user" ? "You" : "KisanBot"}</span>
                        <div className="msg-bubble">
                          {msg.text.split("\n").map((line, j) => (
                            <p key={j}>{line}</p>
                          ))}
                        </div>
                      </div>
                    ))}
                    {loadingChat && (
                      <div className="msg msg-assistant typing">
                        <span className="msg-label">KisanBot</span>
                        <div className="msg-bubble dots">
                          <span />
                          <span />
                          <span />
                        </div>
                      </div>
                    )}
                    <div ref={chatEndRef} />
                  </div>
                  <div className="composer">
                    <textarea
                      rows={2}
                      placeholder="Type your question…"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          sendChat();
                        }
                      }}
                    />
                    <button type="button" className="btn-primary" onClick={sendChat} disabled={loadingChat}>
                      Send
                    </button>
                  </div>
                </section>
              </>
            )}

            {mainView === "crop" && (
              <section className="panel crop-panel" aria-label="Crop scan">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="visually-hidden"
                  id="crop-file"
                  onChange={onPickFile}
                />

                <div
                  className={`dropzone ${preview ? "has-preview" : ""}`}
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.currentTarget.classList.add("drag");
                  }}
                  onDragLeave={(e) => e.currentTarget.classList.remove("drag")}
                  onDrop={(e) => {
                    e.preventDefault();
                    e.currentTarget.classList.remove("drag");
                    const f = e.dataTransfer.files?.[0];
                    if (f?.type?.startsWith("image/") || /\.(jpe?g|png|gif|webp|bmp|heic|heif)$/i.test(f?.name || "")) {
                      if (preview) URL.revokeObjectURL(preview);
                      setFile(f);
                      setPreview(URL.createObjectURL(f));
                      setDiseaseResult("");
                    }
                  }}
                >
                  {preview ? (
                    <img src={preview} alt="Preview" className="preview-img" />
                  ) : (
                    <div className="dropzone-inner">
                      <span className="drop-icon">＋</span>
                      <strong>Click or drop an image</strong>
                      <span className="muted">Any common image format</span>
                    </div>
                  )}
                </div>

                <label className="field-label" htmlFor="crop-caption">
                  Symptoms / notes (optional)
                </label>
                <textarea
                  id="crop-caption"
                  className="caption-input"
                  rows={2}
                  placeholder="e.g. yellow spots on leaves, white powder on underside…"
                  value={caption}
                  onChange={(e) => setCaption(e.target.value)}
                />

                <div className="crop-actions">
                  <button type="button" className="btn-ghost" onClick={clearImage} disabled={!file && !preview}>
                    Clear
                  </button>
                  <button type="button" className="btn-primary" onClick={analyzeImage} disabled={!file || loadingImage}>
                    {loadingImage ? "Analyzing…" : "Analyze crop"}
                  </button>
                </div>

                {diseaseResult && (
                  <div className="result-box">
                    <h2 className="result-title">Analysis</h2>
                    <pre className="result-text">{diseaseResult}</pre>
                  </div>
                )}
              </section>
            )}
          </main>

          <footer className="footer-inline">
            <span>
              Session <code>{sessionId.slice(0, 8)}…</code>
            </span>
            <span>
              Backend: <code>uv run python main.py api</code> · UI: <code>npm run dev</code>
            </span>
          </footer>
        </div>
      </div>
    </div>
  );
}
