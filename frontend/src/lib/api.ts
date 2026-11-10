/**
 * The single door to the backend.
 *
 * Per the frontend conventions, components never call `fetch` directly — they
 * go through this module (usually wrapped in a `features/<domain>/` function or
 * a hook), so auth headers, error shapes, and the base URL stay in one place.
 *
 * ```ts
 * const assets = await api.get<Asset[]>("/assets", { query: { status: "active" } });
 * const created = await api.post<Asset>("/assets", { name: "Laptop" });
 * const health = await api.health();
 * ```
 *
 * Add a named method to the `api` object for each endpoint you build; the
 * generic verbs underneath are there for one-off calls.
 */

import { API_BASE_URL } from "@/lib/config";
import type { HealthResponse } from "@/types";
import type { ApiErrorBody, QueryParams } from "@/types/api";

/** Thrown for any non-2xx response. */
export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export interface RequestOptions extends Omit<RequestInit, "body" | "method"> {
  /** Appended as a query string; `null`/`undefined` entries are skipped. */
  query?: QueryParams;
  /** JSON-serialized automatically, unless it is a `FormData` (file upload). */
  body?: unknown;
}

type TokenProvider = () => string | null | Promise<string | null>;

let tokenProvider: TokenProvider = () => null;

/**
 * Register how the client obtains the Cognito ID token.
 * Call this once from the auth feature so `lib/api` stays auth-agnostic.
 */
export function setAuthTokenProvider(provider: TokenProvider): void {
  tokenProvider = provider;
}

function buildUrl(path: string, query?: QueryParams): string {
  const base = /^https?:\/\//i.test(path)
    ? path
    : `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;

  if (!query) return base;

  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    for (const item of Array.isArray(value) ? value : [value]) {
      if (item === null || item === undefined) continue;
      search.append(key, String(item));
    }
  }

  const qs = search.toString();
  return qs ? `${base}${base.includes("?") ? "&" : "?"}${qs}` : base;
}

function isJson(response: Response): boolean {
  return (
    response.headers.get("content-type")?.includes("application/json") ?? false
  );
}

/** Pull a human-readable message out of FastAPI's `{ "detail": ... }` body. */
function errorMessage(status: number, body: unknown): string {
  const detail = (body as ApiErrorBody | null)?.detail;

  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((entry) => entry.msg).join("; ");
  }
  return `Request failed with status ${status}`;
}

async function request<T>(
  method: string,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { query, body, headers, ...init } = options;

  const isFormData =
    typeof FormData !== "undefined" && body instanceof FormData;

  const requestHeaders = new Headers(headers);
  requestHeaders.set("Accept", "application/json");
  if (body !== undefined && !isFormData && !requestHeaders.has("Content-Type")) {
    // FormData must set its own Content-Type so the multipart boundary is correct.
    requestHeaders.set("Content-Type", "application/json");
  }

  const token = await tokenProvider();
  if (token && !requestHeaders.has("Authorization")) {
    requestHeaders.set("Authorization", `Bearer ${token}`);
  }
  if (!requestHeaders.has("X-Workspace-Id") && typeof document !== "undefined") {
    const workspaceId = document.cookie
      .split("; ")
      .find((cookie) => cookie.startsWith("workspace_id="))
      ?.slice("workspace_id=".length);
    if (workspaceId) requestHeaders.set("X-Workspace-Id", workspaceId);
  }

  const response = await fetch(buildUrl(path, query), {
    ...init,
    method,
    headers: requestHeaders,
    body:
      body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
  });

  if (!response.ok) {
    const errorBody = isJson(response)
      ? await response.json().catch(() => null)
      : await response.text().catch(() => null);
    throw new ApiError(
      response.status,
      errorMessage(response.status, errorBody),
      errorBody,
    );
  }

  if (
    response.status === 204 ||
    response.headers.get("content-length") === "0"
  ) {
    return undefined as T;
  }

  return (isJson(response) ? await response.json() : await response.text()) as T;
}

/**
 * Thin escape hatch kept for compatibility with code written against the
 * original skeleton. Prefer the verbs on `api` below.
 */
export function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const { method, body, ...rest } = init ?? {};
  return request<T>(method ?? "GET", path, { ...rest, body });
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    request<T>("GET", path, options),

  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("POST", path, { ...options, body }),

  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("PUT", path, { ...options, body }),

  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("PATCH", path, { ...options, body }),

  delete: <T = void>(path: string, options?: RequestOptions) =>
    request<T>("DELETE", path, options),

  /** GET /health — proves the frontend can reach the API. */
  health: () => request<HealthResponse>("GET", "/health"),
};
