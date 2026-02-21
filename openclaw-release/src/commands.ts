/**
 * Auto-reply slash commands for the meshtastic plugin.
 *
 * These execute without invoking the AI agent — quick status checks
 * that any authorised user can trigger from any OpenClaw channel.
 */

import type { MeshApiClient } from "./mesh-api-client.js";
import type { CommandDefinition } from "./types.js";

export function createMeshCommands(client: MeshApiClient): CommandDefinition[] {
  return [
    // ── /mesh-status ──────────────────────────────────────────────
    {
      name: "mesh-status",
      description: "Check Meshtastic radio connection status via MESH-API",
      acceptsArgs: false,
      requireAuth: true,

      handler: async () => {
        try {
          const status = await client.getConnectionStatus();
          if (status.status === "connected") {
            return { text: `✅ Mesh radio is connected.` };
          }
          return {
            text: `⚠️ Mesh radio is disconnected${status.error ? `: ${status.error}` : "."}`,
          };
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          return { text: `❌ Could not reach MESH-API: ${msg}` };
        }
      },
    },

    // ── /mesh-nodes ───────────────────────────────────────────────
    {
      name: "mesh-nodes",
      description: "List visible nodes on the Meshtastic mesh network",
      acceptsArgs: false,
      requireAuth: true,

      handler: async () => {
        try {
          const nodes = await client.getNodes();
          if (nodes.length === 0) {
            return { text: "No mesh nodes visible." };
          }
          const lines = nodes.map(
            (n) => `• ${n.longName ?? n.shortName ?? "?"} (${n.id})`
          );
          return {
            text: `📡 ${nodes.length} node(s) on mesh:\n${lines.join("\n")}`,
          };
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          return { text: `❌ Could not reach MESH-API: ${msg}` };
        }
      },
    },

    // ── /mesh-send ────────────────────────────────────────────────
    {
      name: "mesh-send",
      description: "Broadcast a message on the mesh (usage: /mesh-send <text>)",
      acceptsArgs: true,
      requireAuth: true,

      handler: async (ctx) => {
        const text = ctx.args?.trim();
        if (!text) {
          return { text: "Usage: /mesh-send <message>" };
        }
        try {
          await client.sendMessage(text);
          return { text: `✅ Sent to mesh: "${text}"` };
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          return { text: `❌ Send failed: ${msg}` };
        }
      },
    },
  ];
}
