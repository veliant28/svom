# SH scripts for AutoDB clone

Each table has its own script with resume support:

- `./SH/<table>.sh`

Examples:

- `./SH/passanger_car_trees.sh`
- `./SH/articles.sh`

## Guarantees

- Resume from current remote cursor/state (`--resume`)
- Realtime output in terminal
- Timestamped logs from command and wrapper
- Retries for transient network/quota issues
- Skips access-restricted tables without breaking flow

## Environment overrides (optional)

- `WAIT_FOR_AUTODB=120`
- `MAX_RETRIES=8`
- `RETRY_DELAY_SECONDS=45`
- `BATCH_SIZE_OVERRIDE=20`
- `PROGRESS_EVERY_OVERRIDE=1`
- `LIMIT_ROWS=5000`

Usage example:

```bash
WAIT_FOR_AUTODB=120 MAX_RETRIES=10 RETRY_DELAY_SECONDS=30 ./SH/passanger_car_trees.sh
```

## Monitoring

- One-shot:
  - `./SH/monitor.sh 15 once`
- Live loop every 15 sec:
  - `./SH/monitor.sh 15`
- Show only incomplete tables:
  - `./SH/incomplete.sh`
