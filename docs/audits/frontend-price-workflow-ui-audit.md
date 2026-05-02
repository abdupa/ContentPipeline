# Frontend Price Workflow UI Audit

Date: 2026-05-02

Scope: Mobile responsiveness, readability, and UX polish for the price ingestion workflow:

- `ToolsView.jsx`
- `JobStatusView.jsx`
- `PriceUpdateReviewView.jsx`
- `SyncReportView.jsx`
- App shell/sidebar layout

## Executive Summary

The main UI risk is `PriceUpdateReviewView.jsx`. It uses a wide editable table with 10 columns, large padding, desktop header layout, and long numeric IDs inside narrow cells. On mobile or smaller laptop widths, values can be hidden, clipped, or require awkward horizontal scrolling. This makes price review risky because users need to clearly compare product identity, source IDs, stock status, current price, and incoming prices before syncing to WooCommerce.

The better direction is not only to shrink fonts. The review experience should become responsive by layout:

```text
Desktop/tablet wide:
  dense table with sticky/context columns and compact cells

Mobile/narrow:
  row cards with labeled fields, compact action controls, and visible IDs/prices
```

## Confirmed UI Findings

### 1. Price Review Header Is Desktop-Only

File: `frontend/src/components/PriceUpdateReviewView.jsx`

The header uses:

```text
flex justify-between items-center
text-3xl heading
multiple inline action buttons
```

On narrow screens this can compress the title and buttons. The action buttons can overflow or squeeze text.

Recommended fix:

- Use `flex-col sm:flex-row`.
- Use smaller mobile title sizes, such as `text-xl sm:text-2xl`.
- Stack buttons on mobile with full-width or compact layout.
- Make the primary sync action visually dominant.

### 2. Review Table Is Too Wide For Mobile

File: `frontend/src/components/PriceUpdateReviewView.jsx`

The table has 10 columns:

```text
#, Action, Product Name, Status, Stock Status, Sheet Product ID,
Sheet Shop ID, Current DB Price, Sheet Regular Price, Sheet Sale Price
```

It is inside `overflow-x-auto`, but the cell content is not optimized for scanability. Horizontal scrolling hides context, especially product name versus prices.

Recommended fix:

- Keep table for `lg` and above.
- Add a mobile card/list layout for `md` and below.
- In desktop table, reduce padding from `p-4` to `px-3 py-2`.
- Use `text-xs` or `text-sm` consistently in dense rows.
- Add `break-all` or copy-friendly display for long product/shop IDs.

### 3. Long IDs And Values Are Not Fully Readable

File: `frontend/src/components/PriceUpdateReviewView.jsx`

Long marketplace IDs are rendered in regular table cells:

```text
font-mono
```

But they do not use wrapping or tooltips. On narrow cells, characters can become hidden behind scroll boundaries or hard to verify.

Recommended fix:

- Use `break-all` for IDs in mobile cards.
- Use `title={value}` on desktop cells.
- Consider showing compact ID with copy button later.
- Label the ID by source: `Shopee ID` or `Lazada ID`, not only `Sheet Product ID`.

### 4. Editable Inputs Are Large And Ambiguous In Dense Rows

File: `frontend/src/components/PriceUpdateReviewView.jsx`

Product name and price fields use generic `p-2 border rounded-md`. In a dense table this makes rows tall while still not making values more readable.

Recommended fix:

- Use compact input classes for table mode: `px-2 py-1.5 text-sm`.
- Use labeled fields in mobile card mode.
- Align numeric values right for prices.
- Format price display with separators where possible.

### 5. Action Cell Takes Too Much Space

File: `frontend/src/components/PriceUpdateReviewView.jsx`

Matched rows show a checkbox plus unlink button. Unmatched rows show a search input plus Ignore button. In a table cell, this can become tall and visually heavy.

Recommended fix:

- Use compact segmented actions or icon buttons with labels.
- In mobile card mode, place actions at the top or bottom of each card.
- For matched rows, use `Approve` toggle plus secondary `Reset`.
- For unmatched rows, make manual-link search full-width in the card.

### 6. Manual Link Uses Mutable `slug` As Row Identifier

File: `frontend/src/components/PriceUpdateReviewView.jsx`

State updates use `slug` as the row key/identifier, and manual linking changes `slug` to the selected DB product slug. This is both a logic and UI stability risk because rows can collide or update incorrectly.

Recommended fix:

- Add a stable staged row ID from backend, or derive one on frontend:
  `source + product_id + shop_id + index`.
- Use that row key for UI state updates.

### 7. Tools Buttons Are Not Mobile-Friendly

File: `frontend/src/components/ToolsView.jsx`

Shopee and Lazada importer buttons sit in:

```text
flex justify-end space-x-4
```

On narrow screens they may squeeze or overflow.

Recommended fix:

- Use `flex-col sm:flex-row`.
- Make buttons `w-full sm:w-auto`.
- Use separate loading states for Shopee and Lazada, so both buttons do not show a spinner at the same time.

### 8. Job Status Completion Banner Can Overflow

File: `frontend/src/components/JobStatusView.jsx`

The green completion banner uses:

```text
flex items-center justify-between
text-lg
button inline
```

On mobile, message and action button can collide.

Recommended fix:

- Use `flex-col sm:flex-row`.
- Reduce message text size on mobile.
- Make the action button full-width on mobile.

### 9. Sync Report Table Has Similar Mobile Problems

File: `frontend/src/components/SyncReportView.jsx`

The audit report table is simpler than the review table, but long product names and detail strings can still overflow or become hard to read.

Recommended fix:

- Keep desktop table.
- Add mobile audit cards with labels:
  `Product`, `WC ID`, `Status`, `Details`, `Price Before`, `Price After` when available.
- Use wrapping for details, not only `font-mono`.

### 10. App Shell Is Not Responsive

Files:

- `frontend/src/App.jsx`
- `frontend/src/components/Sidebar.jsx`

The app shell always renders a `w-64` sidebar. On mobile this leaves too little room for content. Also, `main` has `p-4 sm-p-8`; `sm-p-8` appears to be a typo and should likely be `sm:p-8`.

Recommended fix:

- Convert sidebar to collapsible/off-canvas on small screens, or at least hide it behind a menu.
- Fix `sm-p-8` to `sm:p-8`.
- Ensure main content can use full width on mobile.

## Proposed Responsive Design Direction

### Price Review Desktop

Use a compact table:

```text
Header row:
  Product / Match
  Source
  IDs
  Stock
  Current
  Regular
  Sale
  Action
```

Improvements:

- Fewer columns by grouping IDs.
- Product column wider and sticky if needed.
- Compact inputs.
- Clear match badge: `ID match`, `Name match`, `Manual`, `Unmatched`.

### Price Review Mobile

Use cards instead of a table:

```text
[Status badge] [Stock badge]
Product name / linked target
Source: Shopee
Product ID: 40513867668
Shop ID: ...
Current DB Price: ...
Sheet Regular Price: [input]
Sheet Sale Price: [input]
[Approve] [Ignore] [Manual Link/Reset]
```

This makes all values visible and avoids horizontal table scrolling for the critical approval workflow.

## Implementation Tracker

| Status | Item | Notes |
| --- | --- | --- |
| Pending | Fix app shell mobile layout | Sidebar and `sm-p-8` typo. |
| Pending | Make Tools importer buttons responsive | Stack buttons on mobile; separate loading states. |
| Pending | Make JobStatus completion banner responsive | Stack message/action on mobile. |
| Pending | Redesign PriceReview mobile layout | Add card layout under `lg`; keep compact table for desktop. |
| Pending | Compact PriceReview desktop table | Reduce padding, group IDs/source, improve wrapping. |
| Pending | Add stable row key | Avoid using mutable `slug` for row state updates. |
| Pending | Improve value visibility | `break-all`, `title`, right-aligned price inputs. |
| Pending | Add source-aware labels | Show Shopee/Lazada ID instead of generic Sheet Product ID. |
| Pending | Make SyncReport mobile layout | Cards for narrow screens. |
| Pending | Browser screenshot verification | Verify mobile and desktop after implementation. |

## Verification Plan

After implementation:

```text
npm run build
manual/dev screenshot at:
  390x844 mobile
  768x1024 tablet
  1366x768 desktop

Critical checks:
  - no clipped IDs
  - prices readable/editable
  - buttons do not overflow
  - product names do not hide action controls
  - review flow still posts the same payload shape
```

## Append-Only UI Findings Log

```text
2026-05-02
- Initial UI audit created for Tools, Job Status, Price Review, Sync Report, and app shell responsiveness.
```
