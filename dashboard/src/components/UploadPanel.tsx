import { useRef, useState } from "react";
import { restoreDemoDataset } from "../db";
import { API_URL, MAX_UPLOAD_MB, UploadError, uploadHevyCsv } from "../upload";
import { useDatasetSource } from "../useQuery";

type Status = { kind: "idle" } | { kind: "busy"; name: string } | { kind: "error"; message: string };

/** Lets a visitor swap the demo data for their own Hevy export. Hidden without an API. */
export function UploadPanel() {
  const source = useDatasetSource();
  const input = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  if (!API_URL) return null;

  const busy = status.kind === "busy";

  async function onFile(file: File | undefined) {
    if (!file) return;
    setStatus({ kind: "busy", name: file.name });
    try {
      await uploadHevyCsv(file);
      setStatus({ kind: "idle" });
    } catch (err) {
      setStatus({
        kind: "error",
        message: err instanceof UploadError ? err.message : "Something went wrong while loading your data.",
      });
    } finally {
      if (input.current) input.current.value = "";
    }
  }

  return (
    <section className="upload" aria-label="Use your own data">
      <div>
        <strong>{source === "upload" ? "Showing your Hevy data" : "Try it with your own data"}</strong>
        <p>
          Upload a Hevy CSV export (Settings, Export &amp; Import Data, up to {MAX_UPLOAD_MB} MB). It is processed in
          memory and deleted straight away; nothing is stored. Apple Health data is not included in uploads.
        </p>
        {busy && (
          <p role="status" aria-live="polite">
            Building your dashboard from {status.name}. This takes around ten seconds.
          </p>
        )}
        {status.kind === "error" && (
          <p role="alert" className="upload-error">
            {status.message}
          </p>
        )}
      </div>
      <div className="controls">
        <input
          ref={input}
          type="file"
          accept=".csv,text/csv"
          hidden
          onChange={(e) => void onFile(e.target.files?.[0])}
        />
        <button type="button" className="primary" disabled={busy} onClick={() => input.current?.click()}>
          {busy ? "Working…" : "Upload Hevy CSV"}
        </button>
        {source === "upload" && (
          <button type="button" disabled={busy} onClick={() => void restoreDemoDataset()}>
            Back to demo data
          </button>
        )}
      </div>
    </section>
  );
}
