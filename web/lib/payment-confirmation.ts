import { ApiError, PaymentVerify } from "@/lib/api";

export type PaymentConfirmation = {
  orderId: string;
  orderNumber: string;
  payload: PaymentVerify;
};

// A client can lose the confirmation response after Razorpay has returned its
// signed callback. Only transient outcomes may be retried with that exact
// callback; invalid, unauthorized, or conflicting responses stay terminal.
export function canRetryPaymentConfirmation(error: unknown) {
  if (!(error instanceof ApiError)) return true;
  return error.status === 408 || error.status === 429 || error.status >= 500;
}
