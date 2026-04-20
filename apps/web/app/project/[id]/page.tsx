"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Copy } from "lucide-react";
import { toast } from "sonner";

import { api, Project, User } from "@/lib/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { FilesPane } from "@/components/files/FilesPane";
import { DashIframe } from "@/components/dash/DashIframe";

export default function ProjectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [filesRefreshKey, setFilesRefreshKey] = useState(0);
  const [isForking, setIsForking] = useState(false);

  async function handleFork() {
    if (!project) return;
    setIsForking(true);
    try {
      const forked = await api.fork(project.id);
      toast.success(
        project.owned_by_me
          ? "Project duplicated"
          : "Project forked successfully"
      );
      router.push(`/project/${forked.id}`);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setIsForking(false);
    }
  }

  useEffect(() => {
    (async () => {
      try {
        const me = await api.me();
        setUser(me);
        const list = await api.listProjects();
        const p = list.find((x) => x.id === id);
        if (!p) {
          router.replace("/");
          return;
        }
        setProject(p);
        try {
          const { running } = await api.logs(p.id);
          if (!running || !p.port) {
            // Owner uses redeploy, viewers use start
            const { port } = await (p.owned_by_me
              ? api.redeploy(p.id)
              : api.start(p.id));
            setProject({ ...p, port });
          }
        } catch {}
      } catch {
        router.replace("/login");
      }
    })();
  }, [id, router]);

  useEffect(() => {
    if (filesRefreshKey === 0) return;
    (async () => {
      try {
        const list = await api.listProjects();
        const p = list.find((x) => x.id === id);
        if (p) setProject(p);
      } catch {}
    })();
  }, [filesRefreshKey, id]);

  if (!project || !user) return null;
  const ownedByMe = project.owner_id === user.id;

  return (
    <main className="flex h-full min-h-0 flex-1 overflow-hidden">
      <aside className="flex w-1/3 min-w-[320px] shrink-0 flex-col overflow-hidden border-r">
        <div className="flex items-center justify-between gap-2 p-3">
          <div className="flex items-center gap-2 overflow-hidden">
            <Link href="/" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground">
              <ArrowLeft className="mr-1 h-4 w-4" />
              Gallery
            </Link>
            <Separator orientation="vertical" className="mx-2 h-5" />
            <h1 className="truncate text-sm font-medium">{project.title}</h1>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleFork}
            disabled={isForking}
          >
            <Copy className="mr-1 h-3 w-3" />
            {isForking
              ? "Copying..."
              : project.owned_by_me
              ? "Duplicate"
              : "Fork"}
          </Button>
        </div>
        <Separator />
        <div className="min-h-0 flex-1 overflow-hidden">
          <ChatPanel
            projectId={project.id}
            onAgentDone={() => setFilesRefreshKey((k) => k + 1)}
          />
        </div>
      </aside>
      <section className="flex-1 overflow-hidden">
        <Tabs defaultValue="app" className="flex h-full flex-col">
          <TabsList className="mx-3 mt-3 w-fit">
            <TabsTrigger value="files">Files</TabsTrigger>
            <TabsTrigger value="app">App</TabsTrigger>
          </TabsList>
          <TabsContent value="files" className="flex-1 overflow-hidden">
            <FilesPane
              projectId={project.id}
              refreshKey={filesRefreshKey}
              ownedByMe={ownedByMe}
            />
          </TabsContent>
          <TabsContent value="app" className="flex-1 overflow-hidden">
            <DashIframe
              project={project}
              refreshKey={filesRefreshKey}
              ownedByMe={ownedByMe}
            />
          </TabsContent>
        </Tabs>
      </section>
    </main>
  );
}
