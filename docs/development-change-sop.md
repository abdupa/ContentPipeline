# Development Change SOP

Use this SOP before changing code, especially in flows that touch Google Sheets parsing, WooCommerce updates, or user-facing review screens.

## 1. Inspect Existing State

Before editing:

```bash
git status --short
git branch --show-current
```

Then inspect the relevant files and routes:

```bash
rg -n "keyword_or_endpoint" backend frontend
sed -n 'START,ENDp' path/to/file
```

Capture:

- Which files own the behavior.
- Which endpoint/task/component starts the flow.
- What data shape enters and leaves each step.
- Whether there are existing uncommitted changes in the same files.

Do not overwrite unrelated dirty work.

## 2. Define Expected Behavior

Write down the expected behavior before editing:

```text
Current behavior:
- What happens now?

Expected behavior after change:
- What should happen?
- Which inputs should still be accepted?
- Which payload fields must remain compatible?

Risk:
- What could break?
- Which UI/backend paths need validation?
```

For price ingestion, explicitly identify:

- Source: Shopee, Lazada, or generic.
- Mapping key: marketplace product ID, shop ID, name fallback, or manual link.
- Target key: WooCommerce/local product ID.
- Review state: matched, unmatched, ignored, approved, linked.

## 3. Plan The Smallest Safe Change

Prefer scoped changes:

- One flow at a time.
- One UI surface at a time.
- One backend task/endpoint at a time.

Avoid unrelated refactors while fixing behavior. If a broader cleanup is discovered, add it to the audit tracker first.

## 4. Implement

Before editing, mention what files and behavior are being changed.

Use existing project patterns:

- FastAPI endpoints in `backend/main.py`.
- Celery and WooCommerce sync logic in `backend/data_tasks.py`.
- Parser helpers in `backend/sheet_parser.py`.
- Price workflow UI in `frontend/src/components/*`.
- Audit notes in `docs/audits/`.

Keep payload compatibility unless intentionally changing a contract.

## 5. Validate Locally

Frontend:

```bash
cd frontend
npm ci
npm run build
```

If Docker owns local dependencies, fix the empty host `node_modules` folder or build through Docker:

```bash
docker-compose exec frontend npm run build
```

Backend syntax:

```bash
PYTHONPYCACHEPREFIX=/tmp/contentpipeline-pycache python -m compileall -q backend
```

Docker health:

```bash
docker-compose ps
```

Known current lint baseline:

```bash
cd frontend
npm run lint
```

As of 2026-05-02, lint is not yet a CI gate because it reports pre-existing issues in plugin folders and older React files. Add lint to CI only after the baseline is cleaned or narrowed.

## 6. Validate User Flow

For price workflow UI changes:

```text
Tools
  -> Run Shopee/Lazada importer
  -> Job Status
  -> Review Staged Updates
  -> Save Changes
  -> Sync to WooCommerce
  -> Sync Report
```

Check at minimum:

- Mobile width around `390x844`.
- Tablet width around `768x1024`.
- Desktop width around `1366x768`.
- Long marketplace IDs are visible.
- Product names do not hide price fields or actions.
- Buttons do not overflow.
- Submitted payload still includes approved products with `matched_db_id` or `linked_db_id`.

## 7. Update Audit/Tracker

If the change relates to an audit item, update the relevant file:

- `docs/audits/price-ingestion-flow-audit.md`
- `docs/audits/frontend-price-workflow-ui-audit.md`

Use the implementation tracker and append-only findings log.

## 8. Review Diff Before Commit

```bash
git diff --stat
git diff -- path/to/changed/files
git status --short
```

Confirm the commit contains only intentional files. Do not include unrelated dirty files.

## 9. Commit And Push

```bash
git add path/to/files
git commit -m "Type: concise summary"
git push
```

If push is rejected because remote has newer work:

```bash
git pull --rebase --autostash origin main
git push
```

If conflicts appear, stop and resolve intentionally.

## 10. CI Gate

GitHub Actions validation runs on push and pull request to `main`:

- Frontend `npm ci`
- Frontend `npm run build`
- Backend `python -m compileall`

Do not merge or continue implementation on top of a failing validation gate unless the failure is understood and documented.
