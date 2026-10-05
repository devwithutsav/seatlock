import { useEffect, useState } from "react";
import { secondsUntil } from "../date";
import type { Reservation } from "../types";

interface Props {
  reservation: Reservation | null;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

function displayRemaining(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds <= 0) return "expired";
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}m ${rest.toString().padStart(2, "0")}s`;
}

export default function ReservationPanel({ reservation, busy, onConfirm, onCancel }: Props) {
  const [remaining, setRemaining] = useState<number | null>(null);

  useEffect(() => {
    const update = () => setRemaining(secondsUntil(reservation?.held_until ?? null));
    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [reservation?.held_until]);

  return (
    <section className="card">
      <h2>Your reservation</h2>

      {!reservation ? (
        <p className="muted">No active reservation.</p>
      ) : (
        <>
          <div className="status-row">
            <span>Reservation #{reservation.id}</span>
            <strong className={`badge badge-${reservation.status.toLowerCase()}`}>
              {reservation.status}
            </strong>
          </div>

          <p>Seat ID: <strong>{reservation.seat_id}</strong></p>

          {reservation.status === "HELD" && (
            <>
              <p>Hold expires in <strong>{displayRemaining(remaining)}</strong></p>
              <div className="button-row">
                <button disabled={busy} onClick={onConfirm}>Confirm</button>
                <button className="secondary" disabled={busy} onClick={onCancel}>Cancel hold</button>
              </div>
            </>
          )}

          {reservation.status === "CONFIRMED" && (
            <>
              <p className="success-text">Your seat is confirmed.</p>
              <button className="danger" disabled={busy} onClick={onCancel}>
                Cancel reservation
              </button>
            </>
          )}
        </>
      )}
    </section>
  );
}
