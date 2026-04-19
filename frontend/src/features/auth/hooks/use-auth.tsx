"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { getCurrentUser } from "@/features/auth/api/get-current-user";
import { login as loginRequest } from "@/features/auth/api/login";
import { logout as logoutRequest } from "@/features/auth/api/logout";
import { clearStoredAuthToken, readStoredAuthToken, writeStoredAuthToken } from "@/features/auth/lib/token-storage";
import type { AuthUser } from "@/features/auth/types/auth";

type AuthContextValue = {
  token: string | null;
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (payload: { email: string; password: string }) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<AuthUser | null>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function bootstrap() {
      const storedToken = readStoredAuthToken();
      if (!storedToken) {
        if (isMounted) {
          setIsLoading(false);
        }
        return;
      }

      try {
        const currentUser = await getCurrentUser(storedToken);
        if (isMounted) {
          setToken(storedToken);
          setUser(currentUser);
        }
      } catch {
        clearStoredAuthToken();
        if (isMounted) {
          setToken(null);
          setUser(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void bootstrap();

    return () => {
      isMounted = false;
    };
  }, []);

  const login = useCallback(async (payload: { email: string; password: string }) => {
    const response = await loginRequest(payload);
    writeStoredAuthToken(response.token);
    setToken(response.token);
    setUser(response.user);
  }, []);

  const logout = useCallback(async () => {
    if (token) {
      try {
        await logoutRequest(token);
      } catch {
        // Intentionally ignored to ensure local auth state is cleared.
      }
    }

    clearStoredAuthToken();
    setToken(null);
    setUser(null);
  }, [token]);

  const refreshUser = useCallback(async (): Promise<AuthUser | null> => {
    if (!token) {
      setUser(null);
      return null;
    }

    const currentUser = await getCurrentUser(token);
    setUser(currentUser);
    return currentUser;
  }, [token]);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      user,
      isLoading,
      isAuthenticated: Boolean(token && user),
      login,
      logout,
      refreshUser,
    }),
    [token, user, isLoading, login, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
