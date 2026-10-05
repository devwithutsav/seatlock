export function secondsUntil(value: string | null): number | null {
  if (!value) return null;
  const milliseconds = new Date(value).getTime() - Date.now();
  return Math.max(0, Math.ceil(milliseconds / 1000));
}

export function formatLocal(value: string): string {
  return new Date(value).toLocaleString();
}
