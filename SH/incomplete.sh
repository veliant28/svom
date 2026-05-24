#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

docker compose exec -T backend python manage.py shell -c "from apps.autodb.models import AutoDbSyncState as S
order=['manufacturers','models','passanger_cars','passanger_car_attributes','passanger_car_engines','passanger_car_trees','commercial_vehicles','motorbikes','engines','axles','suppliers','supplier_details','suppliers_with_nv_articles','suppliers_with_nv_linkages','countries','country_groups','languages','prd','manufacturers_of_new_linkages','articles','article_numbers','article_prd','article_cross','article_oe','article_nn','article_li','article_links']
mp={s.source_table:s for s in S.objects.all()}
print('table\tprocessed\ttotal\tpercent\tstatus\terror')
for t in order:
 s=mp.get(t)
 if not s:
  print(f'{t}\t0\t0\t0.00\tnone\tno_state')
  continue
 p=s.processed_rows or 0
 tot=s.total_rows or 0
 pct=(p*100.0/tot) if tot else 0.0
 status=s.status or 'none'
 err=(s.last_error or '').replace('\n',' ')[:120]
 complete=(status=='completed' and tot>0 and p>=tot)
 if not complete:
  print(f'{t}\t{p}\t{tot}\t{pct:.2f}\t{status}\t{err}')"
