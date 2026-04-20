"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, GitCommit, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { api, HistoryEntry } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

type Props = {
  projectId: string;
  refreshKey?: number;
  onNavigate?: () => void;
};

export function VersionNav({ projectId, refreshKey = 0, onNavigate }: Props) {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [navigating, setNavigating] = useState(false);

  const currentIndexRef = useRef(0);

  const refreshHistory = useCallback(async () => {
    setLoading(true);
    try {
      const entries = await api.history(projectId);
      setHistory(entries);
      // Current version is always at index 0 (newest first)
      // When refreshKey changes, we're back at latest
      if (refreshKey > 0) {
        setCurrentIndex(0);
        currentIndexRef.current = 0;
      }
    } catch {
      // Silently fail - history might not exist yet
    } finally {
      setLoading(false);
    }
  }, [projectId, refreshKey]);

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  const canGoBack = currentIndex < history.length - 1;
  const canGoForward = currentIndex > 0;

  async function goBack() {
    if (!canGoBack || navigating) return;

    const newIndex = currentIndex + 1;
    const targetCommit = history[newIndex];

    setNavigating(true);
    try {
      await api.revert(projectId, targetCommit.hash);
      setCurrentIndex(newIndex);
      currentIndexRef.current = newIndex;
      toast.success(`Reverted to: ${targetCommit.message.slice(0, 50)}...`);
      onNavigate?.();
    } catch (err) {
      toast.error(`Revert failed: ${(err as Error).message}`);
    } finally {
      setNavigating(false);
    }
  }

  async function goForward() {
    if (!canGoForward || navigating) return;

    const newIndex = currentIndex - 1;
    const targetCommit = history[newIndex];

    setNavigating(true);
    try {
      await api.revert(projectId, targetCommit.hash);
      setCurrentIndex(newIndex);
      currentIndexRef.current = newIndex;
      toast.success(`Forward to: ${targetCommit.message.slice(0, 50)}...`);
      onNavigate?.();
    } catch (err) {
      toast.error(`Revert failed: ${(err as Error).message}`);
    } finally {
      setNavigating(false);
    }
  }

  // Get current commit info for tooltip
  const currentInfo = history[currentIndex];
  const positionText =
    history.length > 0
      ? `${currentIndex + 1} of ${history.length}`
      : "No history";

  return (
    <TooltipProvider>
      <div className="flex items-center gap-1">
        {/* Back button */}
        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                size="sm"
                variant="outline"
                className="w-8 px-0"
                disabled={!canGoBack || navigating || loading}
                onClick={goBack}
              >
                {navigating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ChevronLeft className="h-4 w-4" />
                )}
              </Button>
            }
          />
          <TooltipContent>
            {canGoBack
              ? `Back to: ${history[currentIndex + 1]?.message.slice(0, 30) || "previous"}`
              : "At earliest version"}
          </TooltipContent>
        </Tooltip>

        {/* Status indicator */}
        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                size="sm"
                variant="outline"
                className="w-auto gap-1.5 min-w-[100px]"
                disabled={history.length === 0}
              >
                <GitCommit className="h-4 w-4 shrink-0" />
                <span className="text-xs">{positionText}</span>
              </Button>
            }
          />
          <TooltipContent>
            {currentInfo ? (
              <div className="max-w-[200px]">
                <p className="font-medium">{currentInfo.message}</p>
                <p className="text-xs text-muted-foreground">
                  {currentInfo.short_hash} · {new Date(currentInfo.timestamp).toLocaleString()}
                </p>
              </div>
            ) : (
              "No version history yet"
            )}
          </TooltipContent>
        </Tooltip>

        {/* Forward button */}
        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                size="sm"
                variant="outline"
                className="w-8 px-0"
                disabled={!canGoForward || navigating || loading}
                onClick={goForward}
              >
                {navigating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </Button>
            }
          />
          <TooltipContent>
            {canGoForward
              ? `Forward to: ${history[currentIndex - 1]?.message.slice(0, 30) || "latest"}`
              : "At latest version"}
          </TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  );
}
