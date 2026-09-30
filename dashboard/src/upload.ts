import { unzipSync } from "fflate";
import { loadUploadedDataset } from "./db";

export const API_URL = import.meta.env.VITE_API_URL?.replace(/\/$/, "");
export const MAX_UPLOAD_MB = 10;
const TIMEOUT_MS = 120_000;

export class UploadError extends Error {}

/** Send a Hevy CSV to the API and load the returned marts into the in-browser database. */
export async function uploadHevyCsv(file: File): Promise<void> {
  if (!API_URL) throw new UploadError("The upload service is not configured.");
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024)
    throw new UploadError(`That file is larger than the ${MAX_UPLOAD_MB} MB limit.`);

  const body = new FormData();
  body.append("file", file);
  let response: Response;
  try {
    response = await fetch(`${API_URL}/v1/dashboards`, {
      method: "POST",
      body,
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (err) {
    const timedOut = err instanceof DOMException && err.name === "TimeoutError";
    throw new UploadError(
      timedOut ? "Building the dashboard took too long. Try again." : "Could not reach the upload service.",
    );
  }

  if (!response.ok) {
    const detail = await response
      .json()
      .then((j: { detail?: unknown }) => (typeof j.detail === "string" ? j.detail : null))
      .catch(() => null);
    throw new UploadError(detail ?? `The upload failed (${response.status}).`);
  }

  const files = unzipSync(new Uint8Array(await response.arrayBuffer()));
  await loadUploadedDataset(files);
}
