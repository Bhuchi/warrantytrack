import type { Metadata } from "next";

import AddAssetWizard from "@/features/add-asset/AddAssetWizard";

export const metadata: Metadata = {
  title: "Add Asset",
};

/** /assets/new. The page itself stays on the server; the wizard inside runs in the browser. */
export default function AddAssetPage() {
  return (
    <main className="flex flex-1 flex-col px-5 pt-4 pb-6 md:px-8 md:pt-6 md:pb-8">
      <AddAssetWizard />
    </main>
  );
}
