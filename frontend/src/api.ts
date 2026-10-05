import { getToken } from "./auth";
import type {
  Activity,
  Availability,
  LoginResponse,
  Reservation,
  SeatState,
  User,
  WaitlistEntry,
  WaitlistStatusResponse
} from "./types";

const configuredApi = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "");
const API_BASE = configuredApi || "/api";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {})
    }
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      message = body.detail ?? message;
    } catch {
      // Keep generic HTTP message.
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

function key(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

export const login = (name: string, email: string) =>
  request<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ name, email })
  });

export const logout = () =>
  request<{ message: string }>("/auth/logout", { method: "POST" });

export const getMe = () => request<User>("/auth/me");
export const getSeats = () => request<SeatState[]>("/seats");
export const getAvailability = () => request<Availability>("/availability");
export const getMyReservation = () => request<Reservation | null>("/reservations/me");
export const getMyWaitlist = () => request<WaitlistStatusResponse>("/waitlist/me");

export const holdSeat = (seatId: number) =>
  request<Reservation>("/reservations/hold", {
    method: "POST",
    headers: { "Idempotency-Key": key("hold") },
    body: JSON.stringify({ seat_id: seatId })
  });

export const confirmReservation = (reservationId: number) =>
  request<Reservation>(`/reservations/${reservationId}/confirm`, {
    method: "POST",
    headers: { "Idempotency-Key": key("confirm") }
  });

export const cancelReservation = (reservationId: number) =>
  request<Reservation>(`/reservations/${reservationId}/cancel`, {
    method: "POST",
    headers: { "Idempotency-Key": key("cancel") }
  });

export const getActivity = (reservationId: number) =>
  request<Activity[]>(`/reservations/${reservationId}/activity`);

export const joinWaitlist = () =>
  request<WaitlistEntry>("/waitlist/join", {
    method: "POST",
    headers: { "Idempotency-Key": key("waitlist-join") }
  });

export const cancelWaitlist = (entryId: number) =>
  request<WaitlistEntry>(`/waitlist/${entryId}/cancel`, {
    method: "POST",
    headers: { "Idempotency-Key": key("waitlist-cancel") }
  });

export function createSocket(onMessage: () => void): WebSocket | null {
  const token = getToken();
  if (!token) return null;

  const configuredWs = (import.meta.env.VITE_WS_BASE_URL as string | undefined)?.replace(/\/$/, "");

  let wsBase: string;
  if (configuredWs) {
    wsBase = configuredWs;
  } else if (configuredApi) {
    wsBase = configuredApi.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
  } else {
    wsBase = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/api`;
  }

  const socket = new WebSocket(`${wsBase}/ws?token=${encodeURIComponent(token)}`);
  socket.onopen = () => socket.send("ready");
  socket.onmessage = onMessage;
  return socket;
}
