# Price Ingestion Flow Audit

Date: 2026-05-02

Scope: Shopee and Lazada price parsing from Google Sheets, staging in the Tools UI, approval/review flow, and WooCommerce sync.

## Current Flow

```text
Tools UI
  -> POST /api/import/run-shopee-importer
  -> POST /api/import/run-lazada-importer
  -> backend/main.py creates import_* Redis job
  -> backend/data_tasks.py import_from_google_sheet_task(job_id, sheet_url, source)
  -> Google Sheet tabs: In Stock, Sold Out
  -> sheet_parser.py parses name, prices, affiliate URL, product/shop IDs
  -> staged rows saved to Redis staging_area:{job_id}
  -> JobStatusView shows Review Staged Updates
  -> PriceUpdateReviewView loads staged rows + /api/products
  -> user approves, ignores, or manually links rows
  -> POST /api/import/process-staged-data
  -> backend/data_tasks.py update_multi_source_products_task
  -> update product_database.json linked_sources[source]
  -> choose lowest in-stock source
  -> WooCommerce products/batch update by WooCommerce product ID
  -> save product_database.json and audit_log:{job_id}
  -> SyncReportView displays audit log
```

## Mapping Model

The parsed Shopee/Lazada marketplace product ID is not the WooCommerce product ID.

```text
Google Sheet URL
  -> parse marketplace product_id + shop_id
  -> match against product_database.json shopee_id/lazada_id
  -> retrieve local/WooCommerce product id
  -> update WooCommerce by WooCommerce product id
```

Primary intended mapping:

```text
Shopee sheet product_id -> product_database.shopee_id -> product_database.id -> WooCommerce product id
Lazada sheet product_id -> product_database.lazada_id -> product_database.id -> WooCommerce product id
```

Fallback mapping currently exists by exact cleaned product name. Fuzzy matching is used as a suggestion for review, not an automatic approval.

Do not change the matching hierarchy without explicit approval:

1. Source-specific marketplace product ID from the Google Sheet hyperlink.
2. Exact cleaned product name.
3. Fuzzy nearest match suggestion for manual review only.

## Confirmed Findings

- Fixed 2026-05-02: `backend/main.py` generic `/api/import/google-sheet` now requires `source` and passes it to `import_from_google_sheet_task`.
- Fixed 2026-05-02: `backend/data_tasks.py` importer failures now set `job:{job_id}` to `failed`, so the UI does not remain stuck on `starting` or `processing`.
- Fixed 2026-05-02: `backend/data_tasks.py` captures `price_before` before overwriting current price fields, so the sync report can correctly label price changes.
- Fixed 2026-05-02: `frontend/src/components/PriceUpdateReviewView.jsx` now posts reset/unlink requests to `/api/unlink-product` with the matched WooCommerce product ID. The backend also keeps a compatibility alias for `/api/unlink_product`.

## Enhancement Gaps

- Marketplace product ID should be the trusted auto-match key. Name fallback should be review-visible or stricter.
- Shopee matching should consider `(shop_id, product_id)` where possible.
- Duplicate marketplace IDs in sheets should be detected and surfaced.
- Skipped rows should produce diagnostics, such as no URL, no parsed product ID, no price, unsupported source, or duplicate ID.
- Audit report should include source, match method, marketplace product ID, shop ID, winning source, price before, and price after.
- Manual link currently mutates `slug` in the frontend; row identity would be safer with a stable row key.
- Out-of-stock behavior should be confirmed as a business rule.
- Generic importer route should either infer/select source or be removed from active workflows.
- Review header should identify the staged source, such as Shopee or Lazada, so users know which importer produced the rows.
- Legacy/current staged rows may be missing `matched_by`; review UI needs a fallback instead of showing matched rows as `Unmatched`.

## Implementation Tracker

Status meanings:

- `Code Validated`: implementation is committed and compile/build checks passed.
- `Workflow Validated`: local UI/backend workflow was executed successfully.
- `Live Sync Validated`: WooCommerce was updated and inspected successfully.

| Status | Item | Notes |
| --- | --- | --- |
| Code Validated | Fix audit `price_before` capture | Captures old price before updating `local_prod_to_update`; comparison is numeric-tolerant. Needs live sync report verification. |
| Code Validated | Set importer job to failed on exception | Updates Redis `job:{job_id}` in importer `except` block. Needs importer failure test. |
| Code Validated | Fix unlink route mismatch | Frontend uses `/api/unlink-product`; backend accepts hyphen and underscore routes. Needs reset action test against a safe product. |
| Code Validated | Fix or disable generic Google Sheet importer | Generic route validates `source` as `shopee` or `lazada`. Needs endpoint/manual request test if generic path remains in use. |
| Code Validated | Add source/match fields to staged rows | Tracks `matched_by`: marketplace_id, exact_name, manual_link, unmatched; review UI displays it. Needs staged review check with real Shopee/Lazada rows. |
| Pending | Add duplicate ID detection | Detect same source/product ID across In Stock and Sold Out. |
| Pending | Add skipped-row diagnostics | Store summary in job status or a related Redis key. |
| Pending | Strengthen Shopee keying | Prefer product ID plus shop ID if local data supports it. |
| Pending | Improve frontend row identity | Use stable import row ID instead of mutable slug for updates. |
| Pending | Review out-of-stock sync policy | Confirm whether clearing price and URL is desired. |

## Notes For Next Review

- Active Google Sheet flow is in `backend/data_tasks.py`, not mainly `backend/tasks.py`.
- `backend/tasks.py` still contains older Bright Data/MCP and enrichment paths that can interact with WooCommerce, but they are not the current Tools Shopee/Lazada sheet importer path.
- The command `docker-compose exec backend python data_tasks.py <woo_product_id>` inspects a live WooCommerce product by WooCommerce ID, not marketplace ID.
- Real validation passes are tracked in `docs/qa/price-ingestion-qa-test-cases.md` using QA reference IDs such as `QA-PI-001`.

## Append-Only Findings Log

Use this section for new findings as review continues.

```text
2026-05-02
- Initial audit created for Shopee/Lazada Google Sheet to WooCommerce price ingestion flow.
- QA-PI-004 finding: Lazada review showed `MATCHED` rows with `Matched By = Unmatched`. Added frontend inference for existing/current staged rows. Backend matching remains on the original hierarchy: top-level source ID, exact cleaned name, then fuzzy suggestion only.
```
