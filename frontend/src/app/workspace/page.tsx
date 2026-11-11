import type { Metadata } from "next";
import WorkspaceScreen from "@/features/workspace/WorkspaceScreen";

export const metadata: Metadata = { title: "Choose your workspace" };

export default async function WorkspacePage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  return <WorkspaceScreen demoNewUser={(await searchParams).new === "1"} />;
}
