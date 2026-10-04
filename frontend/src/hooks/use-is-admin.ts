"use client";

import { useAuth } from "@/components/providers/auth-provider";

/**
 * True only for the admin role. Operators can open admin reference pages
 * (users, carriers, tariffs, commissions, settings) read-only — the backend
 * rejects their writes — so pages use this to hide create/edit/delete controls.
 */
export function useIsAdmin(): boolean {
  const { currentUser } = useAuth();
  return currentUser?.role === "admin";
}
