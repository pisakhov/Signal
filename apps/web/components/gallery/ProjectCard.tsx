"use client";

import Link from "next/link";
import { Eye, EyeOff, Trash2 } from "lucide-react";

import { Project } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

type Props = {
  project: Project;
  ownedByMe: boolean;
  onDelete: () => void;
  onPublish: () => void;
};

export function ProjectCard({ project, ownedByMe, onDelete, onPublish }: Props) {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <CardTitle className="truncate text-base">{project.title}</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 text-xs text-muted-foreground">
        <p>Owner: {project.owner_username}</p>
        <p>Updated: {new Date(project.updated_at).toLocaleString()}</p>
        {project.published && <p className="mt-1 font-medium text-foreground">Published</p>}
      </CardContent>
      <CardFooter className="flex justify-between gap-2">
        <Link href={`/project/${project.id}`}>
          <Button size="sm">Open</Button>
        </Link>
        {ownedByMe && (
          <div className="flex gap-1">
            <Button size="sm" variant="outline" onClick={onPublish}>
              {project.published ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
            </Button>
            <Button size="sm" variant="outline" onClick={onDelete}>
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        )}
      </CardFooter>
    </Card>
  );
}
