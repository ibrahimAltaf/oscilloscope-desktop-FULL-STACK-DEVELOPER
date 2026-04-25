// Global window.desktopAPI shape (injected by preload via contextBridge)
declare global {
  interface Window {
    desktopAPI: {
      pickDll: () => Promise<{ ok: boolean; result?: { dllPath: string }; error?: string }>;
      rpc: (payload: { method: string; params?: Record<string, unknown> }) => Promise<{
        ok: boolean;
        result?: Record<string, unknown>;
        error?: string;
      }>;
      systemInfo: () => Promise<{ ok: boolean; result?: { electronArch: string } }>;
      openExternal: (url: string) => Promise<void>;
      onPythonEvent: (cb: (evt: { event: string; payload: Record<string, unknown> }) => void) => () => void;
    };
  }
}

export type ServiceStatus = {
  dll_path: string;
  dll_found: boolean;
  dll_arch: string;
  python_arch: string;
  electron_arch: string;
  dll_loaded: boolean;
  exports: string[] | null;
  device_connected: boolean;
  device_detected: boolean;
  capture_running: boolean;
  capture_started: boolean;
  real_data_received: boolean;
  zero_data_warning: boolean;
  samples_received: number;
  last_min: number | null;
  last_max: number | null;
  last_variance: number | null;
  last_error: string | null;
  sdk_error_code: number | null;
  export_count: number;
  mapped_functions: Record<string, string> | null;
  final_status: string;
  verification_reason: string;
};

export type SampleBatch = {
  timestamp_unix: number;
  samples: number[];
  count: number;
  min: number;
  max: number;
  variance: number;
};

export type UiLog = {
  ts: number;
  level: "info" | "warning" | "error";
  message: string;
};
