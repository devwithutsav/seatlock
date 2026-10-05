// Authenticated user profile[cite: 22]
export interface User {
  id: number;
  name: string;
  email: string;
}

// Auth handshake response payload[cite: 22]
export interface LoginResponse {
  token: string;
  user: User;
}

// State machine values mirroring backend reservation status enum[cite: 8, 22]
export type ReservationStatus = "HELD" | "CONFIRMED" | "CANCELLED" | "EXPIRED";

// Reservation model representation for client consumption[cite: 22]
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

// Seat card state projected on the workshop seat grid[cite: 14, 22]
export interface SeatState {
  id: number;
  seat_number: number;
  status: "AVAILABLE" | "HELD" | "CONFIRMED";
  reservation_id: number | null;
  held_until: string | null;
}

// Aggregate metrics driving availability counters and waitlist eligibility[cite: 18, 22]
export interface Availability {
  total: number;
  available: number;
  held: number;
  confirmed: number;
}

// Single FIFO queue item representation[cite: 22]
export interface WaitlistEntry {
  id: number;
  user_id: number;
  status: "WAITING" | "PROMOTED" | "CANCELLED";
  created_at: string;
  promoted_at: string | null;
  cancelled_at: string | null;
}

// Composite response carrying both user's waitlist ticket and computed queue index[cite: 22]
export interface WaitlistStatusResponse {
  entry: WaitlistEntry | null;
  position: number | null;
}

// Historical audit log record for state transitions[cite: 22]
export interface Activity {
  id: number;
  reservation_id: number;
  previous_state: string | null;
  new_state: string;
  timestamp: string;
  reason: string;
}