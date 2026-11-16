import { ApiError, api } from "@/lib/api";

/** What reading a serial-number sticker gives back. */
export interface SerialScan {
  /** The serial that was read, or null when nothing could be read. */
  serial: string | null;
  /** Why it failed, when serial is null. */
  error: string | null;
}

/**
 * Reads the serial number from a photo of the sticker through the authenticated
 * backend, which sends the image to Bedrock. The photo is not stored.
 */
export async function scanSerial(photo: File): Promise<SerialScan> {
  try {
    return await api.post<SerialScan>("/assets/scan-serial", photo, {
      headers: { "Content-Type": photo.type || "image/jpeg" },
    });
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 413) {
        return { serial: null, error: "Photo must be 10 MB or smaller." };
      }
      if (error.status === 415 || error.status === 422) {
        return { serial: null, error: error.message };
      }
      if (error.status === 503) {
        return {
          serial: null,
          error: "Serial scanning is unavailable right now. Please enter it manually.",
        };
      }
    }
    return {
      serial: null,
      error: "We couldn't scan this photo. Please try again or enter the serial manually.",
    };
  }
}
