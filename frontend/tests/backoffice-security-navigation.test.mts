import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const sidebarSource = readFileSync(
  resolve("src/features/backoffice/components/layout/backoffice-sidebar.tsx"),
  "utf8",
);

test("places security center immediately after dashboard and before support", () => {
  const dashboardIndex = sidebarSource.indexOf('key: "dashboard"');
  const securityIndex = sidebarSource.indexOf('key: "securityCenter"');
  const supportIndex = sidebarSource.indexOf('key: "support"');

  assert.ok(dashboardIndex >= 0);
  assert.ok(securityIndex > dashboardIndex);
  assert.ok(supportIndex > securityIndex);
});

test("security center uses security.view capability", () => {
  const securityItemPattern = /href: "\/backoffice\/security"[\s\S]+?requiredCapability: BACKOFFICE_CAPABILITIES\.securityView/;

  assert.match(sidebarSource, securityItemPattern);
});
