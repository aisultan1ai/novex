"use client";

import type { ReactNode } from "react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { usePathname, useRouter } from "next/navigation";

import {
  clearAuthSession,
  getStoredCurrentUser,
  saveAuthSession,
} from "@/lib/auth/session";
import { logoutUser } from "@/lib/api/auth";
import type { ProfileResponse } from "@/types/auth";

type AuthContextValue = {
  currentUser: ProfileResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (profile: ProfileResponse) => void;
  logout: (redirectTo?: string) => void;
  refreshSession: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

type AuthProviderProps = {
  children: ReactNode;
};

export function AuthProvider({ children }: AuthProviderProps) {
  const router = useRouter();

  const [currentUser, setCurrentUser] = useState<ProfileResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshSession = useCallback(() => {
    setCurrentUser(getStoredCurrentUser());
    setIsLoading(false);
  }, []);

  useEffect(() => {
    refreshSession();
  }, [refreshSession]);

  const login = useCallback((profile: ProfileResponse) => {
    saveAuthSession(profile);
    setCurrentUser(profile);
  }, []);

  const logout = useCallback(
    async (redirectTo = "/login") => {
      try {
        await logoutUser();
      } catch {
        // cookie cleared server-side; ignore network errors
      }
      clearAuthSession();
      setCurrentUser(null);
      router.push(redirectTo);
    },
    [router],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      currentUser,
      isAuthenticated: Boolean(currentUser),
      isLoading,
      login,
      logout,
      refreshSession,
    }),
    [currentUser, isLoading, login, logout, refreshSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }

  return context;
}

type RequireAuthProps = {
  children: ReactNode;
  redirectTo?: string;
  fallback?: ReactNode;
};

export function RequireAuth({
  children,
  redirectTo = "/login",
  fallback = null,
}: RequireAuthProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (isLoading || isAuthenticated) {
      return;
    }

    const next = pathname ? `?next=${encodeURIComponent(pathname)}` : "";
    router.replace(`${redirectTo}${next}`);
  }, [isAuthenticated, isLoading, pathname, redirectTo, router]);

  if (isLoading) {
    return (
      fallback ?? (
        <div
          style={{
            minHeight: "40vh",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#475569",
            fontFamily:
              "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
          }}
        >
          Проверяем сессию...
        </div>
      )
    );
  }

  if (!isAuthenticated) {
    return fallback ?? null;
  }

  return <>{children}</>;
}
