# Development Change SOP

Use this SOP before changing code, especially in flows that touch Google Sheets parsing, WooCommerce updates, or user-facing review screens.

## 0. Interaction Mode Guardrails

Treat the user's wording as the workflow mode.

### No-Edit Discussion Mode

When the user asks to review, assess, analyze, audit, discuss, give a take, identify gaps, or propose options:

- Inspect files, logs, screenshots, and current behavior only.
- Do not edit code or docs.
- Present findings, risks, and recommendations first.
- Include expected result/output/behavior for every proposed change.
- Wait for explicit approval before implementation.

Approval words include `proceed`, `approved`, `implement`, `fix it`, `make the change`, or similarly clear instruction.

### Live Flow Guardrail

For live or working flows involving Google Sheets import, parser normalization, WooCommerce sync, price logic, Redis job state, audit reports, or external APIs:

- Default to audit-first.
- Do not alter parser/sync behavior during discussion mode.
- Do not change matching hierarchy without explicit approval.
- Create or confirm a checkpoint branch/commit before risky changes.
- Include a validation plan and rollback/checkpoint note before implementation.

### Proposal Requirement

Before implementation, every proposal must include expected result/output/behavior.

For UI changes:

- What the user will see.
- Changed labels, columns, cards, buttons, or states.
- Mobile/desktop behavior when relevant.

For backend/API changes:

- Expected request/response or payload shape.
- Expected job status behavior.
- Expected stored fields, Redis keys, or audit log fields.

For parser/normalization changes:

- Sample input -> expected output cases.
- Edge cases that should not change.

For sync/WooCommerce changes:

- Expected before/after price behavior.
- Expected WooCommerce fields/meta_data.
- Expected QA evidence and rollback/checkpoint.

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

Expected result/output/behavior:
- What should the user see or receive?
- What fields/values should be stored?
- What sample inputs should produce what sample outputs?
- What should remain unchanged?
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

Treat validation as levels, not one generic "pass":

- **Code validated** means syntax/build checks passed.
- **UI validated** means the relevant screen was opened and inspected at target viewport sizes.
- **Workflow validated** means the actual user flow was executed against the local app or Docker stack.
- **Live sync validated** means the workflow touched the external service it claims to update, such as WooCommerce, and the result was verified.

Do not mark a high-risk task as fully done if only code validation passed. Record the highest validation level reached in the audit tracker or final notes.

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

For Shopee/Lazada price ingestion changes, validate the backend workflow in stages:

```text
1. Run importer from Tools, or source-specific endpoint.
2. Confirm job status becomes complete or failed, never stuck.
3. Open Review Staged Updates.
4. Confirm each row has source, marketplace ID, stock status, matched_by, current price, and new prices.
5. Approve a safe small set or test product.
6. Sync to WooCommerce.
7. Confirm Sync Report shows correct price_before and price_after.
8. Inspect WooCommerce product by WooCommerce product ID.
```

Suggested inspector command:

```bash
docker-compose exec backend python data_tasks.py WOO_PRODUCT_ID
```

Important: this command expects the WooCommerce product ID, not the Shopee or Lazada marketplace product ID.

Minimum evidence for "live sync validated":

- Job status finished as `complete`.
- Audit log/report has the expected product and price delta.
- WooCommerce product `price`, `regular_price`, `sale_price`, `external_url`, and source `meta_data` match the expected winning source.
- No unintended product was changed.

## 7. Update Audit/Tracker

If the change relates to an audit item, update the relevant file:

- `docs/audits/price-ingestion-flow-audit.md`
- `docs/audits/frontend-price-workflow-ui-audit.md`
- `docs/qa/price-ingestion-qa-test-cases.md`

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
