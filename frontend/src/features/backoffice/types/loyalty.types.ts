export type BackofficeLoyaltyCustomerOption = {
  id: string;
  email: string;
  full_name: string;
  label: string;
};

export type BackofficeLoyaltyPromo = {
  id: string;
  code: string;
  discount_type: "delivery_fee" | "product_markup";
  discount_percent: string;
  usage_limit: number;
  usage_count: number;
  reason: string;
  status: "active" | "disabled";
  state: "active" | "used" | "expired" | "disabled";
  is_expired: boolean;
  is_used: boolean;
  is_used_up: boolean;
  is_active: boolean;
  expires_at: string | null;
  issued_at: string;
  issued_by: {
    id: string | null;
    email: string;
    name: string;
  };
  customer: {
    id: string | null;
    email: string;
    name: string;
  };
  last_redeemed_at: string | null;
  last_redeemed_order_id: string | null;
};

export type BackofficeLoyaltyStaffStats = {
  staff_id: string;
  staff_email: string;
  staff_name: string;
  issued_total: number;
  issued_delivery: number;
  issued_product: number;
  nominal_percent_total: string;
  discount_sum_total: string;
  used_total: number;
  conversion_rate: string;
};

export type BackofficeLoyaltyStatsResponse = {
  staff: BackofficeLoyaltyStaffStats[];
  chart: {
    by_day: Array<{
      date: string;
      total: number;
    }>;
  };
};
