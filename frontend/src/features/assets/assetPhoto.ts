import { ApiError, api } from "@/lib/api";
import { API_BASE_URL } from "@/lib/config";

/** The photo could not be uploaded. `message` can go straight on the screen. */
export class PhotoUploadError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PhotoUploadError";
  }
}

/** POST /assets/photos/presign response. */
interface PhotoPresignResponse {
  upload_url: string;
  key: string;
}

/**
 * Uploads a box / storage photo and returns its key, to send as
 * `location_image_key` on POST or PATCH /assets (CLOUDAPPG5-147).
 *
 *   1. POST /assets/photos/presign -> { upload_url, key }
 *   2. PUT the photo to upload_url
 *
 * Throws a PhotoUploadError whose message can go straight on the screen.
 */
export async function uploadAssetPhoto(file: File): Promise<string> {
  const contentType = file.type || "application/octet-stream";
  let reserved: PhotoPresignResponse;
  try {
    reserved = await api.post<PhotoPresignResponse>("/assets/photos/presign", {
      filename: file.name,
      content_type: contentType,
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 422) {
      throw new PhotoUploadError("That photo type isn't supported. Use a JPG, PNG, WEBP or HEIC photo.");
    }
    throw new PhotoUploadError("Couldn't upload the photo. Check your connection and try again.");
  }

  // Same split as receipts (scanReceipt.ts): the local dev route is our own
  // API and needs the bearer token; a presigned S3 URL must not get it.
  try {
    if (reserved.upload_url.startsWith(API_BASE_URL)) {
      await api.put(reserved.upload_url, file, { headers: { "Content-Type": contentType } });
    } else {
      const upload = await fetch(reserved.upload_url, {
        method: "PUT",
        headers: { "Content-Type": contentType },
        body: file,
      });
      if (!upload.ok) throw new Error(`upload failed: ${upload.status}`);
    }
  } catch {
    throw new PhotoUploadError("Couldn't upload the photo. Check your connection and try again.");
  }
  return reserved.key;
}
