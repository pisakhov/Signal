"use client";

import Editor from "@monaco-editor/react";
import { languageFor } from "@/lib/utils";

type Props = {
  path: string | null;
  value: string;
  onChange: (v: string) => void;
  readOnly?: boolean;
};

export function MonacoFileEditor({
  path,
  value,
  onChange,
  readOnly = false,
}: Props) {
  return (
    <Editor
      height="100%"
      theme="light"
      language={languageFor(path)}
      value={value}
      onChange={readOnly ? undefined : (v) => onChange(v ?? "")}
      options={{
        minimap: { enabled: false },
        fontSize: 13,
        tabSize: 4,
        automaticLayout: true,
        scrollBeyondLastLine: false,
        readOnly,
      }}
    />
  );
}
