/**
 * API Client
 * Axios-based API client with authentication, error handling, and retry logic
 */

import axios, {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from "axios";
import { ZodSchema } from "zod";
import { API_URL } from "@/lib/env";

// Token storage
let authToken: string | null = null;

/**
 * Set the authentication token for API requests
 */
export function setAuthToken(token: string): void {
  authToken = token;
}

/**
 * Clear the authentication token
 */
export function clearAuthToken(): void {
  authToken = null;
}

/**
 * Get the current authentication token
 */
export function getAuthToken(): string | null {
  return authToken;
}

/**
 * Custom API Error class with structured error information
 */
export class ApiError extends Error {
  public readonly status: number;
  public readonly statusText: string;
  public readonly data: unknown;
  public readonly isNetworkError: boolean;
  public readonly isTimeoutError: boolean;

  constructor(options: {
    message: string;
    status?: number;
    statusText?: string;
    data?: unknown;
    isNetworkError?: boolean;
    isTimeoutError?: boolean;
  }) {
    super(options.message);
    this.name = "ApiError";
    this.status = options.status ?? 0;
    this.statusText = options.statusText ?? "";
    this.data = options.data;
    this.isNetworkError = options.isNetworkError ?? false;
    this.isTimeoutError = options.isTimeoutError ?? false;
  }
}

/**
 * Create the Axios instance with base configuration
 */
function createApiClient(): AxiosInstance {
  const instance = axios.create({
    baseURL: API_URL,
    timeout: 30000, // 30 second default timeout
    headers: {
      "Content-Type": "application/json",
    },
  });

  // Request interceptor - add auth token
  instance.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      if (authToken && config.headers) {
        config.headers.Authorization = `Bearer ${authToken}`;
      }
      return config;
    },
    (error: AxiosError) => {
      return Promise.reject(error);
    }
  );

  // Response interceptor - handle errors
  instance.interceptors.response.use(
    (response: AxiosResponse) => {
      return response;
    },
    (error: AxiosError) => {
      // Handle 401 - clear token
      if (error.response?.status === 401) {
        clearAuthToken();
      }

      // Convert to ApiError
      if (error.response) {
        // Server responded with error status
        const data = error.response.data as { detail?: string } | undefined;
        throw new ApiError({
          message: data?.detail ?? error.message ?? "Request failed",
          status: error.response.status,
          statusText: error.response.statusText,
          data: error.response.data,
          isNetworkError: false,
          isTimeoutError: false,
        });
      } else if (error.code === "ECONNABORTED" || error.message?.includes("timeout")) {
        // Timeout error
        throw new ApiError({
          message: "Request timed out",
          isNetworkError: false,
          isTimeoutError: true,
        });
      } else {
        // Network error or other issue
        throw new ApiError({
          message: error.message ?? "Network error",
          isNetworkError: true,
          isTimeoutError: false,
        });
      }
    }
  );

  return instance;
}

// Export the configured axios instance
export const apiClient = createApiClient();

/**
 * Retry configuration options
 */
export interface RetryOptions {
  maxRetries?: number;
  retryDelay?: number;
  retryOn?: number[];
}

/**
 * API request options with generic type support
 */
export interface ApiRequestOptions<T = unknown> {
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  url: string;
  data?: unknown;
  params?: Record<string, string | number | boolean | undefined>;
  timeout?: number;
  retry?: RetryOptions;
  schema?: ZodSchema<T>;
}

/**
 * Sleep utility for retry delay
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Determine if an error is retryable
 */
function isRetryableError(error: unknown, retryOn: number[]): boolean {
  if (error instanceof ApiError) {
    // Network errors are retryable
    if (error.isNetworkError || error.isTimeoutError) {
      return true;
    }
    // Check if status is in retry list
    return retryOn.includes(error.status);
  }
  return false;
}

/**
 * Type-safe API request function with optional Zod validation and retry logic
 */
export async function apiRequest<T>(options: ApiRequestOptions<T>): Promise<T> {
  const {
    method,
    url,
    data,
    params,
    timeout,
    retry,
    schema,
  } = options;

  const maxRetries = retry?.maxRetries ?? 0;
  const retryDelay = retry?.retryDelay ?? 1000;
  const retryOn = retry?.retryOn ?? [500, 502, 503, 504];

  let lastError: unknown;
  let attempts = 0;

  while (attempts <= maxRetries) {
    try {
      const config: AxiosRequestConfig = {
        method,
        url,
        data,
        params,
      };

      if (timeout !== undefined) {
        config.timeout = timeout;
      }

      const response = await apiClient.request<T>(config);

      // Validate with Zod schema if provided
      if (schema) {
        const parsed = schema.safeParse(response.data);
        if (!parsed.success) {
          throw new ApiError({
            message: `Response validation failed: ${parsed.error.message}`,
            status: 0,
            data: parsed.error.issues,
          });
        }
        return parsed.data;
      }

      return response.data;
    } catch (error) {
      lastError = error;
      attempts++;

      // Check if we should retry
      if (attempts <= maxRetries && isRetryableError(error, retryOn)) {
        await sleep(retryDelay * attempts); // Exponential backoff
        continue;
      }

      // No more retries, throw the error
      break;
    }
  }

  throw lastError;
}

/**
 * Convenience methods for common HTTP verbs
 */
export const api = {
  get: <T>(url: string, params?: Record<string, string | number | boolean | undefined>) =>
    apiRequest<T>({ method: "GET", url, params }),

  post: <T>(url: string, data?: unknown) =>
    apiRequest<T>({ method: "POST", url, data }),

  put: <T>(url: string, data?: unknown) =>
    apiRequest<T>({ method: "PUT", url, data }),

  patch: <T>(url: string, data?: unknown) =>
    apiRequest<T>({ method: "PATCH", url, data }),

  delete: <T>(url: string) =>
    apiRequest<T>({ method: "DELETE", url }),
};
