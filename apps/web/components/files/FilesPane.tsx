"use client";

import { useCallback, useEffect, useState } from "react";
import { FilePlus, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { api, FileEntry } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MonacoFileEditor } from "@/components/editor/MonacoEditor";

export function FilesPane({
  projectId,
  refreshKey = 0,
}: {
  projectId: string;
  refreshKey?: number;
}) {
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [dirty, setDirty] = useState(false);
  const [newName, setNewName] = useState("");

  const refresh = useCallback(async () => {
    const { items } = await api.listFiles(projectId);
    setFiles(items.filter((f) => !f.is_dir));
  }, [projectId]);

  useEffect(() => {
    (async () => {
      await refresh();
    })();
  }, [refresh, refreshKey]);

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
                {f.path !== "dash_app.py" && (
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
      <div className="flex flex-1 flex-col">
        <div className="flex items-center justify-between border-b px-3 py-2 text-xs">
          <span className="truncate">{active ?? "Select a file"}</span>
          <Button
            size="sm"
            variant="outline"
            disabled={!active || !dirty}
            onClick={handleSave}
          >
            <Save className="mr-2 h-4 w-4" />
            Save
          </Button>
        </div>
        <div className="flex-1">
          <MonacoFileEditor
            path={active}
            value={content}
            onChange={(v) => {
              setContent(v);
              setDirty(true);
            }}
          />
        </div>
      </div>
    </div>
  );
}
