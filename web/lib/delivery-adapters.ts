export type ProofChallengeResponse = {delivery_id: string; expires_at: string};
export type ProofSubmission = {otp: string; evidence_url?: string | null; recipient_name?: string | null; notes?: string | null};
export type DeliveryFailureReason = 'customer_unavailable' | 'address_not_found' | 'vehicle_issue' | 'merchant_issue' | 'unsafe_condition' | 'other';
export type DeliveryFailureSubmission = {reason: DeliveryFailureReason; notes?: string | null; evidence_url?: string | null};
export type DeliveryRecoverySubmission = {resolution: 'reassign' | 'return_to_store'; notes?: string | null};

export function toProofSubmission(sixDigitOtp: string, extras: Omit<ProofSubmission, 'otp'> = {}): ProofSubmission { return {otp: sixDigitOtp, ...extras}; }
export function toDeliveryFailureSubmission(reason: DeliveryFailureReason, notes?: string, evidenceUrl?: string): DeliveryFailureSubmission { return {reason, notes: notes || null, evidence_url: evidenceUrl || null}; }
