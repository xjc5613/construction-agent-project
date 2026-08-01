export async function apiRequest<T>(
  apiBase: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${apiBase.replace(/\/$/, "")}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as {
      detail?: string | { message?: string; missing?: string[] };
    };
    const detail = typeof payload.detail === "string"
      ? payload.detail
      : [payload.detail?.message, ...(payload.detail?.missing ?? [])].filter(Boolean).join("；");
    throw new Error(detail || `请求失败 (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function assetUrl(apiBase: string, path: string): string {
  return `${apiBase.replace(/\/api\/?$/, "")}${path}`;
}
