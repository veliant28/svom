#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

INTERVAL="${1:-15}"
MODE="${2:-loop}"

render_once() {
  clear 2>/dev/null || true
  echo "=== AutoDB Monitor $(date '+%Y-%m-%d %H:%M:%S') ==="
  docker compose exec -T backend python manage.py shell -c "from apps.autodb.models import AutoDbSyncState as S
order=['manufacturers','models','passanger_cars','passanger_car_attributes','passanger_car_engines','passanger_car_trees','commercial_vehicles','motorbikes','engines','axles','suppliers','supplier_details','suppliers_with_nv_articles','suppliers_with_nv_linkages','countries','country_groups','languages','prd','manufacturers_of_new_linkages','articles','article_numbers','article_prd','article_cross','article_oe','article_nn','article_li','article_links']
mp={s.source_table:s for s in S.objects.all()}
print('table\tstatus\tprocessed\ttotal\tpercent\terror')
for t in order:
 s=mp.get(t)
 if not s:
  print(f'{t}\tnone\t0\t0\t0.00\t')
  continue
 p=s.processed_rows or 0
 tot=s.total_rows or 0
 pct=(p*100.0/tot) if tot else 0.0
 err=(s.last_error or '').replace('\n',' ')[:80]
 print(f'{t}\t{s.status}\t{p}\t{tot}\t{pct:.2f}\t{err}')" | sed 's/\t/ | /g'
}

if [[ "$MODE" == "once" ]]; then
  render_once
  exit 0
fi

while true; do
  render_once
  sleep "$INTERVAL"
done
