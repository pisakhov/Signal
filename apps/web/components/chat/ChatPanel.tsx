"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";

import { api, ModelConfig } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";

type Message = { role: "user" | "agent"; text: string };

export function ChatPanel({
  projectId,
  onAgentDone,
}: {
  projectId: string;
  onAgentDone?: () => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [modelId, setModelId] = useState<string>("");
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    (async () => {
      try {
        const list = await api.listModels();
        setModels(list);
        if (list.length > 0) setModelId(list[0].id);
      } catch {}
    })();
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!input.trim() || loading || !modelId) return;
    const prompt = input.trim();
    setMessages((m) => [...m, { role: "user", text: prompt }]);
    setInput("");
    setLoading(true);

    const res = await fetch(api.chatUrl(projectId), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${getToken() ?? ""}`,
        Accept: "text/event-stream",
      },
      body: JSON.stringify({ message: prompt, model_id: modelId }),
    });
    if (!res.ok || !res.body) {
      setMessages((m) => [
        ...m,
        { role: "agent", text: `Error: ${res.status}` },
      ]);
      setLoading(false);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    setMessages((m) => [...m, { role: "agent", text: "" }]);

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const normalized = buffer.replace(/\r\n/g, "\n");
      const events = normalized.split("\n\n");
      buffer = events.pop() ?? "";
      for (const block of events) {
        const dataParts = block
          .split("\n")
          .filter((l) => l.startsWith("data:"))
          .map((l) => l.slice(5).trimStart());
        if (dataParts.length === 0) continue;
        const raw = dataParts.join("\n");
        try {
          const parsed = JSON.parse(raw);
          if (parsed.text) {
            setMessages((m) => {
              const copy = m.slice();
              const last = copy[copy.length - 1];
              copy[copy.length - 1] = {
                role: "agent",
                text: (last.text ?? "") + parsed.text,
              };
              return copy;
            });
          }
        } catch {
          // non-JSON keepalive ignored
        }
      }
    }
    setLoading(false);
    onAgentDone?.();
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden">
      <ScrollArea className="min-h-0 flex-1 px-3 py-3">
        <div className="flex flex-col gap-3">
          {messages.map((m, i) => (
            <div
              key={i}
              className={
                m.role === "user"
                  ? "ml-auto max-w-[85%] break-words rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground"
                  : "mr-auto max-w-[85%] whitespace-pre-wrap break-words rounded-md bg-muted px-3 py-2 text-sm"
              }
            >
              {m.text || (m.role === "agent" && loading ? "…" : "")}
            </div>
          ))}
          <div ref={endRef} />
        </div>
      </ScrollArea>
      <form onSubmit={handleSubmit} className="flex flex-col gap-2 border-t p-3">
        {models.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No models configured. Ask an admin to add one.
          </p>
        ) : (
          <select
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
            className="rounded-md border bg-background px-2 py-1 text-xs"
            disabled={loading}
          >
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        )}
        <div className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask the agent…"
            disabled={loading}
          />
          <Button
            type="submit"
            size="icon"
            disabled={loading || !input.trim() || !modelId}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </form>
    </div>
  );
}
