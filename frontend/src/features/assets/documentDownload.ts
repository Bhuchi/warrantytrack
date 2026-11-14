import { ApiError, api } from "@/lib/api";
import type { DocumentDownload } from "@/types";

/**
 * A short-lived link to open an uploaded receipt or invoice.
 * GET /documents/{id}/download (contract: GitHub #95).
 *
 * USE_MOCK returns a sample receipt from /public instead of calling the API,
 * for working on the page without a backend.
 */
const USE_MOCK = false;

export async function getDocumentDownloadUrl(id: string): Promise<string> {
  if (USE_MOCK) {
    await new Promise((resolve) => setTimeout(resolve, 300));
    return "/mock/sample-receipt.png";
  }
  try {
    const link = await api.get<DocumentDownload>(`/documents/${encodeURIComponent(id)}/download`);
    return link.url;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      throw new Error("This file is no longer available.");
    }
    throw new Error("Couldn't open the file. Check your connection and try again.");
  }
}
