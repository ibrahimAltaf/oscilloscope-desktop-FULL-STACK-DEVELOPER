import type { ServiceStatus } from "../types";

type Props = {
  status: ServiceStatus;
};

export function DeviceStatus({ status }: Props) {
  return (
    <section className="panel">
      <h3>Device Status</h3>
      <div className="grid2">
        <div>DLL path</div>
        <div>{status.dll_path || "Not selected"}</div>
        <div>DLL loaded</div>
        <div>{status.dll_loaded ? "Yes" : "No"}</div>
        <div>Device connected</div>
        <div>{status.device_connected ? "Yes" : "No"}</div>
        <div>Capture running</div>
        <div>{status.capture_running ? "Yes" : "No"}</div>
        <div>Real data received</div>
        <div>{status.real_data_received ? "Yes" : "No"}</div>
        <div>Samples received</div>
        <div>{status.samples_received}</div>
        <div>SDK error code</div>
        <div>{status.sdk_error_code ?? "N/A"}</div>
        <div>Export count</div>
        <div>{status.export_count}</div>
      </div>
      {status.last_error && <div className="error-box">Error: {status.last_error}</div>}
      {!status.real_data_received && status.capture_running && (
        <div className="warn-box">No real signal data received</div>
      )}
    </section>
  );
}
