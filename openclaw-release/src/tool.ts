/**
 * `meshtastic_mesh` agent tool for OpenClaw.
 *
 * Exposes MESH-API operations as an agent-callable tool so the LLM can
 * interact with the mesh network autonomously (list nodes, send messages,
 * check connectivity, read recent messages).
 */

import type { MeshApiClient } from "./mesh-api-client.js";
import type { MeshtasticPluginConfig } from "./index.js";
import type { ToolDefinition } from "./types.js";

/** Meshtastic node ID pattern: `!` followed by exactly 8 hex characters. */
const NODE_ID_RE = /^![0-9a-fA-F]{8}$/;

export function createMeshtasticTool(
  client: MeshApiClient,
  cfg: Required<MeshtasticPluginConfig>
): ToolDefinition {
  return {
    name: "meshtastic_mesh",
    description:
      "Interact with a Meshtastic LoRa mesh network via MESH-API. " +
      "Actions: list_nodes, get_messages, send_message, get_status, get_commands.",

    parameters: {
      type: "object",
      properties: {
        action: {
          type: "string",
          enum: ["list_nodes", "get_messages", "send_message", "get_status", "get_commands"],
          description: "The mesh operation to perform.",
        },
        message: {
          type: "string",
          description:
            "Text body for send_message. Keep under 200 chars when possible — " +
            "longer messages are chunked into multiple radio packets.",
        },
        node_id: {
          type: "string",
          description:
            "Meshtastic node ID (e.g. !a1b2c3d4) for a direct message. " +
            "If omitted, the message is broadcast on the default channel.",
        },
        channel_index: {
          type: "integer",
          description: "Channel index for broadcast (0-7). Defaults to the configured default channel.",
        },
      },
      required: ["action"],
    },

    handler: async (args: Record<string, unknown>): Promise<unknown> => {
      const action = args.action as string;

      switch (action) {
        // ── List visible mesh nodes ──────────────────────────────
        case "list_nodes": {
          const nodes = await client.getNodes();
          return {
            ok: true,
            count: nodes.length,
            nodes: nodes.map((n) => ({
              id: n.id,
              shortName: n.shortName,
              longName: n.longName,
            })),
          };
        }

        // ── Recent mesh messages ─────────────────────────────────
        case "get_messages": {
          const messages = await client.getMessages();
          return {
            ok: true,
            count: messages.length,
            messages: messages.map((m) => ({
              sender: m.senderName ?? m.sender ?? "unknown",
              text: m.text,
              timestamp: m.timestamp,
              channel: m.channel,
            })),
          };
        }

        // ── Send a message ───────────────────────────────────────
        case "send_message": {
          const text = (args.message as string | undefined) ?? "";
          if (!text.trim()) {
            return { ok: false, error: "message is required for send_message." };
          }

          const nodeId = args.node_id as string | undefined;
          if (nodeId && !NODE_ID_RE.test(nodeId)) {
            return {
              ok: false,
              error: `Invalid node_id "${nodeId}". Must match !XXXXXXXX (8 hex chars).`,
            };
          }

          // Warn (but don't block) if message is long
          const chunkWarning =
            text.length > cfg.maxMessageLength
              ? `Message is ${text.length} chars and will be chunked into multiple radio packets.`
              : undefined;

          const channelIndex =
            (args.channel_index as number | undefined) ?? cfg.defaultChannel;

          const result = await client.sendMessage(text, {
            nodeId,
            direct: !!nodeId,
            channelIndex: nodeId ? undefined : channelIndex,
          });

          return {
            ok: true,
            result,
            ...(chunkWarning ? { warning: chunkWarning } : {}),
          };
        }

        // ── Connection status ────────────────────────────────────
        case "get_status": {
          const status = await client.getConnectionStatus();
          return { ok: true, ...status };
        }

        // ── Registered commands ──────────────────────────────────
        case "get_commands": {
          const commands = await client.getCommandsInfo();
          return { ok: true, count: commands.length, commands };
        }

        default:
          return {
            ok: false,
            error: `Unknown action "${action}". Use: list_nodes, get_messages, send_message, get_status, get_commands.`,
          };
      }
    },
  };
}
