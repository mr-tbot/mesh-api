/**
 * Meshtastic channel plugin for OpenClaw.
 *
 * Registers "meshtastic" as a messaging channel so OpenClaw can send
 * outbound messages to the LoRa mesh via MESH-API.
 */

import type { MeshApiClient } from "./mesh-api-client.js";
import type { MeshtasticPluginConfig } from "./index.js";
import type { ChannelPlugin, PluginConfig } from "./types.js";

/**
 * Build the channel plugin object that gets passed to
 * `api.registerChannel({ plugin })`.
 */
export function createMeshtasticChannel(
  client: MeshApiClient,
  cfg: Required<MeshtasticPluginConfig>
): ChannelPlugin {
  return {
    id: "meshtastic",

    meta: {
      id: "meshtastic",
      label: "Meshtastic",
      selectionLabel: "Meshtastic (MESH-API)",
      docsPath: "/channels/meshtastic",
      docsLabel: "meshtastic",
      blurb:
        "LoRa mesh network bridge via MESH-API — send/receive messages, list nodes, relay emergencies.",
      order: 80,
      aliases: ["mesh", "lora", "mesh-api"],
    },

    capabilities: {
      chatTypes: ["direct", "group"],
    },

    config: {
      /**
       * List configured account IDs.  We use a single "default" account
       * unless the user has created multiple entries under
       * `channels.meshtastic.accounts`.
       */
      listAccountIds: (appCfg: PluginConfig): string[] => {
        const accounts =
          (appCfg.channels?.meshtastic as Record<string, unknown> | undefined)?.accounts;
        if (accounts && typeof accounts === "object") {
          return Object.keys(accounts as Record<string, unknown>);
        }
        return ["default"];
      },

      resolveAccount: (appCfg: PluginConfig, accountId?: string): Record<string, unknown> => {
        const channelCfg = appCfg.channels?.meshtastic as Record<string, unknown> | undefined;
        const accounts = channelCfg?.accounts as Record<string, Record<string, unknown>> | undefined;
        const id = accountId ?? "default";
        return accounts?.[id] ?? { accountId: id };
      },
    },

    outbound: {
      deliveryMode: "direct",

      /**
       * Send a text message to the Meshtastic mesh via MESH-API.
       *
       * `recipientId` is mapped to a Meshtastic node ID (direct message).
       * If absent, the message is broadcast on the default channel.
       */
      sendText: async ({ text, recipientId }) => {
        try {
          if (recipientId) {
            await client.sendMessage(text, { nodeId: recipientId, direct: true });
          } else {
            await client.sendMessage(text, { channelIndex: cfg.defaultChannel });
          }
          return { ok: true };
        } catch (err) {
          const message = err instanceof Error ? err.message : String(err);
          return { ok: false, error: message };
        }
      },
    },
  };
}
