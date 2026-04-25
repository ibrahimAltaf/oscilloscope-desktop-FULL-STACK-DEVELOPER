import path from "node:path";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { randomUUID } from "node:crypto";

export type RpcResult<T = unknown> = { ok: boolean; result?: T; error?: string };
export type BridgeEvent =
  | { event: "status"; payload: Record<string, unknown> }
  | { event: "sample_batch"; payload: Record<string, unknown> }
  | { event: "log"; payload: Record<string, unknown> }
  | { event: "rpc_response"; payload: { request_id: string; ok: boolean; result?: unknown; error?: string } };

type Resolver = (value: RpcResult) => void;

export class PythonBridge {
  private proc: ChildProcessWithoutNullStreams | null = null;
  private lineBuffer = "";
  private readonly pending = new Map<string, Resolver>();
  private readonly listeners = new Set<(event: BridgeEvent) => void>();

  public start(): void {
    if (this.proc) return;
    const pythonBin = process.env.OSC_PYTHON_BIN || "python";

    // dev: two levels up from desktop/oscilloscope-desktop-main → project root
    const devRoot = path.resolve(process.cwd(), "..", "..");
    const devServicePath = path.join(devRoot, "sdk", "hardware_service.py");

    // packaged: Electron extracts extra resources to process.resourcesPath
    const packagedRoot = process.resourcesPath;
    const packagedServicePath = path.join(packagedRoot, "sdk", "hardware_service.py");

    const isProduction = process.env.NODE_ENV === "production";
    const servicePath = process.env.OSC_HW_SERVICE_PATH || (isProduction ? packagedServicePath : devServicePath);
    const pythonRoot = isProduction ? packagedRoot : devRoot;

    this.proc = spawn(pythonBin, [servicePath], {
      stdio: ["pipe", "pipe", "pipe"],
      // Inject PYTHONPATH so `from sdk.xxx import` and `import sdk` resolve correctly
      env: { ...process.env, PYTHONPATH: pythonRoot },
    });

    this.proc.stdout.on("data", (chunk: Buffer) => this.handleStdout(chunk.toString("utf-8")));
    this.proc.stderr.on("data", (chunk: Buffer) => {
      this.emit({ event: "log", payload: { level: "error", message: chunk.toString("utf-8").trim() } });
    });
    this.proc.on("exit", (code) => {
      this.emit({ event: "log", payload: { level: "error", message: `Python service exited with code ${code}` } });
      this.proc = null;
      for (const [, resolve] of this.pending.entries()) resolve({ ok: false, error: "Python service crashed" });
      this.pending.clear();
    });
  }

  public async stop(): Promise<void> {
    if (!this.proc) return;
    await this.request("shutdown", {});
    this.proc.kill();
    this.proc = null;
  }

  public async request(method: string, params: Record<string, unknown>): Promise<RpcResult> {
    this.start();
    if (!this.proc) return { ok: false, error: "Python service unavailable" };
    const id = randomUUID();
    const payload = JSON.stringify({ id, method, params }) + "\n";
    const promise = new Promise<RpcResult>((resolve) => this.pending.set(id, resolve));
    this.proc.stdin.write(payload);
    return promise;
  }

  public onEvent(listener: (event: BridgeEvent) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(event: BridgeEvent): void {
    for (const listener of this.listeners) listener(event);
  }

  private handleStdout(chunk: string): void {
    this.lineBuffer += chunk;
    const parts = this.lineBuffer.split("\n");
    this.lineBuffer = parts.pop() ?? "";
    for (const line of parts) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        const parsed = JSON.parse(trimmed) as BridgeEvent;
        if (parsed.event === "rpc_response") {
          const resolver = this.pending.get(parsed.payload.request_id);
          if (resolver) {
            this.pending.delete(parsed.payload.request_id);
            resolver({ ok: parsed.payload.ok, result: parsed.payload.result, error: parsed.payload.error });
          }
        } else {
          this.emit(parsed);
        }
      } catch {
        this.emit({ event: "log", payload: { level: "warning", message: `Invalid JSON from python: ${trimmed}` } });
      }
    }
  }
}
