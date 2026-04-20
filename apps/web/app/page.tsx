"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, LogOut, UserPlus, Cpu } from "lucide-react";
import { toast } from "sonner";

import { api, Project, User } from "@/lib/api";
import { clearToken } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { ProjectCard } from "@/components/gallery/ProjectCard";
import { NewProjectDialog } from "@/components/gallery/NewProjectDialog";
import { CreateUserDialog } from "@/components/admin/CreateUserDialog";
import { ManageModelsDialog } from "@/components/admin/ManageModelsDialog";

export default function GalleryPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [newOpen, setNewOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const [modelsOpen, setModelsOpen] = useState(false);

  const refresh = useCallback(async () => {
    const list = await api.listProjects();
    setProjects(list);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        setUser(await api.me());
        await refresh();
      } catch {
        router.replace("/login");
      }
    })();
  }, [refresh, router]);

  async function handleDelete(id: string) {
    await api.deleteProject(id);
    toast.success("Project deleted");
    await refresh();
  }

  async function handlePublish(id: string) {
    await api.publish(id);
    await refresh();
  }

  function handleLogout() {
    clearToken();
    router.replace("/login");
  }

  if (!user) return null;

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-8 py-10">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Quant Investment Research</h1>
          <p className="text-sm text-muted-foreground">
            Signed in as {user.username}
            {user.is_admin ? " · admin" : ""}
          </p>
        </div>
        <div className="flex gap-2">
          {user.is_admin && (
            <>
              <Button variant="outline" onClick={() => setModelsOpen(true)}>
                <Cpu className="mr-2 h-4 w-4" />
                Models
              </Button>
              <Button variant="outline" onClick={() => setUserOpen(true)}>
                <UserPlus className="mr-2 h-4 w-4" />
                New user
              </Button>
            </>
          )}
          <Button onClick={() => setNewOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            New project
          </Button>
          <Button variant="ghost" onClick={handleLogout}>
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </header>
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map((p) => (
          <ProjectCard
            key={p.id}
            project={p}
            ownedByMe={p.owned_by_me}
            onDelete={() => handleDelete(p.id)}
            onPublish={() => handlePublish(p.id)}
            onForked={refresh}
          />
        ))}
        {projects.length === 0 && (
          <p className="col-span-full text-sm text-muted-foreground">
            No projects yet. Click &quot;New project&quot; to create one.
          </p>
        )}
      </section>
      <NewProjectDialog
        open={newOpen}
        onOpenChange={setNewOpen}
        onCreated={refresh}
      />
      <CreateUserDialog open={userOpen} onOpenChange={setUserOpen} />
      <ManageModelsDialog open={modelsOpen} onOpenChange={setModelsOpen} />
    </main>
  );
}
