"use client";

import { useRef, useState } from "react";
import type { ChatMsg, ChatPatch, ChatSource, ToolRef } from "@/lib/chat";

// UI chat bersama (log + chips + composer). Mengonsumsi ChatSource secara STREAMING,
// jadi walkthrough statis dan live-mode nanti memakai render yang sama persis.
// Host menyediakan resolveTool(ref) → aksi (buka bukti / scroll / navigasi).

function applyPatch(log: ChatMsg[], p: ChatPatch): ChatMsg[] {
  const next = log.slice();
  const last = next[next.length - 1];
  if (!last || last.role !== "agent") return log;
  next[next.length - 1] = {
    role: "agent",
    streaming: true,
    answer: {
      trace: p.trace ? [...last.answer.trace, p.trace] : last.answer.trace,
      text: p.text ? last.answer.text + p.text : last.answer.text,
      tools: p.tool ? [...last.answer.tools, p.tool] : last.answer.tools,
    },
  };
  return next;
}

export default function ChatPanel({
  source,
  resolveTool,
  placeholder,
}: {
  source: ChatSource;
  resolveTool: (ref: ToolRef) => (() => void) | undefined;
  placeholder: string;
}) {
  const [log, setLog] = useState<ChatMsg[]>([{ role: "agent", answer: source.greeting }]);
  const [input, setInput] = useState("");
  const busy = useRef(false);

  async function ask(q: string) {
    if (busy.current) return;
    busy.current = true;
    setLog((l) => [
      ...l,
      { role: "user", text: q },
      { role: "agent", answer: { trace: [], text: "", tools: [] }, streaming: true },
    ]);
    for await (const patch of source.ask(q)) {
      setLog((l) => applyPatch(l, patch));
    }
    setLog((l) => {
      const next = l.slice();
      const last = next[next.length - 1];
      if (last && last.role === "agent") next[next.length - 1] = { role: "agent", answer: last.answer };
      return next;
    });
    busy.current = false;
  }

  return (
    <div className="chat">
      <div className="chat-log">
        {log.map((m, i) =>
          m.role === "user" ? (
            <div className="cmsg user" key={i}>{m.text}</div>
          ) : (
            <div className={`cmsg agent${m.streaming ? " streaming" : ""}`} key={i}>
              {m.answer.trace.length > 0 && (
                <div className="ctrace">
                  {m.answer.trace.map((t, j) => (
                    <span className="tc" key={j}>▸ {t}</span>
                  ))}
                </div>
              )}
              {m.answer.text && <div className="ctext">{m.answer.text}</div>}
              {m.answer.tools.length > 0 && (
                <div className="ctools">
                  {m.answer.tools.map((t, j) => {
                    const onClick = resolveTool(t.ref);
                    return (
                      <button key={j} onClick={onClick} disabled={!onClick}>
                        {t.label} →
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )
        )}
      </div>
      {source.chips.length > 0 && (
        <div className="chat-chips">
          {source.chips.map((q) => (
            <button key={q} onClick={() => ask(q)}>{q}</button>
          ))}
        </div>
      )}
      <form
        className="chat-input"
        onSubmit={(e) => {
          e.preventDefault();
          const q = input.trim();
          if (q) { ask(q); setInput(""); }
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={placeholder}
          aria-label="Tanya agen"
        />
        <button type="submit">Kirim →</button>
      </form>
    </div>
  );
}
