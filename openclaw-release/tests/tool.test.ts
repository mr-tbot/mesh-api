/**
 * Tests for the meshtastic_mesh agent tool.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { createMeshtasticTool } from "../src/tool.js";
import type { MeshApiClient } from "../src/mesh-api-client.js";
import type { MeshtasticPluginConfig } from "../src/index.js";

function mockClient(overrides: Partial<MeshApiClient> = {}): MeshApiClient {
  return {
    baseUrl: "http://localhost:5000",
    getNodes: vi.fn().mockResolvedValue([
      { id: "!a1b2c3d4", shortName: "TBot", longName: "TBot Base Station" },
    ]),
    getMessages: vi.fn().mockResolvedValue([
      { sender: "!a1b2c3d4", senderName: "TBot", text: "Hello", timestamp: 1700000000, channel: 0 },
    ]),
    getConnectionStatus: vi.fn().mockResolvedValue({ status: "connected", error: null }),
    getCommandsInfo: vi.fn().mockResolvedValue([
      { command: "/ping", description: "Check if the bot is online" },
    ]),
    sendMessage: vi.fn().mockResolvedValue({ status: "sent" }),
    ...overrides,
  } as unknown as MeshApiClient;
}

const defaultCfg: Required<MeshtasticPluginConfig> = {
  meshApiUrl: "http://localhost:5000",
  meshApiKey: "",
  agentName: "mesh-api",
  defaultChannel: 0,
  pollEnabled: false,
  pollIntervalSeconds: 30,
  forwardEmergency: true,
  maxMessageLength: 200,
  timeoutMs: 15000,
};

describe("meshtastic_mesh tool", () => {
  afterEach(() => vi.restoreAllMocks());

  it("list_nodes returns nodes", async () => {
    const client = mockClient();
    const tool = createMeshtasticTool(client, defaultCfg);
    const result = (await tool.handler({ action: "list_nodes" })) as Record<string, unknown>;

    expect(result.ok).toBe(true);
    expect(result.count).toBe(1);
    expect(client.getNodes).toHaveBeenCalled();
  });

  it("get_messages returns messages", async () => {
    const client = mockClient();
    const tool = createMeshtasticTool(client, defaultCfg);
    const result = (await tool.handler({ action: "get_messages" })) as Record<string, unknown>;

    expect(result.ok).toBe(true);
    expect(result.count).toBe(1);
  });

  it("get_status returns connection info", async () => {
    const client = mockClient();
    const tool = createMeshtasticTool(client, defaultCfg);
    const result = (await tool.handler({ action: "get_status" })) as Record<string, unknown>;

    expect(result.ok).toBe(true);
    expect(result.status).toBe("connected");
  });

  it("send_message validates empty message", async () => {
    const client = mockClient();
    const tool = createMeshtasticTool(client, defaultCfg);
    const result = (await tool.handler({ action: "send_message", message: "" })) as Record<string, unknown>;

    expect(result.ok).toBe(false);
    expect(result.error).toContain("message is required");
  });

  it("send_message validates invalid node_id", async () => {
    const client = mockClient();
    const tool = createMeshtasticTool(client, defaultCfg);
    const result = (await tool.handler({
      action: "send_message",
      message: "Hi",
      node_id: "badid",
    })) as Record<string, unknown>;

    expect(result.ok).toBe(false);
    expect(result.error).toContain("Invalid node_id");
  });

  it("send_message succeeds with valid params", async () => {
    const client = mockClient();
    const tool = createMeshtasticTool(client, defaultCfg);
    const result = (await tool.handler({
      action: "send_message",
      message: "Hello TBot",
      node_id: "!a1b2c3d4",
    })) as Record<string, unknown>;

    expect(result.ok).toBe(true);
    expect(client.sendMessage).toHaveBeenCalledWith("Hello TBot", {
      nodeId: "!a1b2c3d4",
      direct: true,
      channelIndex: undefined,
    });
  });

  it("send_message warns when message exceeds max length", async () => {
    const client = mockClient();
    const tool = createMeshtasticTool(client, defaultCfg);
    const longMsg = "x".repeat(250);
    const result = (await tool.handler({
      action: "send_message",
      message: longMsg,
    })) as Record<string, unknown>;

    expect(result.ok).toBe(true);
    expect(result.warning).toContain("chunked");
  });

  it("unknown action returns error", async () => {
    const client = mockClient();
    const tool = createMeshtasticTool(client, defaultCfg);
    const result = (await tool.handler({ action: "do_magic" })) as Record<string, unknown>;

    expect(result.ok).toBe(false);
    expect(result.error).toContain("Unknown action");
  });
});
