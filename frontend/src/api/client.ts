const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function parseResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message = readableErrorMessage(body);
    throw new ApiError(message, response.status);
  }
  return body as T;
}

function readableErrorMessage(body: unknown): string {
  if (typeof body === "string") return body || "请求失败";
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return "请求失败，请检查页面填写内容。";
    if (detail && typeof detail === "object") return JSON.stringify(detail);
  }
  return "请求失败，请稍后重试。";
}

export async function apiGet<T>(path: string): Promise<T> {
  return parseResponse<T>(await fetch(`${API_BASE}${path}`));
}

export async function apiPost<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  return parseResponse<T>(
    await fetch(`${API_BASE}${path}`, {
      method: "POST",
      signal,
      headers: body instanceof FormData ? undefined : { "Content-Type": "application/json" },
      body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body)
    })
  );
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return parseResponse<T>(
    await fetch(`${API_BASE}${path}`, {
      method: "PUT",
      headers: body instanceof FormData ? undefined : { "Content-Type": "application/json" },
      body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body)
    })
  );
}

export async function apiDelete<T>(path: string): Promise<T> {
  return parseResponse<T>(await fetch(`${API_BASE}${path}`, { method: "DELETE" }));
}
