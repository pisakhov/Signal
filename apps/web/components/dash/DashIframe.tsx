"use client";

import { useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Power,
  RefreshCw,
  Terminal as TerminalIcon,
} from "lucide-react";
import { toast } from "sonner";

import { api, Project } from "@/lib/api";
import { Button } from "@/components/ui/button";

export function DashIframe({
  project,
  refreshKey = 0,
}: {
  project: Project;
  refreshKey?: number;
}) {
  const [port, setPort] = useState<number | null>(project.port);
  const [busy, setBusy] = useState(false);
  const [nonce, setNonce] = useState(0);
  const [logs, setLogs] = useState("");
  const [running, setRunning] = useState(false);
  const [termOpen, setTermOpen] = useState(true);
  const termRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (refreshKey > 0) setNonce((n) => n + 1);
  }, [refreshKey]);

  useEffect(() => {
    setPort((prev) => {
      if (prev === project.port) return prev;
      setNonce((n) => n + 1);
      return project.port;
    });
  }, [project.port]);

  async function handleRedeploy() {
    setBusy(true);
    try {
      const { port: p } = await api.redeploy(project.id);
      setPort(p);
      setNonce((n) => n + 1);
      toast.success(`Running on port ${p}`);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleStop() {
    setBusy(true);
    try {
      await api.stop(project.id);
      setPort(null);
      toast.success("Stopped");
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function tick() {
      try {
        const res = await api.logs(project.id);
        if (cancelled) return;
        setLogs(res.text);
        setRunning(res.running);
      } catch {}
    }
    tick();
    const h = setInterval(tick, 1000);
    return () => {
      cancelled = true;
      clearInterval(h);
    };
  }, [project.id, nonce]);

  useEffect(() => {
    if (termRef.current) {
      termRef.current.scrollTop = termRef.current.scrollHeight;
    }
  }, [logs]);

  const src = port ? `http://localhost:${port}?v=${nonce}` : null;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b px-3 py-2 text-xs">
        <span>{port ? `Running at localhost:${port}` : "Not running"}</span>
        <div className="flex gap-2">
          <Button size="sm" onClick={handleRedeploy} disabled={busy}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Redeploy
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleStop}
            disabled={busy || !port}
          >
            <Power className="mr-2 h-4 w-4" />
            Stop
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              window.open(`/dashboard/${project.id}`, "_blank", "noopener")
            }
            disabled={!port}
          >
            <ExternalLink className="mr-2 h-4 w-4" />
            Open
          </Button>
        </div>
      </div>
      <div className="flex-1 bg-muted">
        {src ? (
          <iframe
            src={src}
            className="h-full w-full border-0"
            title={project.title}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            Click &quot;Redeploy&quot; to start the Dash app.
          </div>
        )}
      </div>
      <div
        className={`flex flex-col border-t ${termOpen ? "h-56" : "h-auto"}`}
      >
        <button
          type="button"
          onClick={() => setTermOpen((v) => !v)}
          className="flex items-center gap-2 border-b bg-muted/50 px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted"
        >
          <TerminalIcon className="h-3.5 w-3.5" />
          <span>Terminal</span>
          <span className="ml-auto flex items-center gap-2">
            <span>{running ? "● running" : "○ stopped"}</span>
            {termOpen ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronUp className="h-3.5 w-3.5" />
            )}
          </span>
        </button>
        {termOpen && (
          <pre
            ref={termRef}
            className="flex-1 overflow-auto bg-black px-3 py-2 font-mono text-[11px] leading-snug text-green-200"
          >
            {logs || "(no output yet — click Redeploy)"}
          </pre>
        )}
      </div>
    </div>
  );
}
