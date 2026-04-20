"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { RotateCcw, GitCommit, Loader2, Badge } from "lucide-react";
import { toast } from "sonner";

import { api, HistoryEntry } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

type Props = {
  projectId: string;
  refreshKey?: number;
  onRevert?: () => void;
};

export function VersionHistory({ projectId, refreshKey = 0, onRevert }: Props) {
  const [open, setOpen] = useState(false);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [reverting, setReverting] = useState(false);
  const [hasNewChanges, setHasNewChanges] = useState(false);

  // Track the last known commit count to detect new changes
  const lastKnownCountRef = useRef(0);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const entries = await api.history(projectId);
      setHistory(entries);

      // Check if there are new commits since last check
      if (entries.length > lastKnownCountRef.current && lastKnownCountRef.current > 0) {
        setHasNewChanges(true);
      }
      lastKnownCountRef.current = entries.length;
    } catch (err) {
      toast.error(`Failed to load history: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // Refresh when refreshKey changes (external changes like agent edits)
  useEffect(() => {
    if (refreshKey > 0) {
      refresh();
      // Show "new changes" indicator briefly
      setHasNewChanges(true);
      setTimeout(() => setHasNewChanges(false), 3000);
    }
  }, [refreshKey, refresh]);

  useEffect(() => {
    if (open) {
      refresh();
      // Clear the "new changes" indicator when dialog opens
      setHasNewChanges(false);
    }
  }, [open, refresh]);

  async function handleRevert(commit: string) {
    setReverting(true);
    try {
      const result = await api.revert(projectId, commit);
      toast.success(`Reverted to commit ${commit.slice(0, 7)}`);
      setOpen(false);
      onRevert?.();
    } catch (err) {
      toast.error(`Revert failed: ${(err as Error).message}`);
    } finally {
      setReverting(false);
    }
  }

  function formatTimestamp(timestamp: string) {
    const date = new Date(timestamp);
    return date.toLocaleString();
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm" className="relative">
            <GitCommit className="mr-2 h-4 w-4" />
            History
            {hasNewChanges && (
              <span className="absolute -top-1 -right-1 flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-primary"></span>
              </span>
            )}
          </Button>
        }
      />
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Version History</DialogTitle>
          <DialogDescription>
            View and revert to previous versions of your project
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="max-h-[400px]">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : history.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No history available
            </p>
          ) : (
            <ul className="space-y-2 p-2">
              {history.map((entry, index) => (
                <li
                  key={entry.hash}
                  className={`flex items-start justify-between gap-2 rounded-md border p-3 ${
                    index === 0 && refreshKey > 0 ? "bg-primary/5" : ""
                  }`}
                >
                  <div className="flex-1 text-sm">
                    <div className="flex items-center gap-2">
                      <code className="text-xs text-muted-foreground">
                        {entry.short_hash}
                      </code>
                      {index === 0 && (
                        <span className="text-xs bg-primary/10 px-1.5 py-0.5 rounded text-primary">
                          Current
                        </span>
                      )}
                    </div>
                    <p className="mt-1 font-medium">{entry.message}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {entry.author} · {formatTimestamp(entry.timestamp)}
                    </p>
                  </div>
                  {index !== 0 && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleRevert(entry.hash)}
                      disabled={reverting}
                      title="Revert to this version"
                    >
                      {reverting ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <RotateCcw className="h-4 w-4" />
                      )}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
