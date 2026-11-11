import type { Metadata } from "next";
import Image from "next/image";

import AppTopBar from "@/components/AppTopBar";
import WorkspaceSelector from "@/features/workspace/WorkspaceSelector";

export const metadata: Metadata = {
  title: "Choose your workspace",
};

/**
 * Workspace Selection — Figma D03 (3344:2) and M03 (3382:71).
 *
 * Mobile replaces the top bar (email, avatar, sign out) with a plain logo row
 * and left-aligns the heading; desktop centres it under the full bar.
 *
 * `?new=1` (sent by Create Account) shows the new-user state, D03 3640:18 and
 * M03 3640:344: only the personal workspace, and a card to create an
 * organization. CLOUDAPPG5-132.
 *
 * TODO: decide "new user" from GET /me (no organization memberships) instead
 * of the URL, once it exists.
 */
export default async function WorkspacePage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const isNewUser = (await searchParams).new === "1";

  return (
    <div className="flex min-h-screen flex-1 flex-col bg-canvas">
      <div className="hidden md:block">
        {/* TODO: read the signed-in user from the auth session instead. */}
        <AppTopBar email="chai@warrantytrack.io" initials="CA" />
      </div>

      <main className="mx-auto flex w-full max-w-[920px] flex-col gap-5 px-6 pt-4 pb-7 md:items-center md:gap-11 md:px-8 md:pt-[166px] md:pb-20">
        <div className="flex items-center gap-2.5 md:hidden">
          <Image src="/warranty-logo-blue.svg" alt="" width={36} height={36} />
          <span className="text-[19px] font-bold text-brand">
            WarrantyTrack
          </span>
        </div>

        <div className="flex flex-col gap-2 md:gap-3.5 md:text-center">
          <h1 className="text-[29px] leading-[38px] font-bold tracking-[-0.58px] text-brand md:text-[44px] md:leading-[54px] md:tracking-[-0.88px]">
            Choose your workspace
          </h1>
          {isNewUser ? (
            <p className="text-[14px] leading-[22px] tracking-[-0.28px] text-muted md:text-[18px] md:leading-7 md:tracking-[-0.36px]">
              Start with your personal workspace, or set one up for your
              organization.
            </p>
          ) : (
            <>
              <p className="text-[14px] leading-[22px] tracking-[-0.28px] text-muted md:hidden">
                Pick where to store and track warranties. You can switch anytime.
              </p>
              <p className="hidden text-[18px] leading-7 tracking-[-0.36px] text-muted md:block">
                Pick where you want to store and track warranties. You can switch at
                any time.
              </p>
            </>
          )}
        </div>

        <WorkspaceSelector isNewUser={isNewUser} />
      </main>
    </div>
  );
}
