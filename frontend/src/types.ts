export type ReservationStatus = "HELD" | "CONFIRMED" | "CANCELLED" | "EXPIRED";
export type WaitlistStatus = "WAITING" | "PROMOTED" | "CANCELLED";

export interface User {
  id: number;
  name: string;
  email: string;
}

export interface SeatState {
  id: number;
  seat_number: number;
  status: "AVAILABLE" | "HELD" | "CONFIRMED";
  reservation_id: number | null;
  held_until: string | null;
}

export interface Availability {
  total: number;
  available: number;
  held: number;
  confirmed: number;
}

export interface Reservation {
  id: number;
  user_id: number;
  seat_id: number;
  status: ReservationStatus;
  created_at: string;
  held_until: string | null;
  confirmed_at: string | null;
  cancelled_at: string | null;
}

export interface WaitlistEntry {
  id: number;
  user_id: number;
  status: WaitlistStatus;
  created_at: string;
}

export interface WaitlistStatusResponse {
  entry: WaitlistEntry | null;
  position: number | null;
}

export interface Activity {
  id: number;
  reservation_id: number;
  previous_state: string | null;
  new_state: string;
  timestamp: string;
  reason: string;
}
