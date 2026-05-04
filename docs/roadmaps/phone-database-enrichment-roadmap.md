# Phone Database Enrichment Roadmap

Date: 2026-05-04

Scope: Migration of the existing GSMArena-based phone scraper into ContentPipeline as a separate WooCommerce phone database enrichment pipeline.

This roadmap is intentionally separate from the Candidate Bucket workflow. Candidate Bucket starts from unmatched Shopee/Lazada marketplace products. Phone Database Enrichment starts from GSMArena/latest/upcoming/manual phone sources and enriches the WooCommerce phone catalog.

## Purpose

```text
GSMArena source pages
  -> collect latest/upcoming/manual phone URLs
  -> scrape phone specs
  -> compare against WooCommerce
  -> create/update safe WooCommerce drafts/products
  -> improve the Woo phone database
```

The old scraper's main purpose is not candidate resolution. It is database enrichment: finding new phones, classifying upcoming/rumored phones, refreshing existing phone specs, and improving WooCommerce product metadata.

## Existing Old-Code Strengths

Preserve these concepts from the old scraper:

```text
manual URL mode
latest GSMArena device mode
upcoming/rumored mode from Woo cache
GSMArena selectors and predefined page elements
source_url as product identity evidence
Woo product cache for comparison
cache healing for products missing source_url
skip ambiguous same-name products
release-year guard for old phones
camera and memory parsing helpers
category and attribute mapping concepts
image conversion/upload logic
draft creation behavior for new products
```

## Separation From Candidate Bucket

```text
Candidate Bucket Lane
  Input: unmatched Shopee/Lazada staged products
  Goal: link/create product candidates
  Commercial source: marketplace price/affiliate/product ID

Phone Enrichment Lane
  Input: GSMArena latest/upcoming/manual URLs
  Goal: enrich WooCommerce phone database
  Spec source: GSMArena structured phone pages
```

Possible future cross-connect:

```text
Phone enrichment creates or refreshes Woo products
  -> product database refresh
  -> Candidate Bucket can link marketplace candidates to those Woo products
```

The bridge should be added later. It should not drive the first migration.

## Target Enrichment Workflow

```text
Select enrichment mode
  -> latest devices, upcoming/rumored, or manual GSMArena URLs
  -> collect source URL queue
  -> preview enrichment run
  -> scrape preview
  -> normalize phone specs
  -> compare against WooCommerce
  -> generate decision report
  -> user approves selected actions
  -> execute create/update actions
  -> save audit report
```

## Woo Compare Logic To Preserve

Current old-code decision model:

```text
exact name + source_url exists
  -> safe update

exact name exists with missing source_url
  -> attach/heal source_url and update if only one match exists

multiple name-only matches with missing source_url
  -> skip / manual review

no match + valid recent or rumored release
  -> create new draft

old/invalid release
  -> skip

source_url mismatch
  -> warn, do not overwrite silently
```

This should become an explicit compare step:

```text
scraped_phone_preview
  -> compare_against_woo()
  -> enrichment_decision
```

Suggested decisions:

```text
update_existing
attach_missing_source_url
create_new_draft
skip_ambiguous
skip_old_release
skip_source_mismatch
needs_manual_review
```

## Decision Report

Before WooCommerce writes, the app should show a decision report.

Example:

```text
Samsung Galaxy S26 Ultra
Decision: Create new draft
Reason: No Woo product found by exact name/source_url
Warnings: None

vivo X300
Decision: Update existing
Reason: Exact name + source_url match
Changes: Battery, camera, display attributes

Samsung Galaxy S26
Decision: Needs review
Reason: Multiple Woo products share same name and no source_url
```

## Technical Requirements

Rate limiting:

```text
GSMArena/source requests:
  low concurrency
  request delay
  retry backoff
  source URL cache

WooCommerce:
  compare before write
  batch when safe
  live fallback for uncertain matches
  one write decision per product/action

Images:
  preview before upload
  avoid duplicate uploads
  preserve existing approved images unless replace is approved
```

Idempotency:

```text
same run_id + source_url should not duplicate scrape previews
same normalized name + source_url should not create duplicate Woo products
create action must check linked/existing slug before POST
timeout after create must re-check Woo before retry
```

Error handling:

```text
one failed URL must not fail the whole enrichment run
errors must be stored per source URL/product
retryable and non-retryable errors should be labeled
ambiguous matches should go to review instead of being lost in logs
```

Observability:

```text
run_id
source_url
mode
decision
duration_ms
attempt_count
error_type
skipped_reason
woo_product_id
fields_changed
missing_fields
```

## Data Model Concepts

Store raw and normalized data separately:

```text
raw_gsmarena_specs
normalized_phone_specs
woo_compare_result
woo_draft_or_update_preview
execution_result
audit_log
```

Suggested enrichment run status:

```text
queued
collecting_sources
preview_ready
scraping
compare_ready
awaiting_approval
executing
complete
failed
```

Suggested item status:

```text
queued
scraped
compare_ready
approved
executed
skipped
needs_review
failed
```

## Migration Phases

E1: Source Queue Preview

```text
Migrate latest/manual/upcoming source collection into a preview-only run.
Expected output: list of GSMArena URLs and estimated action mode, no scraping.
```

E2: Preview-Only Scrape

```text
Selected source URLs are scraped into raw/normalized phone specs.
Expected output: spec preview, image preview, missing fields, no Woo write.
```

E3: Woo Compare Engine

```text
Compare normalized specs against Woo cache/live fallback.
Expected output: update/create/skip/review decisions with reason.
```

E4: Approval Gate

```text
User approves selected decisions.
Expected output: approved action list.
```

E5: Execution Engine

```text
Create drafts or update existing products idempotently.
Expected output: execution audit with Woo IDs, failures, and skipped reasons.
```

E6: Reporting And QA

```text
Persist run report, item decisions, duration, errors, and validation references.
Expected output: repeatable audit trail for enrichment runs.
```

## Enhancement Gaps

- Add enrichment run preview before scraping.
- Add explicit decision report before Woo writes.
- Add diff engine for attributes, descriptions, image, SEO, and source_url.
- Add approval gate for selected actions.
- Add idempotency keys for source_url, normalized model name, Woo slug, and Woo ID.
- Add stale Woo cache warning and live lookup fallback.
- Add duplicate prevention before create.
- Add source URL conflict policy.
- Validate Woo attribute IDs against live Woo attributes.
- Define rumored/upcoming/cancelled/discontinued product policy.
- Add image approval and duplicate image avoidance.
- Add manual review queue for ambiguous products.
- Add structured observability and run-level metrics.
- Add parser tests with saved GSMArena HTML fixtures.

## Validation Plan

```text
QA-PDE-001: Manual URL mode can produce a source queue preview without scraping.
QA-PDE-002: Latest mode can produce a source queue preview with a limit.
QA-PDE-003: Upcoming mode can identify cached upcoming/rumored products with source_url.
QA-PDE-004: Preview scrape extracts normalized specs without Woo writes.
QA-PDE-005: Exact name + source_url match produces update_existing decision.
QA-PDE-006: Exact name with missing source_url produces attach_missing_source_url when unique.
QA-PDE-007: Multiple name-only matches produce needs_manual_review.
QA-PDE-008: New valid/recent phone produces create_new_draft decision.
QA-PDE-009: Old release below policy threshold is skipped.
QA-PDE-010: Source URL mismatch warns and does not overwrite silently.
QA-PDE-011: Approved create action is idempotent across retries.
QA-PDE-012: Failed source URL records item-level error and does not fail the whole run.
```

## Recommended First Slice

Start with E1 only:

```text
Create Phone Enrichment Preview Run
  -> choose mode: manual/latest/upcoming
  -> collect source URLs
  -> show source queue
  -> no scraping
  -> no WooCommerce writes
```

Expected first usable behavior:

```text
Run: GSMArena Latest Preview
Limit: 10

Output:
1. Samsung Galaxy S26 Ultra - GSMArena URL
2. vivo X300 - GSMArena URL
3. Xiaomi 17 Pro - GSMArena URL

Status:
preview_ready

Next action:
Approve selected URLs for preview scrape
```

