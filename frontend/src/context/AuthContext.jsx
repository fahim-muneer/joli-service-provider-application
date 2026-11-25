import { useCallback, useEffect, useMemo, useState } from "react";
import { AuthContext } from "./authContext";
import * as authApi from "../api/auth";
import { setSessionExpiredHandler } from "../api/client";
import { tokenStore } from "../api/tokenStore";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(() => tokenStore.hasSession());

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
        if (error.response?.status === 401) tokenStore.clear();
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

  const value = useMemo(
    () => ({ user, loading, login, logout, updateUser: setUser }),
    [user, loading, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
