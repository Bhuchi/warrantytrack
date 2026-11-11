import type { Metadata } from "next";

import EditAssetForm from "@/features/assets/EditAssetForm";

export const metadata: Metadata = {
  title: "Edit Asset",
};

/** /assets/{id}/edit. The form runs in the browser, where the token is. */
export default async function EditAssetPage({
  params,
}: {
  params: Promise<{ assetId: string }>;
}) {
  const { assetId } = await params;
  return (
    <main className="flex flex-1 flex-col px-5 pt-4 pb-6 md:px-8 md:pt-6 md:pb-8">
      <EditAssetForm assetId={assetId} />
    </main>
  );
}
