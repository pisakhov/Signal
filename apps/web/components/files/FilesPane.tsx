"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { FilePlus, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { api, FileEntry } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MonacoFileEditor } from "@/components/editor/MonacoEditor";
import { VersionNav } from "@/components/history/VersionNav";

type Props = {
  projectId: string;
  refreshKey?: number;
  ownedByMe?: boolean;
};

export function FilesPane({
  projectId,
  refreshKey = 0,
  ownedByMe = true,
}: Props) {
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [dirty, setDirty] = useState(false);
  const [newName, setNewName] = useState("");
  const [isFading, setIsFading] = useState(false);

  // Track refreshKey to detect external changes
  const prevRefreshKeyRef = useRef(refreshKey);

  const refresh = useCallback(async () => {
    const { items } = await api.listFiles(projectId);
    setFiles(items.filter((f) => !f.is_dir));
  }, [projectId]);

  // Reload active file content from server
  const refreshActiveFile = useCallback(async () => {
    if (!active) return;
    try {
      const { content: text } = await api.readFile(projectId, active);
      setContent(text);
      setDirty(false);
      // Trigger fade effect
      setIsFading(true);
      setTimeout(() => setIsFading(false), 2000);
    } catch {
      // File might have been deleted
      setActive(null);
      setContent("");
    }
  }, [projectId, active]);

  useEffect(() => {
    (async () => {
      await refresh();
    })();
  }, [refresh, refreshKey]);

  // Auto-refresh active file when refreshKey changes (external changes)
  useEffect(() => {
    if (refreshKey !== prevRefreshKeyRef.current && refreshKey > 0) {
      refreshActiveFile();
      prevRefreshKeyRef.current = refreshKey;
    }
  }, [refreshKey, refreshActiveFile]);

  const open = useCallback(
    async (path: string) => {
      const { content: text } = await api.readFile(projectId, path);
      setActive(path);
      setContent(text);
      setDirty(false);
    },
    [projectId],
  );

  async function handleSave() {
    if (!active) return;
    await api.writeFile(projectId, active, content);
    setDirty(false);
    toast.success("Saved");
  }

  async function handleDelete(path: string) {
    await api.deleteFile(projectId, path);
    if (active === path) {
      setActive(null);
      setContent("");
    }
    await refresh();
  }

  async function handleCreate() {
    const path = newName.trim();
    if (!path) return;
    await api.writeFile(projectId, path, "");
    setNewName("");
    await refresh();
    await open(path);
  }

  return (
    <div className="flex h-full">
      <div className="flex w-72 flex-col border-r">
        {ownedByMe && (
          <>
            <div className="flex gap-2 p-3">
              <Input
                placeholder="new_file.py"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
              <Button size="icon" variant="outline" onClick={handleCreate}>
                <FilePlus className="h-4 w-4" />
              </Button>
            </div>
            <Separator />
          </>
        )}
        <Separator />
        <ScrollArea className="flex-1">
          <ul className="p-2 text-sm">
            {files.map((f) => (
              <li
                key={f.path}
                className={`group flex items-center justify-between rounded px-2 py-1 ${active === f.path ? "bg-muted" : "hover:bg-muted"}`}
              >
                <button
                  className="flex-1 truncate text-left"
                  onClick={() => open(f.path)}
                >
                  {f.path}
                </button>
                {ownedByMe && f.path !== "dash_app.py" && (
                  <button
                    className="invisible text-muted-foreground group-hover:visible"
                    onClick={() => handleDelete(f.path)}
                    title="Delete"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </li>
            ))}
          </ul>
        </ScrollArea>
      </div>
      <div className="relative flex flex-1 flex-col">
        {/* Fade overlay - shows for 2 seconds when content changes */}
        {isFading && (
          <div className="pointer-events-none absolute inset-0 z-10 bg-primary/10 animate-[fade-out_2s_ease-out_forwards]" />
        )}
        <div className="flex items-center justify-between border-b px-3 py-2 text-xs">
          <span className="truncate">{active ?? "Select a file"}</span>
          <div className="flex gap-2">
            {ownedByMe && (
              <>
                <VersionNav
                  projectId={projectId}
                  refreshKey={refreshKey}
                  onNavigate={() => {
                    refreshActiveFile();
                    refresh();
                  }}
                />
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!active || !dirty}
                  onClick={handleSave}
                >
                  <Save className="mr-2 h-4 w-4" />
                  Save
                </Button>
              </>
            )}
            {!ownedByMe && (
              <span className="text-xs text-muted-foreground italic">
                Read-only view
              </span>
            )}
          </div>
        </div>
        <div className="flex-1">
          <MonacoFileEditor
            path={active}
            value={content}
            onChange={(v) => {
              setContent(v);
              setDirty(true);
            }}
            readOnly={!ownedByMe}
          />
        </div>
      </div>
    </div>
  );
}
