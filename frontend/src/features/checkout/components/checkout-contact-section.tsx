import type { Dispatch, SetStateAction } from "react";

import {
  PHONE_INPUT_MAX_LENGTH,
  PHONE_INPUT_PLACEHOLDER,
  PHONE_INPUT_REGEX,
  formatPhoneInput,
} from "@/shared/lib/phone-input";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function CheckoutContactSection({
  lastName,
  firstName,
  middleName,
  phone,
  t,
  setLastName,
  setFirstName,
  setMiddleName,
  setPhone,
  setIsLastNameDirty,
  setIsFirstNameDirty,
  setIsMiddleNameDirty,
  setIsPhoneDirty,
}: {
  lastName: string;
  firstName: string;
  middleName: string;
  phone: string;
  t: Translator;
  setLastName: Dispatch<SetStateAction<string>>;
  setFirstName: Dispatch<SetStateAction<string>>;
  setMiddleName: Dispatch<SetStateAction<string>>;
  setPhone: Dispatch<SetStateAction<string>>;
  setIsLastNameDirty: Dispatch<SetStateAction<boolean>>;
  setIsFirstNameDirty: Dispatch<SetStateAction<boolean>>;
  setIsMiddleNameDirty: Dispatch<SetStateAction<boolean>>;
  setIsPhoneDirty: Dispatch<SetStateAction<boolean>>;
}) {
  return (
    <>
      <h2 className="text-lg font-semibold">{t("sections.contact")}</h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div className="grid gap-3">
          <label className="flex flex-col gap-1 text-xs">
            {t("fields.lastName")}
            <input
              value={lastName}
              onChange={(event) => {
                setIsLastNameDirty(true);
                setLastName(event.target.value);
              }}
              required
              className="h-10 rounded-md border px-3"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            {t("fields.firstName")}
            <input
              value={firstName}
              onChange={(event) => {
                setIsFirstNameDirty(true);
                setFirstName(event.target.value);
              }}
              required
              className="h-10 rounded-md border px-3"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            />
          </label>
        </div>
        <div className="grid gap-3">
          <label className="flex flex-col gap-1 text-xs">
            {t("fields.middleName")}
            <input
              value={middleName}
              onChange={(event) => {
                setIsMiddleNameDirty(true);
                setMiddleName(event.target.value);
              }}
              className="h-10 rounded-md border px-3"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            {t("fields.phone")}
            <input
              value={phone}
              onChange={(event) => {
                setIsPhoneDirty(true);
                setPhone(formatPhoneInput(event.target.value));
              }}
              required
              placeholder={PHONE_INPUT_PLACEHOLDER}
              inputMode="numeric"
              pattern={PHONE_INPUT_REGEX.source}
              maxLength={PHONE_INPUT_MAX_LENGTH}
              title={PHONE_INPUT_PLACEHOLDER}
              className="h-10 rounded-md border px-3"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            />
          </label>
        </div>
      </div>
    </>
  );
}
