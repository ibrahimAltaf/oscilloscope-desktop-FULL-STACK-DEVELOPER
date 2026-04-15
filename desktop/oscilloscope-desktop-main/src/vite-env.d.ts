/// <reference types="vite/client" />

type CaptureResult = {
  ok: boolean;
  data: unknown;
  status: number;
  error?: string;
};

type AppConfig = {
  apiBase: string;
  wsUrl: string;
};

declare global {
  interface Window {
    electronAPI: {
      startCapture: () => Promise<CaptureResult>;
      stopCapture: () => Promise<CaptureResult>;
      getStatus: () => Promise<CaptureResult>;
      getConfig: () => Promise<AppConfig>;
    };
  }
}

export {};
