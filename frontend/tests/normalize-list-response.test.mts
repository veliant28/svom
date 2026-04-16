import assert from "node:assert/strict";
import test from "node:test";

import { normalizeListResponse, normalizePaginatedListResponse } from "../src/shared/api/normalize-list-response.ts";

test("normalizeListResponse returns plain array unchanged", () => {
  const input = [{ id: "1" }, { id: "2" }];
  assert.deepEqual(normalizeListResponse(input), input);
});

test("normalizeListResponse extracts paginated results", () => {
  const input = {
    count: 2,
    next: null,
    previous: null,
    results: [{ id: "1" }, { id: "2" }],
  };

  assert.deepEqual(normalizeListResponse(input), input.results);
});

test("normalizeListResponse falls back to empty array for unexpected payload", () => {
  assert.deepEqual(normalizeListResponse({ foo: "bar" } as never), []);
  assert.deepEqual(normalizeListResponse(null), []);
});

test("normalizePaginatedListResponse preserves pagination metadata", () => {
  const input = {
    count: 7,
    next: "https://example.test/page=2",
    previous: null,
    results: [{ id: "1" }],
  };

  assert.deepEqual(normalizePaginatedListResponse(input), {
    count: 7,
    next: "https://example.test/page=2",
    previous: null,
    results: [{ id: "1" }],
  });
});

test("normalizePaginatedListResponse derives metadata for plain arrays", () => {
  const input = [{ id: "1" }, { id: "2" }];

  assert.deepEqual(normalizePaginatedListResponse(input), {
    count: 2,
    next: null,
    previous: null,
    results: input,
  });
});
