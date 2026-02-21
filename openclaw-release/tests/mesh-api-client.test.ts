/**
 * Tests for MeshApiClient.
 *
 * Uses Vitest with mocked fetch to verify all MESH-API REST calls.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { MeshApiClient } from "../src/mesh-api-client.js";

// ── Test helpers ──────────────────────────────────────────────────────

function mockFetchOk(body: unknown): void {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(body),
      text: () => Promise.resolve(JSON.stringify(body)),
    })
  );
}

function mockFetchError(status: number, body: string): void {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status,
      text: () => Promise.resolve(body),
    })
  );
}

function createClient(overrides?: Partial<{ meshApiUrl: string; meshApiKey: string; timeoutMs: number }>) {
  return new MeshApiClient({
    meshApiUrl: overrides?.meshApiUrl ?? "http://localhost:5000",
    meshApiKey: overrides?.meshApiKey ?? "",
    timeoutMs: overrides?.timeoutMs ?? 15000,
  });
}

// ── Tests ─────────────────────────────────────────────────────────────

describe("MeshApiClient", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── getNodes ──────────────────────────────────────────────────

  describe("getNodes()", () => {
    it("returns parsed node list", async () => {
      const nodes = [
        { id: "!a1b2c3d4", shortName: "TBot", longName: "TBot Base Station" },
        { id: "!e5f6a7b8", shortName: "Hike", longName: "Hiker Node" },
      ];
      mockFetchOk(nodes);

      const client = createClient();
      const result = await client.getNodes();

      expect(result).toEqual(nodes);
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:5000/nodes",
        expect.objectContaining({ method: "GET" })
      );
    });

    it("throws on HTTP error", async () => {
      mockFetchError(500, "Internal Server Error");
      const client = createClient();
      await expect(client.getNodes()).rejects.toThrow("MESH-API GET /nodes responded 500");
    });
  });

  // ── getMessages ───────────────────────────────────────────────

  describe("getMessages()", () => {
    it("returns parsed message list", async () => {
      const messages = [
        { sender: "!a1b2c3d4", senderName: "TBot", text: "Hello", timestamp: 1700000000, channel: 0 },
      ];
      mockFetchOk(messages);

      const client = createClient();
      const result = await client.getMessages();

      expect(result).toEqual(messages);
    });
  });

  // ── getConnectionStatus ───────────────────────────────────────

  describe("getConnectionStatus()", () => {
    it("returns connected status", async () => {
      mockFetchOk({ status: "connected", error: null });

      const client = createClient();
      const result = await client.getConnectionStatus();

      expect(result.status).toBe("connected");
      expect(result.error).toBeNull();
    });

    it("returns disconnected status with error", async () => {
      mockFetchOk({ status: "disconnected", error: "serial port closed" });

      const client = createClient();
      const result = await client.getConnectionStatus();

      expect(result.status).toBe("disconnected");
      expect(result.error).toBe("serial port closed");
    });
  });

  // ── sendMessage ───────────────────────────────────────────────

  describe("sendMessage()", () => {
    it("sends a broadcast message", async () => {
      mockFetchOk({ status: "sent", message: "Hello mesh!" });

      const client = createClient();
      const result = await client.sendMessage("Hello mesh!", { channelIndex: 0 });

      expect(result.status).toBe("sent");
      expect(fetch).toHaveBeenCalledWith(
        "http://localhost:5000/send",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ message: "Hello mesh!", channel_index: 0 }),
        })
      );
    });

    it("sends a direct message with node_id", async () => {
      mockFetchOk({ status: "sent", to: "!a1b2c3d4", direct: true });

      const client = createClient();
      const result = await client.sendMessage("Hello TBot", {
        nodeId: "!a1b2c3d4",
        direct: true,
      });

      expect(result.status).toBe("sent");
      const body = JSON.parse((fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body);
      expect(body.node_id).toBe("!a1b2c3d4");
      expect(body.direct).toBe(true);
    });
  });

  // ── getCommandsInfo ───────────────────────────────────────────

  describe("getCommandsInfo()", () => {
    it("returns command list", async () => {
      const commands = [
        { command: "/ping", description: "Check if the bot is online" },
        { command: "/nodes", description: "List online mesh nodes" },
      ];
      mockFetchOk(commands);

      const client = createClient();
      const result = await client.getCommandsInfo();

      expect(result).toEqual(commands);
    });
  });

  // ── Auth headers ──────────────────────────────────────────────

  describe("auth headers", () => {
    it("includes Authorization header when apiKey is set", async () => {
      mockFetchOk([]);

      const client = createClient({ meshApiKey: "test-key-123" });
      await client.getNodes();

      const headers = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].headers;
      expect(headers["Authorization"]).toBe("Bearer test-key-123");
    });

    it("omits Authorization header when apiKey is empty", async () => {
      mockFetchOk([]);

      const client = createClient({ meshApiKey: "" });
      await client.getNodes();

      const headers = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].headers;
      expect(headers["Authorization"]).toBeUndefined();
    });
  });

  // ── URL handling ──────────────────────────────────────────────

  describe("URL handling", () => {
    it("strips trailing slashes from baseUrl", () => {
      const client = createClient({ meshApiUrl: "http://localhost:5000///" });
      expect(client.baseUrl).toBe("http://localhost:5000");
    });
  });
});
