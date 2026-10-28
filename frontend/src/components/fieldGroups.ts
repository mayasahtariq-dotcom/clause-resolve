export const FIELD_GROUPS: { title: string; fields: string[] }[] = [
  { title: "Refunds", fields: ["refund_window", "refund_eligibility", "non_refundable_items"] },
  {
    title: "Cancellation & renewal",
    fields: ["cancellation_method", "cancellation_deadline", "cancellation_fee", "renewal_behavior"],
  },
  { title: "Free trials", fields: ["trial_duration", "trial_conversion"] },
  { title: "Physical returns", fields: ["restocking_fee", "return_shipping_liability"] },
  { title: "Fine print", fields: ["exceptions"] },
];

export const FALLBACK_LABELS: Record<string, string> = {
  refund_window: "Refund window",
  refund_eligibility: "Refund eligibility",
  cancellation_method: "Cancellation method",
  cancellation_deadline: "Cancellation deadline",
  cancellation_fee: "Cancellation fee",
  renewal_behavior: "Renewal behavior",
  trial_duration: "Trial duration",
  trial_conversion: "Trial-to-paid conversion",
  restocking_fee: "Restocking fee",
  return_shipping_liability: "Return shipping",
  non_refundable_items: "Non-refundable items",
  exceptions: "Exceptions & exclusions",
};
