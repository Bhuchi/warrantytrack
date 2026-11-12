"use client";

import { useEffect, useState } from "react";

import { getAssets } from "./getAssets";

/**
 * "128 registered in SIIT Organization", the line under the Assets title.
 *
 * A client component because the count comes from GET /assets, and API calls
 * run in the browser (see getAssets.ts). Shows "…" until the answer arrives,
 * and keeps showing it if the request fails; AssetsList shows the error.
 */
export default function AssetCount({ workspaceName }: { workspaceName: string }) {
  const [total, setTotal] = useState<number | null>(null);

  // The empty [] means "run once, after the first render".
  useEffect(() => {
    getAssets()
      .then((result) => setTotal(result.total))
      .catch(() => setTotal(null));
  }, []);

  return (
    <>
      {total ?? "…"} registered in {workspaceName}
    </>
  );
}
