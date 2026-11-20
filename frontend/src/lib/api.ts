import { z } from "zod";
import { detailSchema, reviewItemSchema } from "./types";
import type { CreateReview } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(message: string, public status: number, public code = "request_failed") { super(message); }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api${path}`, { ...init, cache: "no-store",
      headers: { "Content-Type": "application/json", "X-AICR-Client": "web", ...init.headers } });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("Cannot reach the local review server. Start aicr-api and retry.", 0, "offline");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Request failed (${response.status}). Try again.`, response.status, body?.error);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function createReview(payload: CreateReview) {
  return reviewItemSchema.parse(await api("/reviews", { method: "POST", body: JSON.stringify(payload) }));
}
export async function getReview(id: string, signal?: AbortSignal) {
  return detailSchema.parse(await api(`/reviews/${id}`, { signal }));
}
export async function getReviews(offset = 0, signal?: AbortSignal) {
  return z.array(reviewItemSchema).parse(await api(`/reviews?limit=50&offset=${offset}`, { signal }));
}
