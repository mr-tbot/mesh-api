/**
 * HTTP client for the MESH-API REST endpoints.
 *
 * All calls go through a single class so timeout / auth / error-handling
 * are centralised.  Uses the built-in `fetch` available in Node ≥ 18.
 */

import type { MeshtasticPluginConfig } from "./index.js";

// ── Response types ────────────────────────────────────────────────────

export interface MeshNode {
  id: string;
  shortName: string;
  longName: string;
  [key: string]: unknown;
}

export interface MeshMessage {
  sender?: string;
  senderName?: string;
  text: string;
  timestamp?: number;
  channel?: number;
  [key: string]: unknown;
}

export interface ConnectionStatus {
  status: "connected" | "disconnected";
  error: string | null;
}

export interface SendResult {
  status: string;
  to?: string;
  direct?: boolean;
  message?: string;
  [key: string]: unknown;
}

export interface CommandInfo {
  command: string;
  description: string;
}

// ── Client ────────────────────────────────────────────────────────────

export class MeshApiClient {
  readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly timeoutMs: number;

  constructor(cfg: Pick<Required<MeshtasticPluginConfig>, "meshApiUrl" | "meshApiKey" | "timeoutMs">) {
    this.baseUrl = cfg.meshApiUrl.replace(/\/+$/, "");
    this.apiKey = cfg.meshApiKey;
    this.timeoutMs = cfg.timeoutMs;
  }

  // ── Public methods ──────────────────────────────────────────────

  /** List all visible mesh nodes. */
  async getNodes(): Promise<MeshNode[]> {
    return this.get<MeshNode[]>("/nodes");
  }

  /** Retrieve recent mesh messages. */
  async getMessages(): Promise<MeshMessage[]> {
    return this.get<MeshMessage[]>("/messages");
  }

  /** Check radio connection status. */
  async getConnectionStatus(): Promise<ConnectionStatus> {
    return this.get<ConnectionStatus>("/connection_status");
  }

  /** List registered slash commands on the mesh. */
  async getCommandsInfo(): Promise<CommandInfo[]> {
    return this.get<CommandInfo[]>("/commands_info");
  }

  /**
   * Send a text message to the mesh.
   *
   * @param message  - The text body (will be chunked by MESH-API if too long).
   * @param opts     - Optional targeting: nodeId + direct, or channelIndex.
   */
  async sendMessage(
    message: string,
    opts?: { nodeId?: string; direct?: boolean; channelIndex?: number }
  ): Promise<SendResult> {
    const body: Record<string, unknown> = { message };
    if (opts?.nodeId) {
      body.node_id = opts.nodeId;
      body.direct = opts.direct ?? true;
    }
    if (opts?.channelIndex !== undefined) {
      body.channel_index = opts.channelIndex;
    }
    return this.post<SendResult>("/send", body);
  }

  // ── Internals ───────────────────────────────────────────────────

  private headers(): Record<string, string> {
    const h: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    if (this.apiKey) {
      h["Authorization"] = `Bearer ${this.apiKey}`;
    }
    return h;
  }

  private async get<T>(path: string): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const res = await fetch(url, {
      method: "GET",
      headers: this.headers(),
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    if (!res.ok) {
      throw new Error(`MESH-API GET ${path} responded ${res.status}: ${await res.text()}`);
    }
    return (await res.json()) as T;
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const res = await fetch(url, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    if (!res.ok) {
      throw new Error(`MESH-API POST ${path} responded ${res.status}: ${await res.text()}`);
    }
    return (await res.json()) as T;
  }
}
