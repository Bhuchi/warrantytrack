import { api } from "@/lib/api";
import type { AssetListQuery, AssetListResponse } from "@/types/assetList";

/** Matches the API's default page size. */
export const PAGE_SIZE = 20;

/**
 * One page of assets for the Assets List. The one place the screen gets them.
 *
 * GET /assets (docs/api.md "Assets"). The backend does the searching (name,
 * serial or invoice number), the status filter and the paging.
 *
 * Call it from the browser only. In the deployed app the API address is the
 * relative "/api", which a server component cannot fetch.
 */
export function getAssets(query: AssetListQuery = {}): Promise<AssetListResponse> {
  return api.get<AssetListResponse>("/assets", {
    query: {
      // An empty search box means "no search", so it is left out.
      q: query.q?.trim() || undefined,
      status: query.status,
      page: query.page,
      page_size: PAGE_SIZE,
    },
  });
}
