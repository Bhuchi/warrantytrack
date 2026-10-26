/**
 * GET /assets, the Assets List screen (D05 / M05). Mirrors docs/api.md
 * "Assets". Kept apart from assets.ts, which holds the create request.
 */

import type { WarrantyStatus } from "./index";

/** One lightweight row of the list. */
export interface AssetListItem {
  id: string;
  name: string;
  serial_number: string;
  /** "YYYY-MM-DD". */
  purchase_date: string;
  /**
   * "YYYY-MM-DD". Assumed null when the asset has no warranty (status
   * `unknown`); the contract only shows a filled example.
   */
  warranty_end_date: string | null;
  warranty_status: WarrantyStatus;
  assigned_to_user_id: string | null;

  /*
   * Not in the contract yet. The D05 table shows these columns; asked
   * Sirawich (Leg A, /assets) to add them to each list row. Optional until
   * then, so the table shows "—" when they are missing.
   */
  category_name?: string | null;
  vendor_name?: string | null;
  location?: string | null;
}

/** The whole GET /assets response: one page of rows plus paging info. */
export interface AssetListResponse {
  items: AssetListItem[];
  /** Rows matching the filters across all pages, e.g. 128. */
  total: number;
  /** 1-based. */
  page: number;
  page_size: number;
}

/** Query options GET /assets accepts that this screen uses. */
export interface AssetListQuery {
  /** Search text: name, serial or invoice. */
  q?: string;
  /** Leave out for "All". */
  status?: WarrantyStatus;
  page?: number;
}
