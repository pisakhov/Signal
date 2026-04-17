"use client";

import Editor from "@monaco-editor/react";

function languageFor(path: string | null): string {
  if (!path) return "plaintext";
  if (path.endsWith(".py")) return "python";
  if (path.endsWith(".ts") || path.endsWith(".tsx")) return "typescript";
  if (path.endsWith(".js") || path.endsWith(".jsx")) return "javascript";
  if (path.endsWith(".json")) return "json";
  if (path.endsWith(".md")) return "markdown";
  if (path.endsWith(".css")) return "css";
  if (path.endsWith(".html")) return "html";
  return "plaintext";
}

type Props = {
  path: string | null;
  value: string;
  onChange: (v: string) => void;
};

export function MonacoFileEditor({ path, value, onChange }: Props) {
  return (
    <Editor
      height="100%"
      theme="light"
      language={languageFor(path)}
      value={value}
      onChange={(v) => onChange(v ?? "")}
      options={{
        minimap: { enabled: false },
        fontSize: 13,
        tabSize: 4,
        automaticLayout: true,
        scrollBeyondLastLine: false,
      }}
    />
  );
}
