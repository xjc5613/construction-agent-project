const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${API_BASE.replace(/\/$/, "")}${path}`, {
    ...init,
    headers,
  });
  if (!res.ok) {
    let msg = `请求失败 (${res.status})`;
    try {
      const data = await res.json();
      msg = data?.error?.message || data?.detail?.message || data?.detail || msg;
    } catch {
      /* ignore */
    }
    throw new Error(typeof msg === "string" ? msg : "请求失败");
  }
  return res.json() as Promise<T>;
}
