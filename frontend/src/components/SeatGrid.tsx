import type { SeatState } from "../types";

interface Props {
  seats: SeatState[];
  disabled: boolean;
  onHold: (seatId: number) => void;
}

export default function SeatGrid({ seats, disabled, onHold }: Props) {
  return (
    <section className="card">
      <div className="section-heading">
        <div>
          <h2>Choose a seat</h2>
          <p>Available seats can be held temporarily before confirmation.</p>
        </div>
      </div>

      <div className="seat-grid">
        {seats.map((seat) => (
          <button
            key={seat.id}
            className={`seat seat-${seat.status.toLowerCase()}`}
            disabled={disabled || seat.status !== "AVAILABLE"}
            onClick={() => onHold(seat.id)}
            title={`Seat ${seat.seat_number}: ${seat.status}`}
          >
            <span>{seat.seat_number}</span>
            <small>{seat.status}</small>
          </button>
        ))}
      </div>
    </section>
  );
}
