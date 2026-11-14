/** Shown when the picked file cannot be an invoice or receipt. */
export const NOT_A_RECEIPT_FILE_MESSAGE =
  "Please upload only an invoice or receipt, as a PDF, JPG or PNG file.";

const ACCEPTED_TYPES = new Set(["application/pdf", "image/jpeg", "image/png", "image/webp"]);
const ACCEPTED_EXTENSIONS = /\.(pdf|jpe?g|png|webp)$/i;

/**
 * Whether the file could be an invoice or receipt: a PDF or a photo / scan of
 * one. The picker's `accept` already steers people, but a dropped file skips
 * it, so this runs again before anything is uploaded. The browser sometimes
 * reports no type at all, so the extension is the fallback.
 */
export function isReceiptFile(file: File): boolean {
  return file.type ? ACCEPTED_TYPES.has(file.type) : ACCEPTED_EXTENSIONS.test(file.name);
}
