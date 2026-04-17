import { getToken } from "./auth";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type User = { id: string; username: string; is_admin: boolean };

export type Project = {
  id: string;
  owner_id: string;
  owner_username: string;
  title: string;
  slug: string;
  port: number | null;
  published: boolean;
  created_at: string;
  updated_at: string;
};

export type FileEntry = { path: string; is_dir: boolean; size: number };

export type ModelConfig = {
  id: string;
  label: string;
  model: string;
  base_url: string;
  created_at: string;
};

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return (await res.json()) as T;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ token: string; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  me: () => request<User>("/auth/me"),
  createUser: (username: string, password: string, is_admin = false) =>
    request<User>("/auth/users", {
      method: "POST",
      body: JSON.stringify({ username, password, is_admin }),
    }),
  listProjects: () => request<Project[]>("/projects"),
  createProject: (title: string) =>
    request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  deleteProject: (id: string) =>
    request<{ status: string }>(`/projects/${id}`, { method: "DELETE" }),
  publish: (id: string) =>
    request<Project>(`/projects/${id}/publish`, { method: "POST" }),
  listFiles: (id: string) =>
    request<{ items: FileEntry[] }>(`/projects/${id}/files`),
  readFile: (id: string, path: string) =>
    request<{ path: string; content: string }>(
      `/projects/${id}/file?path=${encodeURIComponent(path)}`,
    ),
  writeFile: (id: string, path: string, content: string) =>
    request<{ status: string }>(`/projects/${id}/file`, {
      method: "PUT",
      body: JSON.stringify({ path, content }),
    }),
  deleteFile: (id: string, path: string) =>
    request<{ status: string }>(
      `/projects/${id}/file?path=${encodeURIComponent(path)}`,
      { method: "DELETE" },
    ),
  renameFile: (id: string, from_path: string, to_path: string) =>
    request<{ status: string }>(`/projects/${id}/file/rename`, {
      method: "POST",
      body: JSON.stringify({ from_path, to_path }),
    }),
  redeploy: (id: string) =>
    request<{ port: number }>(`/projects/${id}/redeploy`, { method: "POST" }),
  stop: (id: string) =>
    request<{ status: string }>(`/projects/${id}/stop`, { method: "POST" }),
  logs: (id: string) =>
    request<{ text: string; running: boolean }>(`/projects/${id}/logs`),
  listModels: () => request<ModelConfig[]>("/models"),
  createModel: (body: {
    label: string;
    model: string;
    base_url: string;
    api_key_env: string;
    api_key?: string;
  }) =>
    request<ModelConfig>("/models", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateModel: (
    id: string,
    body: {
      label?: string;
      model?: string;
      base_url?: string;
      api_key_env?: string;
      api_key?: string;
    },
  ) =>
    request<ModelConfig>(`/models/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteModel: (id: string) =>
    request<{ status: string }>(`/models/${id}`, { method: "DELETE" }),
  testModel: (id: string) =>
    request<{ ok: boolean; message: string; latency_ms: number }>(
      `/models/${id}/test`,
      { method: "POST" },
    ),
  chatUrl: (id: string) => `${API_URL}/projects/${id}/chat`,
};
