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
| QA-PI-004 | Review UI diagnostics | Failed, fix in progress | 2026-05-02 | Lazada staged review showed matched rows with `Matched By = Unmatched`; frontend display fallback added. Needs retest. |
| QA-PI-009 | Lazada product name normalization | Code Validated | 2026-05-02 | Sample parser check normalized noisy Lazada names such as `vivo Y05 mobilephone|...` to `vivo Y05`. Needs real importer retest. |
| QA-PI-005 | Audit `price_before` report | Code Validated | 2026-05-02 | Sync Report now displays before/after price and delta. Needs real report retest. |
| QA-PI-006 | Importer failure status | Deferred | Not run | Requires bad sheet/source test. |
| QA-PI-007 | Unlink/reset mapping | Deferred | Not run | Requires safe WooCommerce product ID. |
| QA-PI-008 | WooCommerce live sync inspection | Deferred | Not run | Requires live sync and `data_tasks.py WOO_PRODUCT_ID`. |
| QA-PI-010 | Affiliate URL diagnostics | Live Sync Validated | 2026-05-02 | Review/sync UI and WooCommerce meta confirmed valid Shopee/Lazada affiliate diagnostics. |
| QA-PI-011 | Manual link live Woo fallback | Code Validated | 2026-05-02 | Local cache miss can search live WooCommerce. Needs UI retest with `Samsung Galaxy S26 Ultra`. |
| QA-PI-012 | Stored source affiliate diagnostics backfill | Live Sync Validated | 2026-05-02 | Existing Shopee winning source showed `Valid` in Sync Report and WooCommerce meta. |
| QA-PI-013 | Candidate bucket save | Workflow Validated | 2026-05-02 | Unmatched Lazada row saved to Candidate Bucket and displayed with affiliate status. |
| QA-PI-014 | Candidate management | Workflow Validated | 2026-05-02 | Candidate status/type/notes save and persist in Candidate Bucket. |

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
- Sync Report displays a visible `Price Change` value in `before -> after` format.
- Sync Report displays a delta, including `No price change` for unchanged prices.

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
Price change display:
Notes:
```

## QA-PI-010: Affiliate URL Diagnostics

Purpose: prove the importer surfaces whether Shopee/Lazada affiliate URL generation produced a tracked affiliate URL or a fallback URL.

Steps:

1. Run the Shopee importer and open `Review Staged Updates`.
2. Confirm staged rows show an `Affiliate` badge.
3. Run the Lazada importer and open `Review Staged Updates`.
4. Confirm staged rows show an `Affiliate` badge.
5. Approve one safe matched row and sync to WooCommerce.
6. Open `Sync Audit Report`.
7. Inspect the WooCommerce product meta using `docker-compose exec backend python data_tasks.py <WOO_PRODUCT_ID>`.

Pass criteria:

- Review rows show one of:
  - `Valid`
  - `Fallback URL`
  - `Missing Config`
  - `Parse Failed`
  - `Missing Link`
- Shopee rows with generated tracking params show `Valid`.
- Lazada rows show `Valid` when `LAZADA_AFFILIATE_PID` is configured.
- Lazada rows show `Missing Config` when `LAZADA_AFFILIATE_PID` is absent.
- Sync Report shows the winning source affiliate status and detail.
- WooCommerce meta includes source-specific diagnostic keys such as:
  - `_shopee_affiliate_status`
  - `_shopee_affiliate_detail`
  - `_lazada_affiliate_status`
  - `_lazada_affiliate_detail`

Evidence to record:

```text
Date:
Branch:
Commit:
Source tested:
Job ID:
Woo product ID:
Review affiliate badge:
Sync report affiliate badge:
Woo meta affiliate status:
Notes:
```

## QA-PI-011: Manual Link Live Woo Fallback

Purpose: prove manual link can find a live WooCommerce product even when `product_database.json` is stale.

Steps:

1. Open a staged import containing an unmatched row.
2. In the manual-link search field, search a known live Woo product that is missing from local cache, such as `Samsung Galaxy S26 Ultra`.
3. Wait for live search results.
4. Select the live Woo result.

Pass criteria:

- Search result appears even if local `product_database.json` does not contain the product.
- Result label shows `Live Woo`.
- Selecting the result sets the row to manual link.
- Linked row shows the WooCommerce product ID.
- Sync payload uses the selected WooCommerce ID.

Evidence to record:

```text
Date:
Branch:
Commit:
Staged job ID:
Search term:
Live Woo product ID:
Manual link result:
Notes:
```

## QA-PI-012: Stored Source Affiliate Diagnostics Backfill

Purpose: prove older linked sources show affiliate status in Sync Report even when their diagnostics were not created during staging.

Steps:

1. Run a Lazada importer for products that already have older Shopee linked source data.
2. Approve safe matched rows.
3. Sync to WooCommerce.
4. Open Sync Audit Report.
5. Find a row where `Details` says `Winner: Shopee`.

Pass criteria:

- Winning old Shopee rows do not show `Affiliate URL = Not Checked`.
- Rows show `Valid`, `Fallback URL`, `Missing Link`, or `Parse Failed` based on the stored Shopee URL.
- Existing affiliate URL is not regenerated or changed just to calculate diagnostics.

Evidence to record:

```text
Date:
Branch:
Commit:
Job ID:
Woo product ID:
Winning source:
Affiliate badge:
Notes:
```

## QA-PI-013: Candidate Bucket Save

Purpose: prove unmatched staged marketplace products can be preserved for later research without syncing them to WooCommerce.

Steps:

1. Run Shopee or Lazada importer.
2. Open `Review Staged Updates`.
3. Find an unmatched row.
4. Click `Add to Bucket`.
5. Open `Tools`.
6. Click `Candidate Bucket`.
7. Confirm the candidate appears.
8. Sync approved rows, if safe.

Pass criteria:

- Unmatched row changes to a candidate/bucketed state.
- Candidate persists after navigating away and back.
- Candidate includes:
  - source
  - marketplace product ID
  - parsed/canonical name
  - original URL
  - affiliate URL/status
  - regular/sale price
  - stock status
  - import job ID
- Bucketed row is not included in WooCommerce sync.

Evidence to record:

```text
Date:
Branch:
Commit:
Import job ID:
Source:
Candidate ID:
Marketplace product ID:
Affiliate badge:
Sync excluded bucketed row:
Notes:
```

## QA-PI-014: Candidate Management

Purpose: prove candidate review fields can be managed without mutating WooCommerce.

Steps:

1. Open `Tools`.
2. Open `Candidate Bucket`.
3. Edit a candidate canonical name.
4. Select a type tag, such as `earbuds` or `phone`.
5. Change status, such as `researching` or `linked_existing`.
6. Add notes.
7. Search and select an existing live Woo product in the Woo Link field.
8. Click `Save`.
9. Refresh or leave/reopen Candidate Bucket.

Pass criteria:

- Canonical name persists.
- Type tag persists.
- Status persists.
- Notes persist.
- Linked Woo product ID/name persists.
- No WooCommerce price, URL, meta, or product record is changed by this save.
- Disabled `Scrape Later` button remains non-functional.

Evidence to record:

```text
Date:
Branch:
Commit:
Candidate ID:
Canonical name:
Type tag:
Status:
Linked Woo ID:
Notes persisted:
Woo mutation checked:
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

## QA-PI-009: Lazada Product Name Normalization

Purpose: prove noisy Lazada title text is reduced to a concise product name without changing the primary product-ID matching hierarchy.

Sample command:

```bash
docker-compose exec backend python - <<'PY'
from sheet_parser import clean_product_name_lazada
samples = [
    "vivo Y05 mobilephone|6500 mAh BlueVolt Battery|IP65 Dust and Water Resistance",
    "[AVAILABLE NOW] vivo Y21d cellphone丨6500 mAh BlueVolt Battery & 44W Flash Charge",
    "vivo V70 FE Mobile phone|200MP OIS Ultra-Clear Al Imaging|7000mAh BlueVolt Battery",
    "vivo Color Earphone",
]
for sample in samples:
    print(clean_product_name_lazada(sample))
PY
```

Pass criteria:

- Phone titles keep brand and model only where practical.
- Feature/spec text after `|` or `丨` is removed.
- Generic words such as `mobilephone`, `mobile phone`, and `cellphone` are removed.
- Accessory names such as `vivo Color Earphone` are not damaged.
- Backend matching hierarchy remains unchanged:
  1. source product ID
  2. exact cleaned name
  3. fuzzy suggestion only

Evidence to record:

```text
Date:
Branch:
Commit:
Input sample:
Expected normalized name:
Observed normalized name:
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

```text
Date: 2026-05-02
Ref: QA-PI-009
Result: Code Validated
Branch: audit-price-ingestion-refinements
Commit: pending
Evidence: Docker parser sample check returned `vivo Y05`, `vivo Y21d`, `vivo Y04s`, `vivo V70`, `vivo X300 series 5G`, `vivo V70 FE`, `vivo Y11d`, `vivo Watch 3`, `vivo Color Earphone`, `vivo Buds Air3`, and `vivo 44W Original Fast Charger`.
Notes: Needs real Lazada importer retest before marking Workflow Validated.
```

```text
Date: 2026-05-02
Ref: QA-PI-010
Result: Code Validated
Branch: audit-price-ingestion-refinements
Commit: pending
Evidence: `PYTHONPYCACHEPREFIX=/tmp/contentpipeline-pycache python3 -m compileall -q backend` passed; `npm run build` in `frontend` passed; backend container smoke test returned `Valid` for sample Shopee and Lazada affiliate URLs.
Notes: Needs real Shopee/Lazada importer retest, sync report check, and WooCommerce meta inspection before marking Workflow Validated or Live Sync Validated.
```

```text
Date: 2026-05-02
Ref: QA-PI-010
Result: Failed / Fix Applied
Branch: audit-price-ingestion-refinements
Commit: pending
Evidence: Real Lazada staged review showed `Affiliate = Not Checked` on all rows after worker restart.
Notes: Root cause was backend `StagedProduct` response/payload model filtering out `affiliate_diagnostics`; field added for retest.
```

```text
Date: 2026-05-02
Ref: QA-PI-011
Result: Code Validated
Branch: audit-price-ingestion-refinements
Commit: pending
Evidence: Added `/api/products/search-live` and manual-link live Woo fallback.
Notes: Needs UI retest by searching `Samsung Galaxy S26 Ultra` and selecting Woo product ID `45720`.
```

```text
Date: 2026-05-02
Ref: QA-PI-012
Result: Code Validated
Branch: audit-price-ingestion-refinements
Commit: pending
Evidence: Added sync-time diagnostics derivation from stored source `affiliate_url` when `affiliate_diagnostics` is absent.
Notes: Needs real sync retest where `Winner: Shopee` appears during a Lazada import sync.
```

```text
Date: 2026-05-02
Ref: QA-PI-013
Result: Code Validated
Branch: audit-price-ingestion-refinements
Commit: pending
Evidence: Added `/api/product-candidates`, `/api/product-candidates/from-staged`, Review UI `Add to Bucket`, and Tools Candidate Bucket view.
Notes: Needs real staged-row validation before marking Workflow Validated.
```

```text
Date: 2026-05-02
Ref: QA-PI-013
Result: Workflow Validated
Branch: audit-price-ingestion-refinements
Commit: pending
Evidence: Candidate Bucket screenshot showed unmatched Lazada candidate `Samsung Galaxy Buds4` with source product ID `5411480006`, regular price `₱11,490`, affiliate status `Valid`, nearest match `samsung galaxy buds3`, and updated timestamp.
Notes: Confirms unmatched staged row can be saved and reviewed without WooCommerce sync.
```

```text
Date: 2026-05-02
Ref: QA-PI-014
Result: Code Validated
Branch: audit-price-ingestion-refinements
Commit: pending
Evidence: Added `PATCH /api/product-candidates/{candidate_id}` and editable Candidate Bucket controls for canonical name, type tag, status, notes, and linked Woo product.
Notes: Needs UI workflow validation before marking Workflow Validated.
```

```text
Date: 2026-05-02
Ref: QA-PI-014
Result: Workflow Validated
Branch: audit-price-ingestion-refinements
Commit: pending
Evidence: Candidate Bucket screenshot confirmed `Samsung Galaxy Buds4` saved with status `researching`, type `earbuds`, note `Test note`, and updated timestamp after clicking Save.
Notes: Confirms candidate management persists review metadata without enabling scraper handoff.
```

```text
Date: 2026-05-02
Ref: QA-PI-010
Result: Live Sync Validated
Branch: audit-price-ingestion-refinements
Commit: pending
Evidence: Sync Audit Report showed Lazada `Affiliate URL = Valid`; WooCommerce meta contained `_shopee_affiliate_status = valid`, `_shopee_affiliate_detail = Shopee affiliate parameters are present.`, `_lazada_affiliate_status = valid`, and `_lazada_affiliate_detail = Lazada affiliate parameters are present.`
Notes: Confirms staged diagnostics, sync report display, and WooCommerce meta persistence.
```

```text
Date: 2026-05-02
Ref: QA-PI-012
Result: Live Sync Validated
Branch: audit-price-ingestion-refinements
Commit: pending
Evidence: Sync Audit Report showed old stored Shopee winners as `Affiliate URL = Valid` with detail `Shopee affiliate parameters are present.`
Notes: Confirms stored source URL diagnostics backfill works when a non-refreshed source wins.
```
