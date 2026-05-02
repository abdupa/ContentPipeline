# Price Ingestion QA Test Cases

Use this manual to validate Shopee/Lazada Google Sheet parsing, review, and WooCommerce sync changes.

Validation levels:

- `Code Validated`: compile/build checks passed.
- `Workflow Validated`: local UI/backend flow was executed successfully.
- `Live Sync Validated`: WooCommerce was updated and verified by inspecting the WooCommerce product.
- `Deferred`: test is documented but intentionally not executed yet.

## Current QA Status

| Ref | Area | Status | Last Result | Notes |
| --- | --- | --- | --- | --- |
| QA-PI-001 | Backend/frontend build gate | Passed | 2026-05-02 | `compileall` and `npm run build` passed. |
| QA-PI-002 | Shopee importer staging | Deferred | Not run | Requires running real Tools importer. |
| QA-PI-003 | Lazada importer staging | Deferred | Not run | Requires running real Tools importer. |
| QA-PI-004 | Review UI diagnostics | Failed, fix in progress | 2026-05-02 | Lazada staged review showed matched rows with `Matched By = Unmatched`; frontend fallback and backend ID map strengthening added. Needs retest. |
| QA-PI-005 | Audit `price_before` report | Deferred | Not run | Requires syncing a safe product and checking Sync Report. |
| QA-PI-006 | Importer failure status | Deferred | Not run | Requires bad sheet/source test. |
| QA-PI-007 | Unlink/reset mapping | Deferred | Not run | Requires safe WooCommerce product ID. |
| QA-PI-008 | WooCommerce live sync inspection | Deferred | Not run | Requires live sync and `data_tasks.py WOO_PRODUCT_ID`. |

## Shared Setup

Run from repo root unless noted.

```bash
git branch --show-current
git status --short
docker-compose ps
```

Expected:

- Branch is the intended working branch.
- Backend, worker, Redis, and frontend services are healthy enough for the workflow.
- Any dirty files are understood before testing.

## QA-PI-001: Build And Compile Gate

Purpose: prove the code can compile and frontend can produce a production build.

Commands:

```bash
PYTHONPYCACHEPREFIX=/tmp/contentpipeline-pycache python3 -m compileall -q backend
cd frontend
npm run build
```

Pass criteria:

- Backend compile exits `0`.
- Frontend build exits `0`.
- No new build warning requires action.

Evidence to record:

```text
Date:
Branch:
Commit:
Backend compile result:
Frontend build result:
Notes:
```

Latest result:

```text
Date: 2026-05-02
Branch: audit-price-ingestion-refinements
Commit: 51bc152
Backend compile result: Passed
Frontend build result: Passed
Notes: This is code validation only, not live workflow validation.
```

## QA-PI-002: Shopee Importer Staging

Purpose: prove the Shopee Tools button parses the configured Google Sheet and stages review rows.

Steps:

1. Open frontend.
2. Go to `Tools`.
3. Click the Shopee importer.
4. Wait for Job Status to finish.
5. Open `Review Staged Updates`.

Pass criteria:

- Job reaches `complete`.
- Job does not stay stuck on `starting` or `processing`.
- Staged rows include Shopee source fields:
  - `source = shopee`
  - `shopee_id`
  - `shop_id`
  - `stock_status`
  - `matched_by`
  - `new_sale_price` or `new_regular_price`

Evidence to record:

```text
Date:
Branch:
Commit:
Job ID:
Rows staged:
Matched rows:
Unmatched rows:
Sample Woo product ID:
Notes:
```

## QA-PI-003: Lazada Importer Staging

Purpose: prove the Lazada Tools button parses the configured Google Sheet and stages review rows.

Steps:

1. Open frontend.
2. Go to `Tools`.
3. Click the Lazada importer.
4. Wait for Job Status to finish.
5. Open `Review Staged Updates`.

Pass criteria:

- Job reaches `complete`.
- Job does not stay stuck on `starting` or `processing`.
- Staged rows include Lazada source fields:
  - `source = lazada`
  - `lazada_id`
  - `shop_id`
  - `stock_status`
  - `matched_by`
  - `new_sale_price` or `new_regular_price`

Evidence to record:

```text
Date:
Branch:
Commit:
Job ID:
Rows staged:
Matched rows:
Unmatched rows:
Sample Woo product ID:
Notes:
```

## QA-PI-004: Review UI Match Diagnostics

Purpose: prove reviewers can see why a row matched.

Steps:

1. Open a staged Shopee or Lazada job.
2. Check desktop review table.
3. Check mobile width around `390x844`.
4. Manually link one unmatched row to a local product if safe.

Pass criteria:

- Each row shows a readable `Matched By` value:
  - `Marketplace ID`
  - `Exact Name`
  - `Manual Link`
  - `Unmatched`
- Long marketplace IDs remain visible.
- Manual link changes the badge to `Manual Link`.
- Price fields and actions remain usable on mobile.

Evidence to record:

```text
Date:
Branch:
Commit:
Viewport checked:
Sample row source:
Sample matched_by:
Manual link tested:
Notes:
```

## QA-PI-005: Sync Report Price Before/After

Purpose: prove the audit report captures the old price before overwriting local price fields.

Steps:

1. Choose one safe matched product.
2. Record the current WooCommerce/local DB price before sync.
3. Approve only that product.
4. Sync to WooCommerce.
5. Open Sync Report.

Pass criteria:

- Report shows `Price Updated` when the new winning price differs.
- Report shows `Synced` when the numeric value is effectively the same.
- `price_before` equals the pre-sync price.
- `price_after` equals the winning Shopee/Lazada price.

Evidence to record:

```text
Date:
Branch:
Commit:
Job ID:
Woo product ID:
Source:
Price before:
Price after:
Report status:
Notes:
```

## QA-PI-006: Importer Failure Status

Purpose: prove importer failures update Redis job status to `failed`.

Safe test option:

Use the generic endpoint with an invalid source or invalid sheet URL.

Example:

```bash
curl -s -X POST http://localhost:8000/api/import/google-sheet \
  -H 'Content-Type: application/json' \
  -d '{"sheet_url":"https://docs.google.com/spreadsheets/d/invalid/edit","source":"shopee"}'
```

Pass criteria:

- Invalid `source` returns HTTP `400`.
- Runtime importer failure updates `job:{job_id}` to `failed`.
- Job Status UI shows failure instead of staying stuck.

Evidence to record:

```text
Date:
Branch:
Commit:
Endpoint used:
Job ID:
Observed status:
Error message:
Notes:
```

## QA-PI-007: Unlink / Reset Mapping

Purpose: prove Reset sends WooCommerce product ID and clears source mapping safely.

Steps:

1. Select a safe product that can be reset.
2. Record WooCommerce product ID and current source meta.
3. In Review UI, click `Reset`.
4. Confirm action.
5. Inspect the WooCommerce product.

Inspector command:

```bash
docker-compose exec backend python data_tasks.py WOO_PRODUCT_ID
```

Pass criteria:

- Request posts to `/api/unlink-product`.
- Backend receives `product_id`.
- WooCommerce product clears source metadata:
  - `_shopee_id`
  - `_lazada_id`
  - `_shopee_price`
  - `_lazada_price`
  - source URLs and histories
- No unrelated product is changed.

Evidence to record:

```text
Date:
Branch:
Commit:
Woo product ID:
Before meta summary:
After meta summary:
Notes:
```

## QA-PI-008: WooCommerce Live Sync Inspection

Purpose: prove final sync updates WooCommerce product fields and metadata correctly.

Steps:

1. Sync a safe single product from Review UI.
2. Wait for sync job to complete.
3. Inspect the WooCommerce product by Woo product ID.

Command:

```bash
docker-compose exec backend python data_tasks.py WOO_PRODUCT_ID
```

Pass criteria:

- WooCommerce `price`, `regular_price`, and `sale_price` match expected winning source.
- `external_url` points to the winning source affiliate URL.
- `button_text` matches the winning source.
- `meta_data` includes updated source price, URL, last updated timestamp, and price history.
- `_price_history` matches the winning source history.

Evidence to record:

```text
Date:
Branch:
Commit:
Sync job ID:
Woo product ID:
Winning source:
Expected price:
Observed price:
External URL updated:
Source meta updated:
Notes:
```

## Deferred Test Log

Use this when we intentionally move forward without a real pass.

```text
Date:
Deferred refs:
Reason:
Risk accepted:
Planned validation window:
Owner:
```

## Completed Test Log

Append real test passes here.

```text
Date:
Ref:
Result:
Branch:
Commit:
Evidence:
Notes:
```

```text
Date: 2026-05-02
Ref: QA-PI-004
Result: Failed
Branch: audit-price-ingestion-refinements
Commit: a2f9923
Evidence: Lazada Review Price Updates screenshot for job import_lazada_cb576190 showed rows with Status = MATCHED but Matched By = Unmatched.
Notes: Fix added to infer match source from matched Woo product for legacy/current staged rows. Backend matching hierarchy remains unchanged: source product ID, exact cleaned name, then fuzzy suggestion only.
```
