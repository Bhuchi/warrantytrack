"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

import WorkspaceCard from "./WorkspaceCard";
import { OrganizationIcon, PersonalIcon } from "./WorkspaceIcons";

/**
 * "use client" marks this as a Client Component: it runs in the browser, so it
 * can hold state and respond to clicks. Everything it imports becomes client
 * code too, so keep the boundary as low in the tree as possible.
 *
 * Desktop (D03) gives each card its own Continue button. Mobile (M03) drops
 * those for one shared button at the bottom, which needs to know the current
 * selection — so it lives here, where the state is.
 *
 * TODO: the counts below are the placeholder values from Figma. Replace with
 * real data from lib/api once the workspaces endpoint exists.
 */

const WORKSPACES = [
  {
    id: "personal",
    title: "Personal Workspace",
    description:
      "Manage your own devices, receipts and warranties in a private space only you can see.",
    descriptionShort: "Private space only you can see.",
    href: "/dashboard",
    stats: [
      { value: "12", label: "Assets" },
      { value: "1", label: "Expiring soon" },
    ],
  },
  {
    id: "organization",
    title: "Organization Workspace",
    description:
      "Track assets and warranties across departments, with shared visibility for your whole team.",
    descriptionShort: "Shared across your whole team.",
    href: "/dashboard",
    stats: [
      { value: "128", label: "Assets" },
      { value: "5", label: "Departments" },
    ],
  },
] as const;

type WorkspaceId = (typeof WORKSPACES)[number]["id"];

export default function WorkspaceSelector() {
  // Figma shows the organization card selected by default.
  const [selected, setSelected] = useState<WorkspaceId>("organization");

  const selectedWorkspace =
    WORKSPACES.find((workspace) => workspace.id === selected) ?? WORKSPACES[0];

  return (
    <div className="flex w-full flex-col gap-5 md:items-center md:gap-11">
      <div className="flex w-full flex-col gap-5 md:flex-row md:items-start md:gap-8">
        {WORKSPACES.map((workspace) => (
          <WorkspaceCard
            key={workspace.id}
            title={workspace.title}
            description={workspace.description}
            descriptionShort={workspace.descriptionShort}
            href={workspace.href}
            stats={[...workspace.stats]}
            icon={
              workspace.id === "personal" ? (
                <PersonalIcon className="size-6 md:size-[26px]" />
              ) : (
                <OrganizationIcon className="size-6 md:size-[26px]" />
              )
            }
            selected={workspace.id === selected}
            onSelect={() => setSelected(workspace.id)}
          />
        ))}
      </div>

      <p className="flex w-full items-center gap-2.5 rounded-[10px] bg-brand-subtle px-4 py-3.5 text-[13px] leading-[19px] tracking-[-0.26px] text-brand md:w-auto md:rounded-lg md:py-3.5 md:pr-5 md:pl-[18px] md:text-[14px] md:tracking-[-0.28px]">
        <Image
          src="/icons/info.svg"
          alt=""
          width={18}
          height={18}
          className="shrink-0"
        />
        You can switch workspaces anytime from Settings.
      </p>

      <Link
        href={selectedWorkspace.href}
        className="flex h-14 w-full items-center justify-center rounded-[10px] bg-brand text-[17px] font-bold tracking-[-0.34px] text-brand-foreground md:hidden"
      >
        Continue
      </Link>
    </div>
  );
}
