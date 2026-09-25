export type BootStage =
  | "idle"
  | "loading-pyodide"
  | "loading-core"
  | "ready"
  | "error";

interface Pending {
  resolve: (value: unknown) => void;
  reject: (error: Error) => void;
}

interface WorkerResponse {
  id?: number;
  ok?: boolean;
  data?: unknown;
  error?: string;
  type?: string;
  stage?: BootStage;
  version?: string;
}

class PyClient {
  private worker: Worker;
  private pending = new Map<number, Pending>();
  private nextId = 1;
  private statusListeners = new Set<(stage: BootStage, detail?: string) => void>();
  version: string | null = null;

  constructor() {
    this.worker = new Worker(new URL("./worker.ts", import.meta.url), {
      type: "module",
    });
    this.worker.onmessage = (event: MessageEvent<WorkerResponse>) => {
      const message = event.data;
      if (message.type === "status" && message.stage) {
        this.statusListeners.forEach((listener) => listener(message.stage!));
        return;
      }
      if (message.type === "ready") {
        this.version = message.version ?? null;
        this.statusListeners.forEach((listener) => listener("ready"));
        return;
      }
      if (message.type === "boot-error") {
        this.statusListeners.forEach((listener) =>
          listener("error", message.error ?? "Unknown boot error"),
        );
        return;
      }
      if (typeof message.id === "number") {
        const pending = this.pending.get(message.id);
        if (!pending) return;
        this.pending.delete(message.id);
        if (message.ok) {
          pending.resolve(message.data);
        } else {
          pending.reject(new Error(message.error ?? "Unknown bridge error"));
        }
      }
    };
    this.worker.onerror = (event) => {
      this.statusListeners.forEach((listener) => listener("error", event.message));
    };
  }

  onStatus(listener: (stage: BootStage, detail?: string) => void): () => void {
    this.statusListeners.add(listener);
    return () => this.statusListeners.delete(listener);
  }

  request<T>(action: string, payload: Record<string, unknown> = {}): Promise<T> {
    const id = this.nextId++;
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, {
        resolve: (value) => resolve(value as T),
        reject,
      });
      this.worker.postMessage({ id, action, payload });
    });
  }
}

export const pyClient = new PyClient();
