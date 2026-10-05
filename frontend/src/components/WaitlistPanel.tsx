import type { Reservation, WaitlistStatusResponse } from "../types";

interface Props {
  waitlist: WaitlistStatusResponse;
  reservation: Reservation | null;
  isFull: boolean;
  busy: boolean;
  onJoin: () => void;
  onCancel: () => void;
}

export default function WaitlistPanel({ waitlist, reservation, isFull, busy, onJoin, onCancel }: Props) {
  const active = waitlist.entry?.status === "WAITING";

  return (
    <section className="card">
      <h2>Waitlist</h2>
      {active ? (
        <>
          <p>You are in the FIFO waitlist at position <strong>#{waitlist.position ?? "-"}</strong>.</p>
          <button className="secondary" disabled={busy} onClick={onCancel}>Leave waitlist</button>
        </>
      ) : (
        <>
          <p className="muted">The waitlist opens when all 20 seats are held or confirmed.</p>
          <button disabled={busy || !isFull || !!reservation} onClick={onJoin}>Join waitlist</button>
        </>
      )}
    </section>
  );
}
