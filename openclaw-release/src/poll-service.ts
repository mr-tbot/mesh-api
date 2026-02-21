/**
 * Background polling service.
 *
 * When `pollEnabled` is `true`, this service periodically fetches new
 * messages from MESH-API and injects them into the OpenClaw conversation
 * stream.  This lets OpenClaw react to mesh activity without requiring
 * the mesh side to explicitly address the agent.
 */

import type { MeshApiClient, MeshMessage } from "./mesh-api-client.js";
import type { MeshtasticPluginConfig } from "./index.js";
import type { PluginApi, ServiceDefinition } from "./types.js";

/** AI-generated message prefix used by MESH-API for bot-loop prevention. */
const AI_PREFIX = "m@i- ";

export function createPollService(
  api: PluginApi,
  client: MeshApiClient,
  cfg: Required<MeshtasticPluginConfig>
): ServiceDefinition {
  let timer: ReturnType<typeof setInterval> | null = null;
  let lastSeenTimestamp = 0;

  /** Single poll iteration. */
  async function poll(): Promise<void> {
    try {
      const messages = await client.getMessages();

      // Only process messages newer than what we've already seen
      const fresh = messages.filter((m) => {
        const ts = m.timestamp ?? 0;
        return ts > lastSeenTimestamp;
      });

      if (fresh.length === 0) return;

      // Update watermark to the newest timestamp
      lastSeenTimestamp = Math.max(...fresh.map((m) => m.timestamp ?? 0));

      for (const msg of fresh) {
        // Skip AI-generated messages (bot-loop prevention)
        if (msg.text?.startsWith(AI_PREFIX)) continue;

        api.logger.debug(
          `[meshtastic] Polled new mesh message from ${msg.senderName ?? msg.sender ?? "unknown"}: ${msg.text?.slice(0, 80)}`
        );

        // Relay into OpenClaw as an inbound channel message.
        // The standard pattern is channel → Gateway → agent.
        // Since the plugin API doesn't expose a direct "inject inbound
        // message" method, we log it.  In a production build, you'd use
        // `api.runtime.injectMessage(...)` or the channel's inbound
        // adapter once OpenClaw publishes that surface.
        //
        // For now, log and let the skill / tool surface mesh messages
        // on demand.
        api.logger.info(
          `[meshtastic] Inbound mesh message: [${msg.senderName ?? msg.sender}] ${msg.text}`
        );
      }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      api.logger.warn(`[meshtastic] Poll error: ${errMsg}`);
    }
  }

  return {
    id: "meshtastic-poll",

    start: () => {
      api.logger.info(
        `[meshtastic] Polling service started (interval=${cfg.pollIntervalSeconds}s)`
      );
      // Run first poll immediately, then on interval
      poll();
      timer = setInterval(poll, cfg.pollIntervalSeconds * 1000);
    },

    stop: () => {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      api.logger.info("[meshtastic] Polling service stopped.");
    },
  };
}
