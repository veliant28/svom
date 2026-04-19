import { useCallback, useState } from "react";

export function useOrderFilters() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);

  const onSearchChange = useCallback((value: string) => {
    setQ(value);
    setPage(1);
  }, []);

  const onStatusChange = useCallback((value: string) => {
    setStatus(value);
    setPage(1);
  }, []);

  return {
    q,
    status,
    page,
    setPage,
    onSearchChange,
    onStatusChange,
  };
}
