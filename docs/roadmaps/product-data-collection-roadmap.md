# Product Data Collection Roadmap

Date: 2026-05-04

Scope: Candidate Bucket source discovery, product specification collection, normalization, preview, and WooCommerce draft creation for unmatched marketplace products.

This roadmap is about resolving products that enter through the Candidate Bucket. The legacy GSMArena scraper migration is tracked separately in `docs/roadmaps/phone-database-enrichment-roadmap.md` because its purpose is WooCommerce phone database enrichment, not marketplace candidate resolution.

## Guiding Principles

- Source discovery must be separate from scraping.
- Scraping must be separate from WooCommerce draft creation.
- WooCommerce draft creation must require explicit user approval.
- Marketplace pages are commercial evidence only: price, stock, affiliate URL, marketplace product ID, and seller title reference.
- Product specifications should come from official or trusted non-marketplace sources.
- AI may assist with ranking, summarizing, or formatting approved source data, but it must not invent missing specifications or treat seller descriptions as verified truth.

## Target Workflow

```text
Candidate Bucket
  -> classify product type
  -> discover trusted source candidates
  -> user selects/approves source URL
  -> preview-only extraction
  -> normalize extracted fields
  -> preview WooCommerce draft payload
  -> user approves draft creation
  -> candidate links to WooCommerce draft/product
  -> future price imports map by marketplace product ID
```

## Source Roles

```text
Commercial Source
  -> Shopee/Lazada sheet source
  -> price, stock, affiliate URL, marketplace product ID

Primary Spec Source
  -> official brand product/spec page where available
  -> trusted retailer fallback when official source is unavailable

Image Source
  -> official source preferred
  -> trusted retailer fallback
  -> marketplace image only with manual approval

Support/News Source
  -> official support/newsroom page
  -> useful for launch context or feature confirmation
```

## Source Trust Registry

The app should eventually maintain a registry that defines which domains are trusted for each brand and product type.

Suggested fields:

```text
brand
allowed_domains
source_type
trust_level
supported_product_types
blocked_for_specs
notes
```

Suggested trust levels:

```text
official_product_page
official_support_or_newsroom
authorized_retailer
manual_reviewed
blocked_for_specs
```

Marketplace domains such as Shopee and Lazada should be marked as `blocked_for_specs` but kept as commercial sources.

## Example Trusted Sources

Samsung:

```text
Official product/spec source:
https://www.samsung.com/ph/

Official newsroom fallback:
https://news.samsung.com/ph/

Good for:
Galaxy Buds, Galaxy Watch, tablets, chargers, accessories
```

Apple:

```text
Official specs source:
https://www.apple.com/ph/

Authorized retailer fallback:
https://powermaccenter.com/

Good for:
AirPods, Apple Watch, chargers, cables, accessories
```

Xiaomi:

```text
Official product/spec source:
https://www.mi.com/ph/

Good for:
Xiaomi Buds, watches, bands, chargers, power banks
```

OPPO:

```text
Official accessory/spec source:
https://www.oppo.com/ph/

Good for:
OPPO Enco earbuds, watches, bands, accessories
```

Huawei:

```text
Official specs source:
https://consumer.huawei.com/ph/

Good for:
FreeBuds, watches, bands, tablets, accessories
```

Sony:

```text
Official specs source:
https://www.sony.com.ph/

Good for:
headphones, earbuds, speakers, audio accessories
```

realme:

```text
Official product source:
https://www.realme.com/ph/

Good for:
realme Buds, watches, accessories
```

Trusted retailer fallbacks:

```text
Power Mac Center:
https://powermaccenter.com/

Abenson:
https://home.abenson.com/

Anson's:
https://ansons.ph/
```

## Candidate Phone And Tablet Roadmap

Phones and tablets that enter through Candidate Bucket can use GSMArena as a preferred structured specification source, but the URL must be reviewed before extraction. This candidate-driven path is separate from the broader Phone Database Enrichment Pipeline.

### Phone Workflow

```text
Candidate phone/tablet
  -> type = phone or tablet
  -> Find GSMArena Source
  -> show candidate GSMArena URLs with confidence and reason
  -> user selects correct URL
  -> save spec_source_url
  -> Preview Scrape
  -> show structured specs and image
  -> user approves Woo draft payload
  -> create WooCommerce draft
  -> save linked_wc_id on candidate
```

### Phone Data Model

```text
canonical_name
brand
model
product_type
spec_source_url
source_confidence
source_status
image_url
network
launch_status
dimensions
weight
build
sim
display_type
display_size
display_resolution
os
chipset
cpu
gpu
memory
main_camera
selfie_camera
battery
charging
colors
models
source_scraped_at
```

### Phone-Specific Gaps

- Add GSMArena source discovery for candidate names.
- Add source approval states: `needs_source`, `source_candidates_found`, `source_selected`, `ready_for_scraper`.
- Add preview-only extraction that does not write to WooCommerce.
- Keep WooCommerce draft creation separate from scraping.
- Change candidate-driven creation to WooCommerce `draft`, not `publish`.
- Validate existing WooCommerce product/slug before creating a draft.
- Handle close model names such as `Pro`, `Ultra`, `FE`, `Plus`, and `5G`.
- Define policy for rumored, upcoming, cancelled, and discontinued products.
- Support tablet category routing separately from phone category routing.
- Validate WooCommerce attribute IDs before writing attributes.
- Show image preview and require image approval before upload.
- Store raw GSMArena specs, normalized specs, and Woo draft payload separately.
- Show missing fields during preview instead of failing silently.
- Record an audit trail for source discovery, source selection, preview scrape, draft creation, and link actions.

### Expected Phone Behavior

```text
Candidate:
Samsung Galaxy S26 Ultra

Action:
Find GSMArena Source

Results:
1. Samsung Galaxy S26 Ultra - confidence 96 - exact model match
2. Samsung Galaxy S26+ - confidence 74 - related model
3. Samsung Galaxy S26 - confidence 70 - base model

User selects:
Samsung Galaxy S26 Ultra

Candidate update:
spec_source_url = selected GSMArena URL
source_status = source_selected
status = ready_for_scraper

No scraping or WooCommerce write happens during discovery.
```

## Non-Phone Roadmap

Non-phone products should use product-type templates and trusted source roles instead of a universal scraper.

### Non-Phone Workflow

```text
Candidate non-phone product
  -> type = earbuds, watch, charger, power_bank, cable, case, accessory, or unknown
  -> Find Trusted Sources or Paste Source URL
  -> user selects primary spec source
  -> preview extracted/manual fields
  -> show draft readiness
  -> user approves WooCommerce draft
  -> save linked_wc_id on candidate
```

### Common Non-Phone Fields

```text
canonical_name
brand
product_type
commercial_source
source_product_id
affiliate_url
regular_price
sale_price
stock_status
primary_spec_source_url
image_source_url
short_description
key_features
compatibility
color_or_variant
notes
```

### Category-Specific Fields

Earbuds:

```text
bluetooth_version
battery_life
charging_case
noise_cancellation
water_resistance
codec
latency
driver
microphones
```

Watch:

```text
display
battery_life
sensors
gps
water_resistance
compatibility
case_size
connectivity
```

Charger:

```text
wattage
ports
charging_protocol
cable_included
compatibility
input_output_rating
```

Power bank:

```text
capacity
output_wattage
ports
fast_charging_protocol
battery_type
input_rating
```

Case/accessory:

```text
compatible_models
material
protection_level
color
dimensions
```

### Non-Phone-Specific Gaps

- Add source roles to candidate records instead of one generic source URL.
- Add manual trusted source URL fields before automated source search.
- Add source trust registry and blocked-spec domains.
- Add type-specific field templates.
- Add draft readiness scoring.
- Add missing-field policy for incomplete trusted sources.
- Add field-level source tracking for extracted values.
- Add duplicate candidate detection and merge workflow.
- Add image source and image approval policy.
- Add audit trail for source selection, field extraction, manual edits, and draft creation.
- Add per-brand/per-source extractors only after source selection and templates are stable.

### Expected Non-Phone Behavior

```text
Candidate:
Samsung Galaxy Buds4

Commercial source:
Lazada
Affiliate: valid
Price: from staged row

User sets:
Type = earbuds

Action:
Find Trusted Sources or Paste Source URL

Result:
Samsung official page/newsroom and trusted retailer pages are suggested.
Shopee/Lazada are shown only as commercial sources.

User selects:
Primary spec source = Samsung official page

No scraping or WooCommerce write happens during discovery.
```

## Candidate Data Additions

Suggested candidate fields for this roadmap:

```text
commercial_source_url
primary_spec_source_url
image_source_url
support_source_url
retailer_backup_url
source_candidates
source_status
source_trust_level
source_notes
scrape_status
scrape_preview
normalized_specs
woo_draft_preview
draft_readiness
field_sources
```

## Validation Plan

```text
QA-PDC-001: Phone candidate can run GSMArena source discovery without scraping specs.
QA-PDC-002: User can select and save a GSMArena source URL.
QA-PDC-003: Source discovery does not create or update WooCommerce products.
QA-PDC-004: Preview scrape only runs after source URL selection.
QA-PDC-005: WooCommerce draft creation requires explicit preview approval.
QA-PDC-006: Non-phone candidate can store commercial source separately from spec source.
QA-PDC-007: Shopee/Lazada are blocked as spec sources but retained as commercial sources.
QA-PDC-008: Non-phone candidate can save a manually reviewed trusted spec URL.
QA-PDC-009: Draft readiness shows missing fields before draft creation.
QA-PDC-010: Candidate stores linked WooCommerce ID after draft creation.
```

## Recommended Implementation Order

1. Add candidate source role fields and manual trusted source URL entry.
2. Add source trust registry as configuration/data, not hardcoded UI logic.
3. Add GSMArena discovery for phone/tablet candidates.
4. Add source selection and `ready_for_scraper` status transition.
5. Add preview-only phone extraction.
6. Add normalized phone spec schema and Woo draft preview.
7. Add WooCommerce draft creation gate.
8. Add non-phone type templates and draft readiness.
9. Add trusted source discovery for non-phone products.
10. Add duplicate candidate detection and merge workflow.

## Related Roadmaps

```text
Phone Database Enrichment Pipeline:
docs/roadmaps/phone-database-enrichment-roadmap.md

Purpose:
Migrate the existing GSMArena scraper for latest/upcoming/manual phone enrichment against WooCommerce.
```
