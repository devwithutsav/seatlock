import type {
  Activity,
  Availability,
  Reservation,
  SeatState,
  User,
  WaitlistEntry,
  WaitlistStatusResponse
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers ?? {})
    }
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      message = body.detail ?? JSON.stringify(body);
    } catch {
      // Keep the HTTP status text.
    }
    throw new Error(message);
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) return undefined as T;
  return response.json() as Promise<T>;
}

export function newIdempotencyKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

export const login = (name: string, email: string) =>
  request<User>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ name, email })
  });

export const logout = () => request<{ message: string }>("/auth/logout", { method: "POST" });
export const getMe = () => request<User>("/auth/me");
export const getSeats = () => request<SeatState[]>("/seats");
export const getAvailability = () => request<Availability>("/availability");
export const getMyReservation = () => request<Reservation | null>("/reservations/me");
export const getMyWaitlist = () => request<WaitlistStatusResponse>("/waitlist/me");

export const holdSeat = (seatId: number) =>
  request<Reservation>("/reservations/hold", {
    method: "POST",
    headers: { "Idempotency-Key": newIdempotencyKey("hold") },
    body: JSON.stringify({ seat_id: seatId })
  });

export const confirmReservation = (reservationId: number) =>
  request<Reservation>(`/reservations/${reservationId}/confirm`, {
    method: "POST",
    headers: { "Idempotency-Key": newIdempotencyKey("confirm") }
  });

export const cancelReservation = (reservationId: number) =>
  request<Reservation>(`/reservations/${reservationId}/cancel`, {
    method: "POST",
    headers: { "Idempotency-Key": newIdempotencyKey("cancel") }
  });

export const getActivity = (reservationId: number) =>
  request<Activity[]>(`/reservations/${reservationId}/activity`);

export const joinWaitlist = () =>
  request<WaitlistEntry>("/waitlist/join", {
    method: "POST",
    headers: { "Idempotency-Key": newIdempotencyKey("waitlist-join") }
  });

export const cancelWaitlist = (entryId: number) =>
  request<WaitlistEntry>(`/waitlist/${entryId}/cancel`, {
    method: "POST",
    headers: { "Idempotency-Key": newIdempotencyKey("waitlist-cancel") }
  });

export function createSocket(onMessage: () => void): WebSocket {
  const wsBase = API_BASE.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
  const socket = new WebSocket(`${wsBase}/ws`);
  socket.onopen = () => socket.send("ready");
  socket.onmessage = onMessage;
  return socket;
}
