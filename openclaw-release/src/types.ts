/**
 * Lightweight type definitions for the OpenClaw Plugin API surface used by
 * this plugin.  These are intentionally minimal — they cover only the parts
 * we call.  When OpenClaw publishes a first-party SDK / type package, these
 * should be replaced with an import from that package.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

// ── Logger ────────────────────────────────────────────────────────────

export interface Logger {
  info(msg: string, ...args: any[]): void;
  warn(msg: string, ...args: any[]): void;
  error(msg: string, ...args: any[]): void;
  debug(msg: string, ...args: any[]): void;
}

// ── Config (read-only view) ───────────────────────────────────────────

export interface PluginConfig {
  plugins?: {
    entries?: Record<
      string,
      {
        enabled?: boolean;
        config?: Record<string, unknown>;
      }
    >;
  };
  channels?: Record<string, unknown>;
  [key: string]: unknown;
}

// ── Channel plugin types ──────────────────────────────────────────────

export interface ChannelMeta {
  id: string;
  label: string;
  selectionLabel?: string;
  docsPath?: string;
  docsLabel?: string;
  blurb?: string;
  order?: number;
  aliases?: string[];
}

export interface ChannelCapabilities {
  chatTypes: ("direct" | "group")[];
}

export interface ChannelOutbound {
  deliveryMode: "direct" | "queue";
  sendText: (ctx: SendTextContext) => Promise<{ ok: boolean; error?: string }>;
}

export interface SendTextContext {
  text: string;
  accountId?: string;
  recipientId?: string;
  channel?: string;
  [key: string]: unknown;
}

export interface ChannelConfigHelpers {
  listAccountIds: (cfg: PluginConfig) => string[];
  resolveAccount: (cfg: PluginConfig, accountId?: string) => Record<string, unknown>;
}

export interface ChannelPlugin {
  id: string;
  meta: ChannelMeta;
  capabilities: ChannelCapabilities;
  config: ChannelConfigHelpers;
  outbound: ChannelOutbound;
}

// ── Agent tool types ──────────────────────────────────────────────────

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  handler: (args: Record<string, unknown>) => Promise<unknown>;
}

// ── Auto-reply command types ──────────────────────────────────────────

export interface CommandContext {
  senderId?: string;
  channel?: string;
  isAuthorizedSender?: boolean;
  args?: string;
  commandBody?: string;
  config?: PluginConfig;
}

export interface CommandDefinition {
  name: string;
  description: string;
  acceptsArgs?: boolean;
  requireAuth?: boolean;
  handler: (ctx: CommandContext) => Promise<{ text: string }> | { text: string };
}

// ── Background service types ──────────────────────────────────────────

export interface ServiceDefinition {
  id: string;
  start: () => void | Promise<void>;
  stop: () => void | Promise<void>;
}

// ── Top-level Plugin API ──────────────────────────────────────────────

export interface PluginApi {
  logger: Logger;
  config: PluginConfig;
  registerChannel: (opts: { plugin: ChannelPlugin }) => void;
  registerTool: (tool: ToolDefinition) => void;
  registerCommand: (cmd: CommandDefinition) => void;
  registerService: (svc: ServiceDefinition) => void;
}
