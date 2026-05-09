import assert from "node:assert/strict";
import test from "node:test";

import { HEADER_MAX_PARENT_ITEMS, groupHeaderCategories } from "../src/shared/components/layout/header/categories/group-header-categories.ts";

test("groupCategoriesByParent deduplicates parent labels and limits roots", () => {
  const categories = [];
  for (let index = 1; index <= HEADER_MAX_PARENT_ITEMS + 4; index += 1) {
    categories.push({
      id: `root-${index}`,
      name: `Категория ${index}`,
      slug: `root-${index}`,
      parent: null,
    });
  }
  categories.push(
    {
      id: "dup-a",
      name: "Амортизатор",
      slug: "dup-a",
      parent: null,
    },
    {
      id: "dup-b",
      name: "  амортизатор  ",
      slug: "dup-b",
      parent: null,
    },
  );

  const grouped = groupHeaderCategories(categories);
  const normalized = new Set(grouped.map((item) => item.name.trim().replace(/\s+/g, " ").toLowerCase()));

  assert.equal(grouped.length <= HEADER_MAX_PARENT_ITEMS, true);
  assert.equal(grouped.length, normalized.size);
});

test("groupCategoriesByParent removes section items duplicating section title", () => {
  const grouped = groupHeaderCategories([
    { id: "root", name: "Подвеска", slug: "podveska", parent: null },
    { id: "child", name: "Амортизатор", slug: "amortizator", parent: { id: "root", name: "Подвеска", slug: "podveska" } },
    { id: "leaf-a", name: "Амортизатор", slug: "amortizator-a", parent: { id: "child", name: "Амортизатор", slug: "amortizator" } },
    { id: "leaf-b", name: "Стойка стабилизатора", slug: "stoyka", parent: { id: "child", name: "Амортизатор", slug: "amortizator" } },
  ]);

  assert.equal(grouped.length, 1);
  assert.equal(grouped[0].sections.length, 1);
  const section = grouped[0].sections[0];
  assert.equal(section.title, "Амортизатор");
  assert.deepEqual(section.items.map((item) => item.name), ["Стойка стабилизатора"]);
});
