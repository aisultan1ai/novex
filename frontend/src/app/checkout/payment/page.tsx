"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function PaymentRedirect() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const orderId = searchParams.get("orderId");

  useEffect(() => {
    if (orderId) {
      router.replace(`/checkout?draftId=${orderId}`);
    } else {
      router.replace("/dashboard/orders");
    }
  }, [orderId, router]);

  return null;
}

export default function PaymentPage() {
  return <Suspense><PaymentRedirect /></Suspense>;
}
