const TOKEN_KEY = "seatlock_token";

// Reads bearer auth token from local storage
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

// Persists auth token upon successful login
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

// Clears auth token on sign-out or session expiry
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}