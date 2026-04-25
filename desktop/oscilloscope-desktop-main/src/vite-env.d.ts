/// <reference types="vite/client" />

type CaptureResult = {
  ok: boolean;
  result?: unknown;
  error?: string;
};

type PythonEvent = {
  event: string;
  payload: Record<string, unknown>;
};

declare global {
  interface Window {
    desktopAPI: {
      pickDll: () => Promise<{ ok: boolean; result?: { dllPath: string }; error?: string }>;
      rpc: (payload: { method: string; params?: Record<string, unknown> }) => Promise<CaptureResult>;
      systemInfo: () => Promise<{ ok: boolean; result?: { electronArch: string }; error?: string }>;
      onPythonEvent: (cb: (evt: PythonEvent) => void) => () => void;
    };
  }
}

export {};
