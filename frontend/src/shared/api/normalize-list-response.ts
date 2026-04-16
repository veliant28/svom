export type PaginatedListResponse<T> = {
  count?: number;
  next?: string | null;
  previous?: string | null;
  results?: T[];
};

export type ListResponse<T> = T[] | PaginatedListResponse<T> | null | undefined;

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function normalizeListResponse<T>(data: ListResponse<T>): T[] {
  if (Array.isArray(data)) {
    return data;
  }

  if (isObjectRecord(data) && Array.isArray(data.results)) {
    return data.results;
  }

  return [];
}

export function normalizePaginatedListResponse<T>(data: ListResponse<T>): {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
} {
  const results = normalizeListResponse(data);

  if (!isObjectRecord(data)) {
    return {
      count: results.length,
      next: null,
      previous: null,
      results,
    };
  }

  return {
    count: typeof data.count === "number" ? data.count : results.length,
    next: typeof data.next === "string" || data.next === null ? data.next : null,
    previous: typeof data.previous === "string" || data.previous === null ? data.previous : null,
    results,
  };
}
