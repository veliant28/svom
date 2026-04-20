export type CheckoutPaymentMethod = "monobank" | "cash_on_delivery" | "novapay" | "liqpay";

export type MonobankWidgetInit = {
  key_id: string;
  request_id: string;
  signature: string;
  payload_base64: string;
};

export type MonobankWidgetResponse = {
  order_id: string;
  invoice_id: string;
  page_url: string;
  widget: MonobankWidgetInit | null;
  widget_error?: string;
};

export type MonobankSelectorWidgetResponse = {
  widget: MonobankWidgetInit | null;
  widget_error?: string;
};
