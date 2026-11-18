import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import * as authApi from "../api/auth";
import { setSessionExpiredHandler } from "../api/client";
import { tokenStore } from "../api/tokenStore";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // While we check a saved session on first load, treat the user as "unknown", not "signed out".
  const [loading, setLoading] = useState(() => tokenStore.hasSession());

  // If a token refresh fails mid-session, the API client tells us and we sign the user out.
  useEffect(() => {
    setSessionExpiredHandler(() => setUser(null));
    return () => setSessionExpiredHandler(null);
  }, []);

  useEffect(() => {
    if (!tokenStore.hasSession()) return undefined;
    let cancelled = false;
    authApi
      .getProfile()
      .then((profile) => !cancelled && setUser(profile))
      .catch((error) => {
        if (cancelled) return;
        if (error.response?.status === 401) tokenStore.clear(); // saved session is no longer valid
        setUser(null);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (credentials) => {
    const signedIn = await authApi.login(credentials);
    setUser(signedIn);
    return signedIn;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
