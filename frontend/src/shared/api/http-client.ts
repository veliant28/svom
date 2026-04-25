import { siteConfig } from "@/shared/config/site";
import { createRequestTimingId, logServerTiming } from "@/shared/lib/server-timing";

export type QueryParams = Record<string, string | number | boolean | undefined>;

type RequestOptions = {
  params?: QueryParams;
  headers?: Record<string, string>;
  token?: string;
  credentials?: RequestCredentials;
  requestId?: string;
  timingLabel?: string;
};

type ApiErrorPayload = {
  detail?: string;
  message?: string;
  [key: string]: unknown;
};

export class ApiRequestError extends Error {
  status?: number;
  url: string;
  payload?: ApiErrorPayload;
  isNetworkError: boolean;

  constructor(params: {
    message: string;
    url: string;
    status?: number;
    payload?: ApiErrorPayload;
    isNetworkError?: boolean;
  }) {
    super(params.message);
    this.name = "ApiRequestError";
    this.url = params.url;
    this.status = params.status;
    this.payload = params.payload;
    this.isNetworkError = params.isNetworkError ?? false;
  }
}

export function isApiRequestError(error: unknown): error is ApiRequestError {
  return error instanceof ApiRequestError;
}

function toSearchParams(params?: QueryParams): string {
  if (!params) {
    return "";
  }

  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  });

  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : "";
}

async function requestJson<T>(
  method: "GET" | "POST" | "PATCH" | "DELETE",
  path: string,
  options: RequestOptions = {},
  body?: unknown,
): Promise<T> {
  const requestUrl = `${siteConfig.apiBaseUrl}${path}${toSearchParams(options.params)}`;
  const isServerRequest = typeof window === "undefined";
  const requestId = isServerRequest ? (options.requestId ?? createRequestTimingId("api")) : options.requestId;
  const startedAt = performance.now();
  let status: number | undefined;
  const headers: Record<string, string> = {
    ...(options.headers ?? {}),
  };

  if (options.token) {
    headers.Authorization = `Token ${options.token}`;
  }

  if (requestId) {
    headers["X-Request-ID"] = requestId;
  }

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  let response: Response;
  try {
    response = await fetch(requestUrl, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
      credentials: options.credentials ?? "omit",
    });
    status = response.status;
  } catch {
    logServerTiming(options.timingLabel ?? `api.${method}`, startedAt, {
      method,
      path,
      request_id: requestId,
      network_error: true,
    });
    throw new ApiRequestError({
      message: "Network error while sending request.",
      url: requestUrl,
      isNetworkError: true,
    });
  }

  if (!response.ok) {
    let payload: ApiErrorPayload | undefined;
    let rawErrorBody: string | undefined;

    try {
      rawErrorBody = await response.text();
      if (rawErrorBody) {
        payload = JSON.parse(rawErrorBody) as ApiErrorPayload;
      }
    } catch {
      payload = undefined;
    }

    if (!payload && rawErrorBody) {
      payload = { message: rawErrorBody };
    }

    const backendMessage = payload?.detail ?? payload?.message;
    logServerTiming(options.timingLabel ?? `api.${method}`, startedAt, {
      method,
      path,
      request_id: requestId,
      status,
    });
    throw new ApiRequestError({
      message: backendMessage ? String(backendMessage) : `API request failed with ${response.status}`,
      status: response.status,
      payload,
      url: requestUrl,
    });
  }

  if (response.status === 204) {
    logServerTiming(options.timingLabel ?? `api.${method}`, startedAt, {
      method,
      path,
      request_id: requestId,
      status,
    });
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } finally {
    logServerTiming(options.timingLabel ?? `api.${method}`, startedAt, {
      method,
      path,
      request_id: requestId,
      status,
    });
  }
}

export async function getJson<T>(path: string, params?: QueryParams, options?: Omit<RequestOptions, "params">): Promise<T> {
  return requestJson<T>("GET", path, {
    ...(options ?? {}),
    params,
  });
}

export async function postJson<TResponse, TBody extends Record<string, unknown>>(
  path: string,
  body: TBody,
  params?: QueryParams,
  options?: Omit<RequestOptions, "params">,
): Promise<TResponse> {
  return requestJson<TResponse>(
    "POST",
    path,
    {
      ...(options ?? {}),
      params,
    },
    body,
  );
}

export async function patchJson<TResponse, TBody extends Record<string, unknown>>(
  path: string,
  body: TBody,
  params?: QueryParams,
  options?: Omit<RequestOptions, "params">,
): Promise<TResponse> {
  return requestJson<TResponse>(
    "PATCH",
    path,
    {
      ...(options ?? {}),
      params,
    },
    body,
  );
}

export async function deleteJson<TResponse = void>(
  path: string,
  params?: QueryParams,
  options?: Omit<RequestOptions, "params">,
): Promise<TResponse> {
  return requestJson<TResponse>("DELETE", path, {
    ...(options ?? {}),
    params,
  });
}
