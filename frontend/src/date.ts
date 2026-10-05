// Backend timestamps are naive UTC because the existing PostgreSQL schema uses
// TIMESTAMP WITHOUT TIME ZONE. Append Z so browsers interpret them as UTC.
export function parseUtc(value: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
  return new Date(hasZone ? value : `${value}Z`);
}
