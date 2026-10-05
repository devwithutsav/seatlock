import { useEffect, useState } from "react";
import { parseUtc } from "../date";
import type { Reservation } from "../types";

interface Props {
  reservation: Reservation | null;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

function remainingSeconds(value: string | null): number {
  if (!value) return 0;
  return Math.max(0, Math.ceil((parseUtc(value).getTime() - Date.now()) / 1000));
}

export default function ReservationPanel({ reservation, busy, onConfirm, onCancel }: Props) {
  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    const update = () => setRemaining(remainingSeconds(reservation?.held_until ?? null));
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
        <div>
          <div className="status-row">
            <span>Reservation #{reservation.id}</span>
            <strong className={`badge badge-${reservation.status.toLowerCase()}`}>{reservation.status}</strong>
          </div>
          <p>Seat ID: <strong>{reservation.seat_id}</strong></p>

          {reservation.status === "HELD" && (
            <>
              <p>Hold expires in <strong>{remaining > 0 ? `${remaining}s` : "expired"}</strong></p>
              <div className="button-row">
                <button disabled={busy || remaining <= 0} onClick={onConfirm}>Confirm</button>
                <button className="secondary" disabled={busy} onClick={onCancel}>Cancel hold</button>
              </div>
            </>
          )}

          {reservation.status === "CONFIRMED" && (
            <button className="danger" disabled={busy} onClick={onCancel}>Cancel reservation</button>
          )}
        </div>
      )}
    </section>
  );
}
