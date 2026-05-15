import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const root = process.cwd();

function readProjectFile(path: string) {
  return readFileSync(join(root, path), "utf8");
}

const ruMessages = JSON.parse(readProjectFile("src/messages/ru/backoffice/autodb-matching.json"));

test("Auto_DB matching tabs and titles use exact Russian labels", () => {
  const tabs = ruMessages.backoffice.autodbMatching.tabs;

  assert.deepEqual([tabs.dashboard, tabs.products, tabs.search], ["Дашборд", "Товары", "Поиск"]);
  assert.equal(tabs.dashboardTitle, "Операционный дашборд");
  assert.equal(tabs.productsTitle, "Несвязанные товары");
  assert.equal(tabs.searchTitle, "Поиск в Auto-DB");
});

test("Auto_DB matching quota widget is line/area chart, not gauge", () => {
  const quotaCard = readProjectFile("src/features/backoffice/components/autodb-matching/quota-card.tsx");

  assert.match(quotaCard, /type:\s*"line"/);
  assert.match(quotaCard, /areaStyle/);
  assert.doesNotMatch(quotaCard, /type:\s*"gauge"|Gauge|progress ring|circular/i);
});

test("Auto_DB matching remote search is disabled and dashboard shows quota toast when paused", () => {
  const searchTab = readProjectFile("src/features/backoffice/components/autodb-matching/search-tab.tsx");
  const dashboardTab = readProjectFile("src/features/backoffice/components/autodb-matching/dashboard-tab.tsx");

  assert.match(searchTab, /quotaPaused/);
  assert.match(searchTab, /remoteDisabled/);
  assert.match(dashboardTab, /quota\?\.status === "quota_paused"/);
  assert.match(dashboardTab, /showWarning\(t\("quota\.remoteDisabled"\)\)/);
});
