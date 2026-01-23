/**
 * WebSocket message type definitions
 */

export type WSMessageType =
  | "status"
  | "progress"
  | "log"
  | "batch"
  | "error"
  | "connected"
  | "disconnected";

export interface WSStatusMessage {
  type: "status";
  job_id: string;
  status: string;
  progress: number;
  message?: string;
  error?: string;
}

export interface WSProgressMessage {
  type: "progress";
  job_id?: string;
  percent: number;
  line: string;
}

export interface WSLogMessage {
  type: "log";
  job_id?: string;
  line: string;
  timestamp?: string;
}

export interface WSBatchMessage {
  type: "batch";
  messages: WSMessage[];
  count: number;
}

export interface WSErrorMessage {
  type: "error";
  message: string;
  code?: number;
}

export interface WSConnectedMessage {
  type: "connected";
  job_id: string;
}

export interface WSDisconnectedMessage {
  type: "disconnected";
  reason?: string;
}

export type WSMessage =
  | WSStatusMessage
  | WSProgressMessage
  | WSLogMessage
  | WSBatchMessage
  | WSErrorMessage
  | WSConnectedMessage
  | WSDisconnectedMessage;

// Type guard functions
export function isStatusMessage(msg: WSMessage): msg is WSStatusMessage {
  return msg.type === "status";
}

export function isProgressMessage(msg: WSMessage): msg is WSProgressMessage {
  return msg.type === "progress";
}

export function isLogMessage(msg: WSMessage): msg is WSLogMessage {
  return msg.type === "log";
}

export function isBatchMessage(msg: WSMessage): msg is WSBatchMessage {
  return msg.type === "batch";
}

export function isErrorMessage(msg: WSMessage): msg is WSErrorMessage {
  return msg.type === "error";
}

// WebSocket connection state
export type WSConnectionState =
  | "connecting"
  | "connected"
  | "disconnected"
  | "reconnecting"
  | "failed";

export interface WSConnection {
  state: WSConnectionState;
  lastConnected?: Date;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
}
