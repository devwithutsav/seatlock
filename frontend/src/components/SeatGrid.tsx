import type { SeatState } from "../types";

interface Props {
  seats: SeatState[];
  disabled: boolean;
  onHold: (seatId: number) => void;
}

export default function SeatGrid({ seats, disabled, onHold }: Props) {
  return (
    <section className="card">
      <h2>Choose a seat</h2>
      <p className="muted">Available seats can be held for five minutes before confirmation.</p>

      <div className="seat-grid">
        {seats.map((seat) => {
          const available = seat.status === "AVAILABLE";
          return (
            <button
              key={seat.id}
              className={`seat seat-${seat.status.toLowerCase()}`}
              disabled={disabled || !available}
              onClick={() => onHold(seat.id)}
            >
              <strong>{seat.seat_number}</strong>
              <span>{seat.status}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
