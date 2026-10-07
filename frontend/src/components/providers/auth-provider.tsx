"use client";

import type { ReactNode } from "react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { usePathname, useRouter } from "next/navigation";

import {
  clearAuthSession,
  getSessionExpiresAt,
  getStoredCurrentUser,
  saveAuthSession,
} from "@/lib/auth/session";
import { fetchProfileQuietly, logoutUser } from "@/lib/api/auth";
import type { ProfileResponse } from "@/types/auth";

type AuthContextValue = {
  currentUser: ProfileResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (profile: ProfileResponse, expiresIn?: number) => void;
  logout: (redirectTo?: string) => void;
  refreshSession: () => void;
  /**
   * False until the full profile (phone, ИИН/БИН, company, email_verified) has
   * been loaded from the API once after sign-in. localStorage keeps only a thin
   * copy, so forms that prefill from the profile must wait for this flag.
   */
  isProfileReady: boolean;
  /** Re-load the profile from the API (or apply an already fetched one). */
  refreshProfile: (profile?: ProfileResponse) => Promise<ProfileResponse | null>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

type AuthProviderProps = {
  children: ReactNode;
};

export function AuthProvider({ children }: AuthProviderProps) {
  const router = useRouter();

  // `storedUser` is the thin copy from localStorage (no phone / tax id /
  // company, email_verified assumed true). `serverProfile` is the full profile
  // from the API, kept in memory only. `currentUser` merges them.
  const [storedUser, setCurrentUser] = useState<ProfileResponse | null>(null);
  const [serverProfile, setServerProfile] = useState<ProfileResponse | null>(null);
  const [syncedUserId, setSyncedUserId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const sessionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearSessionTimer = useCallback(() => {
    if (sessionTimerRef.current) {
      clearTimeout(sessionTimerRef.current);
      sessionTimerRef.current = null;
    }
  }, []);

  // Cleanup timer on unmount
  useEffect(() => {
    return clearSessionTimer;
  }, [clearSessionTimer]);

  const scheduleSessionExpiry = useCallback(
    (expiresAt: number) => {
      clearSessionTimer();
      const msLeft = expiresAt - Date.now();
      if (msLeft <= 0) return;
      sessionTimerRef.current = setTimeout(() => {
        clearAuthSession();
        setCurrentUser(null);
        router.push("/login?expired=1");
      }, msLeft);
    },
    [clearSessionTimer, router],
  );

  const refreshSession = useCallback(() => {
    const stored = getStoredCurrentUser();
    const expiresAt = getSessionExpiresAt();

    if (stored && expiresAt !== null && expiresAt < Date.now()) {
      clearAuthSession();
      setCurrentUser(null);
      setIsLoading(false);
      router.replace("/login?expired=1");
      return;
    }

    setCurrentUser(stored);
    setIsLoading(false);

    if (stored && expiresAt !== null) {
      scheduleSessionExpiry(expiresAt);
    }
  }, [router, scheduleSessionExpiry]);

  useEffect(() => {
    refreshSession();
  }, [refreshSession]);

  const login = useCallback(
    (profile: ProfileResponse, expiresIn?: number) => {
      saveAuthSession(profile, expiresIn);
      setCurrentUser(getStoredCurrentUser());
      // The login response already carries the full profile — use it as is.
      setServerProfile(profile);
      setSyncedUserId(profile.user_id);
      const expiresAt = getSessionExpiresAt();
      if (expiresAt !== null) {
        scheduleSessionExpiry(expiresAt);
      }
    },
    [scheduleSessionExpiry],
  );

  const logout = useCallback(
    async (redirectTo = "/login") => {
      clearSessionTimer();
      try {
        await logoutUser();
      } catch {
        // cookie cleared server-side; ignore network errors
      }
      clearAuthSession();
      setCurrentUser(null);
      setServerProfile(null);
      setSyncedUserId(null);
      router.push(redirectTo);
    },
    [clearSessionTimer, router],
  );

  const currentUser = useMemo<ProfileResponse | null>(() => {
    if (!storedUser) return null;
    return serverProfile && serverProfile.user_id === storedUser.user_id
      ? { ...storedUser, ...serverProfile }
      : storedUser;
  }, [storedUser, serverProfile]);

  const storedUserId = storedUser?.user_id ?? null;

  const refreshProfile = useCallback(
    async (profile?: ProfileResponse) => {
      const full = profile ?? (await fetchProfileQuietly());
      if (full) setServerProfile(full);
      setSyncedUserId(full?.user_id ?? storedUserId);
      return full;
    },
    [storedUserId],
  );

  // Load the full profile once per signed-in user. Failure is not fatal: the
  // thin profile keeps working and the flag flips so forms stop waiting.
  useEffect(() => {
    if (storedUserId === null || syncedUserId === storedUserId) return;
    let cancelled = false;
    void fetchProfileQuietly().then((full) => {
      if (cancelled) return;
      if (full && full.user_id === storedUserId) setServerProfile(full);
      setSyncedUserId(storedUserId);
    });
    return () => { cancelled = true; };
  }, [storedUserId, syncedUserId]);

  const isProfileReady = storedUserId === null || syncedUserId === storedUserId;

  const value = useMemo<AuthContextValue>(
    () => ({
      currentUser,
      isAuthenticated: Boolean(currentUser),
      isLoading,
      login,
      logout,
      refreshSession,
      isProfileReady,
      refreshProfile,
    }),
    [currentUser, isLoading, login, logout, refreshSession, isProfileReady, refreshProfile],
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
