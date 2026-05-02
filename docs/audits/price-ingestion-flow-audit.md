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

## Confirmed Findings

- `backend/main.py` generic `/api/import/google-sheet` calls `import_from_google_sheet_task.delay(job_id, sheet_url)` without `source`, but `backend/data_tasks.py` requires `source`. The source-specific Tools buttons avoid this, but the generic route will fail if used.
- `backend/data_tasks.py` logs importer failures but does not set `job:{job_id}` to `failed`, so the UI can remain stuck on `starting` or `processing`.
- `backend/data_tasks.py` computes audit `price_before` after overwriting current price fields, so the sync report can label a real price change as `Synced`.
- `frontend/src/components/PriceUpdateReviewView.jsx` posts unlink requests to `/api/unlink_product`, while `backend/main.py` defines `/api/unlink-product`.

## Enhancement Gaps

- Marketplace product ID should be the trusted auto-match key. Name fallback should be review-visible or stricter.
- Shopee matching should consider `(shop_id, product_id)` where possible.
- Duplicate marketplace IDs in sheets should be detected and surfaced.
- Skipped rows should produce diagnostics, such as no URL, no parsed product ID, no price, unsupported source, or duplicate ID.
- Audit report should include source, match method, marketplace product ID, shop ID, winning source, price before, and price after.
- Manual link currently mutates `slug` in the frontend; row identity would be safer with a stable row key.
- Out-of-stock behavior should be confirmed as a business rule.
- Generic importer route should either infer/select source or be removed from active workflows.

## Implementation Tracker

| Status | Item | Notes |
| --- | --- | --- |
| Pending | Fix audit `price_before` capture | Capture old price before updating `local_prod_to_update`. |
| Pending | Set importer job to failed on exception | Update Redis `job:{job_id}` in importer `except` block. |
| Pending | Fix unlink route mismatch | Align frontend route with backend or add compatibility alias. |
| Pending | Fix or disable generic Google Sheet importer | Add `source` handling or remove unused path. |
| Pending | Add source/match fields to staged rows | Track `matched_by`: marketplace_id, exact_name, manual_link, unmatched. |
| Pending | Add duplicate ID detection | Detect same source/product ID across In Stock and Sold Out. |
| Pending | Add skipped-row diagnostics | Store summary in job status or a related Redis key. |
| Pending | Strengthen Shopee keying | Prefer product ID plus shop ID if local data supports it. |
| Pending | Improve frontend row identity | Use stable import row ID instead of mutable slug for updates. |
| Pending | Review out-of-stock sync policy | Confirm whether clearing price and URL is desired. |

## Notes For Next Review

- Active Google Sheet flow is in `backend/data_tasks.py`, not mainly `backend/tasks.py`.
- `backend/tasks.py` still contains older Bright Data/MCP and enrichment paths that can interact with WooCommerce, but they are not the current Tools Shopee/Lazada sheet importer path.
- The command `docker-compose exec backend python data_tasks.py <woo_product_id>` inspects a live WooCommerce product by WooCommerce ID, not marketplace ID.

## Append-Only Findings Log

Use this section for new findings as review continues.

```text
2026-05-02
- Initial audit created for Shopee/Lazada Google Sheet to WooCommerce price ingestion flow.
```
