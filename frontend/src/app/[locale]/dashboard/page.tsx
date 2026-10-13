"use client";
import { useEffect } from "react";
import { useRouter } from "@/i18n/navigation";

export default function DashboardPage() {
  const router = useRouter();
  useEffect(() => { router.replace("/dashboard/orders"); }, [router]);
  return null;
}