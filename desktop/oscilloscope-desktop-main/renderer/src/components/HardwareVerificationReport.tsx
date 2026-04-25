import type { ServiceStatus } from "../types";

type Props = {
  status: ServiceStatus;
  electronArch: string;
};

function toTextReport(status: ServiceStatus, electronArch: string): string {
  const lines = [
    "Hardware Verification Report",
    `DLL path: ${status.dll_path || "N/A"}`,
    `DLL found: ${status.dll_found ? "yes" : "no"}`,
    `DLL architecture: ${status.dll_arch}`,
    `Python architecture: ${status.python_arch}`,
    `Electron architecture: ${electronArch || status.electron_arch || "unknown"}`,
    `Device detected: ${status.device_detected ? "yes" : "no"}`,
    `Device connected: ${status.device_connected ? "yes" : "no"}`,
    `Capture started: ${status.capture_started ? "yes" : "no"}`,
    `Real samples received: ${status.real_data_received ? "yes" : "no"}`,
    `Sample count: ${status.samples_received}`,
    `Min: ${status.last_min ?? "N/A"}`,
    `Max: ${status.last_max ?? "N/A"}`,
    `Variance: ${status.last_variance ?? "N/A"}`,
    `Zero-data warning: ${status.zero_data_warning ? "yes" : "no"}`,
    `SDK error code: ${status.sdk_error_code ?? "N/A"}`,
    `Final status: ${status.final_status}`,
    `Reason: ${status.verification_reason}`,
    "",
    "Mapped SDK functions:",
    JSON.stringify(status.mapped_functions ?? {}, null, 2),
    "",
    "Exports:",
    JSON.stringify(status.exports ?? [], null, 2),
  ];
  return lines.join("\n");
}

function download(name: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function HardwareVerificationReport({ status, electronArch }: Props) {
  const txt = toTextReport(status, electronArch);
  const json = JSON.stringify(
    {
      ...status,
      electron_arch: electronArch || status.electron_arch,
      generated_at: new Date().toISOString(),
    },
    null,
    2,
  );

  return (
    <section className="panel">
      <h3>Hardware Verification Report</h3>
      <div className="grid2">
        <div>DLL path</div>
        <div>{status.dll_path || "N/A"}</div>
        <div>DLL found</div>
        <div>{status.dll_found ? "yes" : "no"}</div>
        <div>DLL architecture</div>
        <div>{status.dll_arch}</div>
        <div>Python architecture</div>
        <div>{status.python_arch}</div>
        <div>Electron architecture</div>
        <div>{electronArch || status.electron_arch || "unknown"}</div>
        <div>Device detected</div>
        <div>{status.device_detected ? "yes" : "no"}</div>
        <div>Device connected</div>
        <div>{status.device_connected ? "yes" : "no"}</div>
        <div>Capture started</div>
        <div>{status.capture_started ? "yes" : "no"}</div>
        <div>Real samples received</div>
        <div>{status.real_data_received ? "yes" : "no"}</div>
        <div>Sample count</div>
        <div>{status.samples_received}</div>
        <div>Min/Max/Variance</div>
        <div>
          {status.last_min ?? "N/A"} / {status.last_max ?? "N/A"} /{" "}
          {status.last_variance != null ? status.last_variance.toFixed(2) : "N/A"}
        </div>
        <div>Zero-data warning</div>
        <div>{status.zero_data_warning ? "yes" : "no"}</div>
        <div>Final status</div>
        <div>{status.final_status}</div>
      </div>
      <div className={status.final_status.includes("NOT") ? "error-box" : "log-info"}>{status.verification_reason}</div>
      <div className="row">
        <button onClick={() => download("hardware-verification-report.txt", txt, "text/plain")}>Export TXT</button>
        <button onClick={() => download("hardware-verification-report.json", json, "application/json")}>Export JSON</button>
      </div>
      <details>
        <summary>Real DLL export list</summary>
        <pre className="logs">{JSON.stringify(status.exports ?? [], null, 2)}</pre>
      </details>
      <details>
        <summary>Final mapped SDK functions</summary>
        <pre className="logs">{JSON.stringify(status.mapped_functions ?? {}, null, 2)}</pre>
      </details>
    </section>
  );
}
