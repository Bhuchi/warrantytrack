import type { Metadata } from "next";
import Link from "next/link";

import { AddAssetIcon } from "@/components/NavIcons";
import AssetsList from "@/features/assets/AssetsList";
import { getAssets } from "@/features/assets/getAssets";

export const metadata: Metadata = {
  title: "Assets",
};

/**
 * /assets. Mobile M05 (3382:296), personal M05 (3418:524), desktop D05 (3354:2).
 * The page stays on the server; the search, filters and list run in the
 * browser inside AssetsList.
 *
 * TODO: "SIIT Organization" is the Figma placeholder; read the workspace name
 * from the session once /workspaces exists (FE-05).
 */
export default async function AssetsPage() {
  // Everything registered, ignoring filters: the count under the title.
  const { total } = await getAssets();

  return (
    <main className="flex flex-1 flex-col gap-3 px-5 pt-4 pb-6 md:gap-4 md:px-8 md:pt-6 md:pb-8">
      <div className="flex items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-[22px] font-bold tracking-[-0.44px] text-brand md:text-[30px] md:tracking-[-0.6px]">
            Assets
          </h1>
          <p className="text-[12px] tracking-[-0.24px] text-muted md:text-[14px] md:tracking-[-0.28px]">
            {total} registered in SIIT Organization
          </p>
        </div>
        {/* Desktop: next to the title (D05). Mobile has it at the bottom instead. */}
        <Link
          href="/assets/new"
          className="hidden h-[42px] shrink-0 items-center gap-2 rounded-lg bg-brand px-4 text-[14px] font-bold tracking-[-0.28px] text-brand-foreground md:flex"
        >
          <AddAssetIcon className="size-[17px]" />
          Add Asset
        </Link>
      </div>

      <AssetsList />

      {/* Mobile only, as on the Dashboard. M05 3460:171. */}
      <Link
        href="/assets/new"
        className="flex h-[54px] items-center justify-center gap-2 rounded-lg bg-brand text-[14px] font-bold tracking-[-0.28px] text-brand-foreground md:hidden"
      >
        <AddAssetIcon className="size-[17px]" />
        Add Asset
      </Link>
    </main>
  );
}
