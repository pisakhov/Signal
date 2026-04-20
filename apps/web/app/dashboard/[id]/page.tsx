"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { api, Project } from "@/lib/api";

const DASH_BASE_URL = process.env.NEXT_PUBLIC_DASH_BASE_URL || "";

export default function DashboardFullscreen({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [port, setPort] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const list = await api.listProjects();
        const p = list.find((x) => x.id === id);
        if (!p || !p.published) {
          router.replace("/");
          return;
        }
        setProject(p);
        try {
          const { port: newPort } = await api.start(p.id);
          setPort(newPort);
        } catch (err) {
          setError((err as Error).message);
        }
      } catch {
        router.replace("/login");
      }
    })();
  }, [id, router]);

  if (!project) return null;

  if (error) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background text-sm text-destructive">
        {error}
      </div>
    );
  }

  if (!port) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background text-sm text-muted-foreground">
        Starting {project.title}…
      </div>
    );
  }

  return (
    <iframe
      src={DASH_BASE_URL || `http://localhost:${port}`}
      title={project.title}
      className="h-screen w-screen border-0"
    />
  );
}
