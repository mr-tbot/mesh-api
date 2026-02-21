/**
 * @mesh-api/openclaw-meshtastic
 *
 * OpenClaw channel plugin for Meshtastic LoRa mesh networks.
 * Bridges OpenClaw to a Meshtastic mesh via a running MESH-API instance.
 *
 * Registers:
 *  - Messaging channel ("meshtastic")
 *  - Agent tool ("meshtastic_mesh")
 *  - Auto-reply commands (/mesh-status, /mesh-nodes)
 *  - Background polling service (optional)
 */

import { createMeshtasticChannel } from "./channel.js";
import { createMeshtasticTool } from "./tool.js";
import { createMeshCommands } from "./commands.js";
import { createPollService } from "./poll-service.js";
import { MeshApiClient } from "./mesh-api-client.js";
import type { PluginApi, PluginConfig } from "./types.js";

export { MeshApiClient } from "./mesh-api-client.js";

export interface MeshtasticPluginConfig {
  meshApiUrl: string;
  meshApiKey?: string;
  agentName?: string;
  defaultChannel?: number;
  pollEnabled?: boolean;
  pollIntervalSeconds?: number;
  forwardEmergency?: boolean;
  maxMessageLength?: number;
  timeoutMs?: number;
}

/**
 * Plugin entrypoint — called by the OpenClaw Gateway at load time.
 */
export default function register(api: PluginApi): void {
  const cfg = resolveConfig(api);
  const client = new MeshApiClient(cfg);

  api.logger.info(
    `[meshtastic] Registering plugin — MESH-API at ${cfg.meshApiUrl}, ` +
      `poll=${cfg.pollEnabled ? "on" : "off"}, emergency=${cfg.forwardEmergency ? "on" : "off"}`
  );

  // ── Channel registration ──────────────────────────────────────────
  const channel = createMeshtasticChannel(client, cfg);
  api.registerChannel({ plugin: channel });

  // ── Agent tool registration ───────────────────────────────────────
  const tool = createMeshtasticTool(client, cfg);
  api.registerTool(tool);

  // ── Auto-reply commands ───────────────────────────────────────────
  const commands = createMeshCommands(client);
  for (const cmd of commands) {
    api.registerCommand(cmd);
  }

  // ── Background polling service (opt-in) ───────────────────────────
  if (cfg.pollEnabled) {
    const service = createPollService(api, client, cfg);
    api.registerService(service);
  }
}

// ── Config resolution ─────────────────────────────────────────────────

function resolveConfig(api: PluginApi): Required<MeshtasticPluginConfig> {
  const raw: Partial<MeshtasticPluginConfig> =
    (api.config?.plugins?.entries?.meshtastic?.config as Partial<MeshtasticPluginConfig>) ?? {};

  return {
    meshApiUrl: (raw.meshApiUrl ?? process.env.MESH_API_URL ?? "http://localhost:5000").replace(
      /\/+$/,
      ""
    ),
    meshApiKey: raw.meshApiKey ?? process.env.MESH_API_KEY ?? "",
    agentName: raw.agentName ?? "mesh-api",
    defaultChannel: raw.defaultChannel ?? 0,
    pollEnabled: raw.pollEnabled ?? false,
    pollIntervalSeconds: raw.pollIntervalSeconds ?? 30,
    forwardEmergency: raw.forwardEmergency ?? true,
    maxMessageLength: raw.maxMessageLength ?? 200,
    timeoutMs: raw.timeoutMs ?? 15_000,
  };
}
