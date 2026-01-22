/**
 * Environment variable validation and type-safe access
 * Uses Zod for runtime validation
 */

import { z } from "zod";

const envSchema = z.object({
  // API Configuration
  NEXT_PUBLIC_API_URL: z.string().url().default("http://localhost:8000"),
  NEXT_PUBLIC_WS_URL: z.string().url().default("ws://localhost:8000"),

  // Feature Flags (optional)
  NEXT_PUBLIC_ENABLE_PWA: z
    .string()
    .default("false")
    .transform((val) => val === "true"),
  NEXT_PUBLIC_ENABLE_OFFLINE: z
    .string()
    .default("false")
    .transform((val) => val === "true"),
});

type Env = z.infer<typeof envSchema>;

function getEnv(): Env {
  // Only validate on client-side to avoid issues during SSR
  if (typeof window === "undefined") {
    return {
      NEXT_PUBLIC_API_URL:
        process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
      NEXT_PUBLIC_WS_URL:
        process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000",
      NEXT_PUBLIC_ENABLE_PWA: process.env.NEXT_PUBLIC_ENABLE_PWA === "true",
      NEXT_PUBLIC_ENABLE_OFFLINE:
        process.env.NEXT_PUBLIC_ENABLE_OFFLINE === "true",
    };
  }

  const parsed = envSchema.safeParse({
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL,
    NEXT_PUBLIC_ENABLE_PWA: process.env.NEXT_PUBLIC_ENABLE_PWA,
    NEXT_PUBLIC_ENABLE_OFFLINE: process.env.NEXT_PUBLIC_ENABLE_OFFLINE,
  });

  if (!parsed.success) {
    console.error("Invalid environment variables:", parsed.error.flatten());
    throw new Error("Invalid environment variables");
  }

  return parsed.data;
}

export const env = getEnv();

// Convenience exports
export const API_URL = env.NEXT_PUBLIC_API_URL;
export const WS_URL = env.NEXT_PUBLIC_WS_URL;
export const ENABLE_PWA = env.NEXT_PUBLIC_ENABLE_PWA;
export const ENABLE_OFFLINE = env.NEXT_PUBLIC_ENABLE_OFFLINE;
