"use client";

import { Search } from "lucide-react";
import { useState } from "react";
import { useTranslations } from "next-intl";

import { HeaderIconButton } from "@/shared/components/layout/header/header-icon-control";
import { SearchModal } from "@/features/search/components/search/search-modal";

export function SearchHeaderControl() {
  const t = useTranslations("common.header");
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <HeaderIconButton
        tooltip={t("tooltips.search")}
        icon={<Search size={18} />}
        onClick={() => setIsOpen(true)}
        isActive={isOpen}
      />
      {isOpen ? <SearchModal isOpen={isOpen} onClose={() => setIsOpen(false)} /> : null}
    </>
  );
}
