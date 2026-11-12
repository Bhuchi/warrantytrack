import type { Metadata } from "next";

import AssetDetail from "@/features/assets/AssetDetail";

export const metadata: Metadata = {
  title: "Asset Details",
};

export default async function AssetDetailPage({
  params,
}: {
  params: Promise<{ assetId: string }>;
}) {
  const { assetId } = await params;
  return <AssetDetail assetId={assetId} />;
}
