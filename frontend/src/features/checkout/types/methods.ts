import type { Order } from "@/features/commerce/types";
import type { CheckoutPaymentMethod } from "@/features/checkout/types/payment";

export type CheckoutMethods = {
  delivery_methods: Order["delivery_method"][];
  payment_methods: CheckoutPaymentMethod[];
};
