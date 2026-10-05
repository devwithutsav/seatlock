import { formatLocal } from "../date";
import type { Activity } from "../types";

export default function ActivityTimeline({ activity }: { activity: Activity[] }) {
  return (
    <section className="card">
      <h2>Activity timeline</h2>

      {activity.length === 0 ? (
        <p className="muted">No activity for the current reservation.</p>
      ) : (
        <div className="timeline">
          {activity.map((item) => (
            <article className="timeline-item" key={item.id}>
              <div>
                <strong>{item.previous_state ?? "NONE"} → {item.new_state}</strong>
                <p>{item.reason}</p>
              </div>
              <time>{formatLocal(item.timestamp)}</time>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
