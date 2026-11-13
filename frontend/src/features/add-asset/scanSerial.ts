import { wait } from "./scanReceipt";

/** What reading a serial-number sticker gives back. Frontend-only for now: see below. */
export interface SerialScan {
  /** The serial that was read, or null when nothing could be read. */
  serial: string | null;
  /** Why it failed, when serial is null. */
  error: string | null;
}

/**
 * Reads the serial number from a photo of the sticker on the device.
 *
 * Mock for now: waits 1.5 seconds, then returns the Figma serial. A photo whose
 * name contains "fail" comes back with no serial, so that case can be tested.
 *
 * TODO: docs/api.md has no endpoint for this yet (it only reads serials off the
 * receipt). Asked Bhuchi to add one; Bedrock can read a sticker photo the same
 * way as a receipt. Swap this body for the real call when it exists.
 */
export async function scanSerial(photo: File): Promise<SerialScan> {
  await wait(1500);

  if (photo.name.toLowerCase().includes("fail")) {
    return { serial: null, error: "We couldn't find a serial number in this photo." };
  }

  return { serial: "C02X1234ABC", error: null };
}
