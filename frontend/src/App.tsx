import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  cancelReservation,
  cancelWaitlist,
  confirmReservation,
  createSocket,
  getActivity,
  getAvailability,
  getMe,
  getMyReservation,
  getMyWaitlist,
  getSeats,
  holdSeat,
  joinWaitlist,
  login,
  logout
} from "./api";
import { clearToken, getToken, setToken } from "./auth";
import ActivityTimeline from "./components/ActivityTimeline";
import ReservationPanel from "./components/ReservationPanel";
import SeatGrid from "./components/SeatGrid";
import WaitlistPanel from "./components/WaitlistPanel";
import type {
  Activity,
  Availability,
  Reservation,
  SeatState,
  User,
  WaitlistStatusResponse
} from "./types";

const EMPTY_AVAILABILITY: Availability = {
  total: 20,
  available: 20,
  held: 0,
  confirmed: 0
};

const EMPTY_WAITLIST: WaitlistStatusResponse = {
  entry: null,
  position: null
};

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [seats, setSeats] = useState<SeatState[]>([]);
  const [availability, setAvailability] = useState<Availability>(EMPTY_AVAILABILITY);
  const [reservation, setReservation] = useState<Reservation | null>(null);
  const [waitlist, setWaitlist] = useState<WaitlistStatusResponse>(EMPTY_WAITLIST);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    const [nextSeats, nextAvailability] = await Promise.all([
      getSeats(),
      getAvailability()
    ]);

    setSeats(nextSeats);
    setAvailability(nextAvailability);

    if (!getToken()) return;

    const [nextReservation, nextWaitlist] = await Promise.all([
      getMyReservation(),
      getMyWaitlist()
    ]);

    setReservation(nextReservation);
    setWaitlist(nextWaitlist);

    if (nextReservation) {
      setActivity(await getActivity(nextReservation.id));
    } else {
      setActivity([]);
    }
  }, []);

  useEffect(() => {
    const token = getToken();

    if (!token) {
      getSeats().then(setSeats).catch(() => undefined);
      getAvailability().then(setAvailability).catch(() => undefined);
      return;
    }

    getMe()
      .then(async (me) => {
        setUser(me);
        await refresh();
      })
      .catch(() => {
        clearToken();
        setUser(null);
      });
  }, [refresh]);

  useEffect(() => {
    if (!user) return;

    let socket: WebSocket | null = null;
    let retryTimer: number | null = null;
    let stopped = false;

    const connect = () => {
      if (stopped) return;

      socket = createSocket(() => {
        refresh().catch(() => undefined);
      });

      if (!socket) return;

      socket.onclose = () => {
        if (!stopped) {
          retryTimer = window.setTimeout(connect, 1500);
        }
      };
    };

    connect();

    const fallback = window.setInterval(() => {
      refresh().catch(() => undefined);
    }, 10000);

    return () => {
      stopped = true;
      if (retryTimer !== null) window.clearTimeout(retryTimer);
      window.clearInterval(fallback);
      socket?.close();
    };
  }, [user, refresh]);

  const isFull = useMemo(
    () => availability.available === 0,
    [availability.available]
  );

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");

    try {
      await action();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleLogin(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");

    try {
      const result = await login(name.trim(), email.trim());
      setToken(result.token);
      setUser(result.user);
      await refresh();
    } catch (err) {
      clearToken();
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleLogout() {
    setBusy(true);

    try {
      await logout();
    } catch {
      // Local logout should still succeed even if the server session is gone.
    } finally {
      clearToken();
      setUser(null);
      setReservation(null);
      setWaitlist(EMPTY_WAITLIST);
      setActivity([]);
      setBusy(false);
    }
  }

  if (!user) {
    return (
      <main className="login-shell">
        <form className="login-card" onSubmit={handleLogin}>
          <div className="brand">
            <span className="brand-mark">SL</span>
            <div>
              <h1>SeatLock</h1>
              <p>Real-time workshop reservations</p>
            </div>
          </div>

          <label>
            Name
            <input
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Your name"
            />
          </label>

          <label>
            Email
            <input
              required
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
            />
          </label>

          {error && <div className="error">{error}</div>}

          <button disabled={busy}>
            {busy ? "Signing in…" : "Enter SeatLock"}
          </button>
        </form>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">SL</span>
          <div>
            <h1>SeatLock</h1>
            <p>20-seat campus workshop</p>
          </div>
        </div>

        <div className="user-area">
          <span>{user.name}</span>
          <button className="secondary small" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>

      {error && (
        <div className="error banner">
          <span>{error}</span>
          <button className="ghost small" onClick={() => setError("")}>
            Dismiss
          </button>
        </div>
      )}

      <section className="stats">
        <article><span>Total</span><strong>{availability.total}</strong></article>
        <article><span>Available</span><strong>{availability.available}</strong></article>
        <article><span>Held</span><strong>{availability.held}</strong></article>
        <article><span>Confirmed</span><strong>{availability.confirmed}</strong></article>
      </section>

      <div className="layout">
        <div className="main-column">
          <SeatGrid
            seats={seats}
            disabled={busy || !!reservation || !!waitlist.entry}
            onHold={(seatId) => run(() => holdSeat(seatId))}
          />

          <ActivityTimeline activity={activity} />
        </div>

        <aside className="side-column">
          <ReservationPanel
            reservation={reservation}
            busy={busy}
            onConfirm={() => {
              if (!reservation) return;
              const reservationId = reservation.id;
              run(() => confirmReservation(reservationId));
            }}
            onCancel={() => {
              if (!reservation) return;
              const reservationId = reservation.id;
              run(() => cancelReservation(reservationId));
            }}
          />

          <WaitlistPanel
            waitlist={waitlist}
            reservation={reservation}
            isFull={isFull}
            busy={busy}
            onJoin={() => run(joinWaitlist)}
            onCancel={() => {
              if (!waitlist.entry) return;
              const entryId = waitlist.entry.id;
              run(() => cancelWaitlist(entryId));
            }}
          />
        </aside>
      </div>
    </main>
  );
}
