export type VchasnoCodeEntry = {
  code: string;
};

export const VCHASNO_PAYMENT_METHOD_ENTRIES: readonly VchasnoCodeEntry[] = [
  { code: "0" },
  { code: "1" },
  { code: "2" },
  { code: "3" },
  { code: "4" },
  { code: "5" },
  { code: "6" },
  { code: "8" },
  { code: "11" },
  { code: "12" },
  { code: "13" },
  { code: "14" },
  { code: "15" },
  { code: "16" },
  { code: "17" },
  { code: "18" },
  { code: "19" },
  { code: "20" },
] as const;

export const VCHASNO_TAX_GROUP_ENTRIES: readonly VchasnoCodeEntry[] = [
  { code: "А" },
  { code: "В" },
  { code: "З" },
  { code: "Б" },
  { code: "Е" },
  { code: "ИК" },
  { code: "ГД" },
  { code: "Ж" },
  { code: "Л" },
] as const;
