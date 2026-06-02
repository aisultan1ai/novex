import { apiFormDataRequest, apiRequest, ApiError } from "./client";

export { ApiError };

export interface BankDetails {
  recipient_name: string;
  bank_name: string;
  iban: string;
  bin: string;
  knp: string;
  purpose: string;
  amount: string;
  currency: string;
}

export interface PaymentData {
  payment_id: number;
  order_reference: string;
  status: string;
  bank_details: BankDetails;
}

export async function initiatePayment(orderId: string): Promise<PaymentData> {
  return apiRequest<PaymentData>(
    `/payments/orders/${orderId}/initiate-bank-transfer`,
    { method: "POST" },
  );
}

export async function getPaymentStatus(
  orderId: string,
): Promise<{ status: string }> {
  try {
    return await apiRequest<{ status: string }>(
      `/payments/orders/${orderId}/payment-status`,
    );
  } catch {
    return { status: "unknown" };
  }
}

export async function uploadPaymentProof(
  orderId: string,
  paymentId: number,
  file: File,
): Promise<void> {
  const form = new FormData();
  form.append("payment_id", String(paymentId));
  form.append("file", file);
  await apiFormDataRequest<unknown>(
    `/payments/orders/${orderId}/upload-proof`,
    form,
  );
}
