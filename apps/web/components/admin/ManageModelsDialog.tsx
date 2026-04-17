"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Pencil, PlugZap, Trash2, X } from "lucide-react";
import { toast } from "sonner";

import { api, ModelConfig } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";

type Props = {
  open: boolean;
  onOpenChange: (v: boolean) => void;
};

export function ManageModelsDialog({ open, onOpenChange }: Props) {
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [label, setLabel] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKeyEnv, setApiKeyEnv] = useState("OPENAI_API_KEY");
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editLabel, setEditLabel] = useState("");
  const [editModel, setEditModel] = useState("");
  const [editBaseUrl, setEditBaseUrl] = useState("");
  const [editApiKeyEnv, setEditApiKeyEnv] = useState("");
  const [editApiKey, setEditApiKey] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setModels(await api.listModels());
    } catch (err) {
      toast.error((err as Error).message);
    }
  }, []);

  useEffect(() => {
    if (open) refresh();
  }, [open, refresh]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await api.createModel({
        label,
        model,
        base_url: baseUrl,
        api_key_env: apiKeyEnv,
        api_key: apiKey || undefined,
      });
      toast.success("Model added");
      setLabel("");
      setModel("");
      setBaseUrl("");
      setApiKey("");
      await refresh();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.deleteModel(id);
      await refresh();
    } catch (err) {
      toast.error((err as Error).message);
    }
  }

  function startEdit(m: ModelConfig) {
    setEditingId(m.id);
    setEditLabel(m.label);
    setEditModel(m.model);
    setEditBaseUrl(m.base_url);
    setEditApiKeyEnv("");
    setEditApiKey("");
  }

  function cancelEdit() {
    setEditingId(null);
  }

  async function handleSaveEdit(id: string) {
    setSavingEdit(true);
    try {
      await api.updateModel(id, {
        label: editLabel,
        model: editModel,
        base_url: editBaseUrl,
        api_key_env: editApiKeyEnv || undefined,
        api_key: editApiKey || undefined,
      });
      toast.success("Model updated");
      setEditingId(null);
      await refresh();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setSavingEdit(false);
    }
  }

  async function handleTest(id: string) {
    setTestingId(id);
    try {
      const res = await api.testModel(id);
      if (res.ok) {
        toast.success(res.message);
      } else {
        toast.error(res.message);
      }
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setTestingId(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Models</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-2">
          {models.length === 0 && (
            <p className="text-sm text-muted-foreground">No models yet.</p>
          )}
          {models.map((m) =>
            editingId === m.id ? (
              <div
                key={m.id}
                className="flex flex-col gap-2 rounded-md border px-3 py-2 text-sm"
              >
                <Input
                  value={editLabel}
                  onChange={(e) => setEditLabel(e.target.value)}
                  placeholder="Label"
                />
                <Input
                  value={editModel}
                  onChange={(e) => setEditModel(e.target.value)}
                  placeholder="Model"
                />
                <Input
                  value={editBaseUrl}
                  onChange={(e) => setEditBaseUrl(e.target.value)}
                  placeholder="Base URL"
                />
                <Input
                  value={editApiKeyEnv}
                  onChange={(e) => setEditApiKeyEnv(e.target.value)}
                  placeholder="API key env var (leave blank to keep)"
                />
                <Input
                  type="password"
                  value={editApiKey}
                  onChange={(e) => setEditApiKey(e.target.value)}
                  placeholder="API key (leave blank to keep)"
                />
                <div className="flex justify-end gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={cancelEdit}
                    disabled={savingEdit}
                  >
                    <X className="h-4 w-4" />
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => handleSaveEdit(m.id)}
                    disabled={savingEdit}
                  >
                    {savingEdit ? "Saving…" : "Save"}
                  </Button>
                </div>
              </div>
            ) : (
              <div
                key={m.id}
                className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
              >
                <div className="flex flex-col">
                  <span className="font-medium">{m.label}</span>
                  <span className="text-xs text-muted-foreground">
                    {m.model} · {m.base_url}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleTest(m.id)}
                    disabled={testingId === m.id}
                  >
                    <PlugZap className="h-4 w-4" />
                    {testingId === m.id ? "Testing…" : "Test"}
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => startEdit(m)}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => handleDelete(m.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ),
          )}
        </div>
        <Separator />
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-2">
            <Label htmlFor="m-label">Label</Label>
            <Input
              id="m-label"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Cerebras GLM 4.7"
              required
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="m-model">Model</Label>
            <Input
              id="m-model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="zai-glm-4.7"
              required
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="m-base">Base URL</Label>
            <Input
              id="m-base"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.cerebras.ai/v1"
              required
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="m-env">API key env var</Label>
            <Input
              id="m-env"
              value={apiKeyEnv}
              onChange={(e) => setApiKeyEnv(e.target.value)}
              placeholder="OPENAI_API_KEY"
              required
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="m-key">API key (optional)</Label>
            <Input
              id="m-key"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Written to .env if provided"
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={loading}>
              {loading ? "Adding…" : "Add model"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
