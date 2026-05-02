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
- Fixed 2026-05-02: staged rows and sync audit entries now carry affiliate diagnostics, and WooCommerce meta receives source-specific affiliate status/detail fields.
- Fixed 2026-05-02: `backend/main.py` now preserves `affiliate_diagnostics` in staged data responses/payloads and provides live WooCommerce product search as a manual-link fallback when `product_database.json` is stale.
- Fixed 2026-05-02: sync now derives affiliate diagnostics from existing stored source URLs when older linked source data does not yet have diagnostics.
- Added 2026-05-02: Phase 2A candidate bucket foundation lets unmatched staged rows be saved for later review without syncing them to WooCommerce.

## Enhancement Gaps

- Marketplace product ID should be the trusted auto-match key. Name fallback should be review-visible or stricter.
- Shopee matching should consider `(shop_id, product_id)` where possible.
- Duplicate marketplace IDs in sheets should be detected and surfaced.
- Skipped rows should produce diagnostics, such as no URL, no parsed product ID, no price, unsupported source, or duplicate ID.
- Audit report should include source, match method, marketplace product ID, shop ID, winning source, price before, and price after.
- Sync Report should make price changes immediately visible with `before -> after` and delta, not only status/details text.
- Manual link currently mutates `slug` in the frontend; row identity would be safer with a stable row key.
- Out-of-stock behavior should be confirmed as a business rule.
- Generic importer route should either infer/select source or be removed from active workflows.
- Review header should identify the staged source, such as Shopee or Lazada, so users know which importer produced the rows.
- Legacy/current staged rows may be missing `matched_by`; review UI needs a fallback instead of showing matched rows as `Unmatched`.
- Affiliate URL generation should expose validation diagnostics so reviewers can confirm the generated Shopee/Lazada affiliate URL is complete before sync.
- Unmatched staged products need a clean path into a candidate bucket instead of only `Ignore` or manual link to an existing WooCommerce product.
- Full product database refresh is slow because it fetches each WooCommerce product individually and sleeps per product; manual-link workflows should not depend on running a full refresh.

## Affiliate URL Generation Assessment

Current behavior:

```text
Google Sheet hyperlink
  -> sheet_parser.py parse_ecommerce_url()
  -> sheet_parser.py convert_to_affiliate_link()
  -> staged row affiliate_link
  -> update_multi_source_products_task()
  -> WooCommerce external_url and source URL meta
```

Shopee affiliate links are generated by taking the original product URL without old query parameters and adding the configured affiliate campaign parameters. Lazada affiliate links are generated from the clean PDP URL plus `LAZADA_AFFILIATE_PID`; if that environment value is missing, the parser currently falls back to the clean non-affiliate Lazada URL.

Reliability gaps:

- Lazada affiliate generation depends on `LAZADA_AFFILIATE_PID`; missing configuration silently produces a non-affiliate URL.
- Generated click IDs are intentionally variable, which is useful for tracking but makes exact URL comparison harder during QA.
- There is no staged-row warning for `affiliate_link_missing`, `affiliate_config_missing`, `source_url_unparseable`, or `marketplace_product_id_missing`.
- The review UI does not currently show whether a staged row has a valid affiliate URL before the user approves sync.
- The sync report confirms the winning source, but it does not show affiliate URL validation status.

Proposed expected behavior:

```text
Review Price Updates
  -> each row shows source product ID, shop ID, and affiliate URL status
  -> rows with missing affiliate config are still reviewable but visibly warned
  -> sync report records whether WooCommerce received an affiliate URL or a clean fallback URL
```

## Candidate Bucket Workflow Proposal

Problem:

Unmatched staged products may be real new products that are not yet in the live WooCommerce database. Today, the reviewer can ignore the row or manually link it to an existing product. There is no structured path to keep the item for research, scraping, and future WooCommerce creation.

Recommended flow:

```text
Unmatched staged row
  -> Add to Product Candidate Bucket
  -> reviewer tags category/type and canonical product name
  -> optional research step validates source/spec URL
  -> send phone items to existing phone scraper when a spec source is available
  -> create WooCommerce draft/product
  -> refresh product database
  -> re-run importer or link candidate to new WooCommerce product ID
  -> price sync proceeds only after WooCommerce product exists and user approves
```

Candidate bucket data should keep both the marketplace evidence and the user's review decisions:

```text
candidate_id
source
source_product_id
shop_id
raw_name
normalized_name
canonical_name
original_url
affiliate_url
new_sale_price
new_regular_price
stock_status
nearest_match
import_job_id
created_at
status
tags
notes
spec_source_url
linked_wc_id
```

Suggested statuses:

```text
candidate
researching
ready_for_scraper
draft_created
created_in_woo
linked_existing
rejected
```

Suggested Review UI actions:

- `Manual Link`: link to an existing WooCommerce product.
- `Add to Bucket`: save the staged row as a new product candidate without syncing price to WooCommerce.
- `Ignore`: skip the row for this import.

Suggested Candidate Bucket actions:

- `Research`: add or verify the canonical product name and spec source.
- `Send to Phone Scraper`: hand off phone candidates to the existing phone scraper flow when a supported spec URL is available.
- `Create Manual Draft`: create a WooCommerce draft for non-phone or incomplete candidates.
- `Link Existing Product`: attach the candidate to a WooCommerce product that was created outside the importer.
- `Reject`: close the candidate when it should not become a WooCommerce product.

Expected behavior after implementation:

```text
Unmatched staged product does not disappear after import review
Candidate keeps source product ID, affiliate URL, prices, and raw source name
No WooCommerce price update happens while the item is only a candidate
Once a WooCommerce product exists, the candidate can be linked and future imports match by marketplace product ID
```

## Product Name Normalization Notes

Product name normalization is useful for review readability and exact-name fallback, but it should not override the primary source-product-ID mapping.

Current priority remains:

```text
marketplace product ID match
exact cleaned name match
fuzzy suggestion for manual review
```

Future normalization tuning:

- Remove marketplace noise such as `series`, `mobilephone`, `mobile phone`, `cellphone`, and promo labels.
- Keep meaningful model/network tokens such as `5G` when they are part of the standard WooCommerce product name.
- Use a canonical name reference list only as a review aid, not as a replacement for source product ID matching.
- For example, a future approved rule should prefer `vivo X300 5G`, not `vivo X300 series 5G`, when WooCommerce standard names do not include `series`.

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
| Live Sync Validated | Add affiliate URL validation diagnostics | Staging, review UI, sync report, local source data, and WooCommerce meta surface valid Shopee/Lazada affiliate status/detail. |
| Code Validated | Add live Woo search fallback for manual link | Manual-link search uses local `product_database.json` first and live WooCommerce search when local results are thin. Needs UI retest with a product missing from local cache. |
| Live Sync Validated | Backfill affiliate diagnostics for stored source URLs | Existing linked sources such as old Shopee data are labeled during sync without regenerating affiliate URLs. Real sync report showed old Shopee winners as valid. |
| Workflow Validated | Add candidate bucket for unmatched staged products | Unmatched Lazada row saved to `product_candidates.json` and displayed in Tools Candidate Bucket with affiliate status. |
| Workflow Validated | Add candidate management controls | Candidate Bucket supports editing canonical name, type tag, status, notes, and linked Woo ID without mutating WooCommerce. Save/persist workflow validated. |
| Pending | Add candidate-to-phone-scraper handoff | Use existing phone scraper for approved phone candidates when a supported spec source URL is available. |
| Pending | Add canonical product-name reference list | Use as a review aid for staged/candidate products while keeping marketplace product ID as the primary mapping key. |
| Pending | Optimize full product database refresh | Replace per-product fetch/sleep flow with paged field fetch, chunked saves, progress, and cancellation. |

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
- Added documentation-only audit for affiliate URL reliability, unmatched product candidate bucket, existing phone scraper handoff, and product-name normalization boundaries. No runtime code changes were made for this audit entry.
- QA-PI-010 code validation: Affiliate diagnostics are generated at staging, shown in Review Price Updates and Sync Audit Report, stored in local source data, and sent to WooCommerce meta as `_shopee_affiliate_status`, `_shopee_affiliate_detail`, `_lazada_affiliate_status`, and `_lazada_affiliate_detail`.
- QA follow-up: Real Lazada QA exposed two gaps: `StagedProduct` response filtering removed `affiliate_diagnostics`, and manual-link search could not find live Woo products missing from stale `product_database.json`. Added backend model field and live Woo search fallback.
- QA follow-up: Real sync report showed `Affiliate URL = Not Checked` when an older Shopee linked source won during a Lazada sync. Added stored URL diagnostics backfill so old winning source URLs are inspected instead of reported as unchecked.
- Live validation: WooCommerce meta confirmed `_shopee_affiliate_status = valid`, `_shopee_affiliate_detail = Shopee affiliate parameters are present.`, `_lazada_affiliate_status = valid`, and `_lazada_affiliate_detail = Lazada affiliate parameters are present.`
- Phase 2A implementation: Added Product Candidate Bucket storage and UI for unmatched staged products. Bucketed rows are intentionally excluded from WooCommerce sync.
- QA-PI-013 workflow validation: Candidate Bucket displayed `Samsung Galaxy Buds4` from Lazada with source product ID, price, valid affiliate status, nearest match, and updated timestamp.
- Added Candidate Bucket placeholder action `Scrape Later` for the future phone/spec scraper handoff. This is intentionally disabled and has no backend behavior yet.
- Phase 2B implementation: Added review-only candidate management fields for canonical name, type tag, status, notes, and linked Woo product. These updates are stored only in `product_candidates.json`.
- QA-PI-014 workflow validation: Candidate management saved `Samsung Galaxy Buds4` as status `researching`, type `earbuds`, with note `Test note` and updated timestamp.
```
