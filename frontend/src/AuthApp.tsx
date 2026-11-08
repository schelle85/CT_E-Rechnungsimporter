import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Group,
  Loader,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import App from "./App";
import { api, ApiError, type AuthState } from "./api";
export default function AuthApp() {
  const [state, setState] = useState<AuthState | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [username, setUsername] = useState(""),
    [password, setPassword] = useState("");
  const refresh = useCallback(async () => {
    try {
      setState(await api<AuthState>("/api/auth/session"));
    } catch (e) {
      setState(null);
      if (e instanceof ApiError && e.status === 401) {
        try {
          setState(await api<AuthState>("/api/auth/session"));
          return;
        } catch {}
      }
      setError(e instanceof Error ? e.message : "Sitzung nicht verfügbar.");
    }
  }, []);
  useEffect(() => {
    void refresh();
    const invalid = () => {
      setState(null);
      setError(
        "Sitzung abgelaufen oder Berechtigung entzogen. Bitte erneut anmelden.",
      );
      void refresh();
    };
    window.addEventListener("session-invalid", invalid);
    return () => window.removeEventListener("session-invalid", invalid);
  }, [refresh]);
  const logout = async () => {
    if (!state) return;
    setError("");
    try {
      await api("/api/auth/logout", { method: "POST" }, state.csrf_token);
      setState(null);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Abmeldung fehlgeschlagen.");
    }
  };
  const reauthenticate = async () => {
    setState(null);
    setError("Geprüfte Konfiguration aktiviert. Bitte erneut anmelden.");
    await refresh();
  };
  if (state?.authenticated && state.user)
    return (
      <>
        {error && (
          <Alert color="yellow" style={{ marginLeft: 238 }}>
            {error}
          </Alert>
        )}
        <App
          user={state.user}
          csrfToken={state.csrf_token}
          onLogout={logout}
          onReauthenticate={reauthenticate}
        />
      </>
    );
  return (
    <div className="auth-page">
      <Paper withBorder className="login-card">
        <div className="brand">
          <span className="brand-mark">E</span>
          <div>
            E-Rechnungen<small>IMPORTER</small>
          </div>
        </div>
        <Title order={1}>Willkommen zurück</Title>
        <Text c="dimmed" mt="sm" mb="xl">
          Melden Sie sich mit Ihrem bestehenden Windows-Konto an.
        </Text>
        {error && (
          <Alert color="yellow" mb="lg">
            {error}
          </Alert>
        )}
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (!state) return;
            setBusy(true);
            setError("");
            try {
              setState(
                await api<AuthState>(
                  "/api/auth/login",
                  {
                    method: "POST",
                    body: JSON.stringify({ username, password }),
                  },
                  state.csrf_token,
                ),
              );
            } catch (e) {
              setError(
                e instanceof Error ? e.message : "Anmeldung fehlgeschlagen.",
              );
            } finally {
              setPassword("");
              setBusy(false);
            }
          }}
        >
          <Stack>
            <TextInput
              label="Benutzername oder UPN"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.currentTarget.value)}
              required
              maxLength={128}
              disabled={busy || !state}
            />
            <PasswordInput
              label="Kennwort"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.currentTarget.value)}
              required
              maxLength={1024}
              disabled={busy || !state}
            />
            <Button type="submit" loading={busy} disabled={!state}>
              Anmelden
            </Button>
            {!state && (
              <Group justify="center">
                <Loader size="xs" />
                <Button variant="subtle" onClick={() => void refresh()}>
                  Verbindung erneut prüfen
                </Button>
              </Group>
            )}
            <Text size="xs" c="dimmed">
              Der Zugriff richtet sich nach Ihrer AD-Gruppe. Kennwörter werden
              nicht in der Anwendung gespeichert.
            </Text>
          </Stack>
        </form>
        <Alert color="blue" mt="xl" title="AP01 · geschützter Arbeitsplatz">
          Die Verarbeitungsvorgänge sind weiterhin synthetische Vorschau. Kein
          automatischer Import oder Mailversand aktiv.
        </Alert>
      </Paper>
    </div>
  );
}
