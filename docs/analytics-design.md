# Superset reporting and analysis — demo scope

## Decisions

The user replaces Metabase with Superset because the current cards do not explain the business. Superset becomes the default consumer UI; the Warehouse/Airflow/dbt/MetricFlow platform remains. No production rollout is added. ADR-014 supersedes the Metabase choice in ADR-004; REQ-006 and V-006 keep their identifiers.

Consumers: business reviewer (performance and priorities), commercial analyst (category/seller/customer behavior), operations analyst (delivery and payment observations), DE/interviewer (metric trust and reproduction). Data is the accepted Olist snapshot, not healthcare/telesales or current company performance.

## Executive entry and navigation — ADR-015

The suite has one executive overview and five specialist pages, not one unbounded page of every chart. The executive consumer needs magnitude/change, contributors and delivery observations before choosing a follow-up investigation. Existing specialist questions and metric definitions remain authoritative.

- Entry: **00 · Executive Overview**. Eight monthly KPI cards (delivered merchandise/orders/customers/AOV, MoM, cancellation, eligible on-time rate and median delivery days), four contextual/contribution plots and three computed answers. No target traffic lights: no approved financial/service targets exist.
- Every page has an in-dashboard six-destination navigation strip. Links stay on the same retained published release and carry the selected month through Superset native-filter URL state. Navigation is not a drill-through to individual source orders.
- Overview/sales/commercial/service: one purchase month filters monthly KPIs, findings and navigation; historical trend charts retain their declared window.
- Customers: its repeat/cohort results retain cutoff 2018-08-31. Trust: findings retain the selected producer/release and live audit remains separately labeled. On these two pages the month selector affects **navigation only**, explicitly not customer history or producer quality.
- No new Warehouse tables, metrics, fact joins, application/frontend service, credentials or migrations. This revision changes governed Superset virtual datasets, chart metadata and presentation only.

Acceptance: all sixty chart objects execute, six pages render, June/July changes reconcile to independent SQL, all six links are clickable, forward/back/sibling routes preserve month and release, fixed-window results stay unchanged, empty denominators remain explicit, and rebootstrap creates no duplicate assets. `make verify-bi`, `make verify-browser` and unit/design checks provide bounded evidence. A prior publication-transition drill is not automatically extended to new charts.

| Executive question | Evidence / decision support | Specialist destination |
|---|---|---|
| What was delivered, and what changed? | Monthly value/orders/customers/AOV, MoM, cancellation and contextual trends; no assumed cause | Sales |
| Which categories and buyer states contribute? | Item-value/category and order-value/state contributions at compatible grains | Products & Sellers |
| How were eligible deliveries observed? | On-time numerator/denominator, median days and coverage, grouped by purchase month; no invented SLA | Delivery & Payments |
| Do observed customers return? | Fixed-window repeat/cohort, explicitly not a selected-month customer KPI | Customer Behavior |
| Can I trace and trust this version? | Retained published release/source cut, pinned producer quality and separately labeled live audit | Data Trust & Pipeline |

Risk: medium (BI presentation/metadata only). Non-goals: production rollout, arbitrary row-level drill-through, global category/state filters incompatible with existing export grains, and fabricated targets/causality. Bounded API/browser/idempotency results are recorded in implementation progress and the Superset evidence bundle. Open issues: mobile widths outside the two tested desktop sizes and a fresh concurrent-publication drill for the new overview/navigation are not verified; no production acceptance is implied.

Implementation/verification notes: Superset native filters update query responses, filter UI and rendered cells asynchronously; the browser gate waits for all three to agree, rather than accepting the first returned navigation query. Screenshots are captured from the visible baseline grid, not a transient rehydration frame after restoring a filter. The 1366/1720 checks cover all question/finding/follow-up columns as well as the six links; page-level overflow alone does not detect an internally clipped table. Navigation markup contains only fixed labels/relative links and a PostgreSQL-formatted month, never source customer/category HTML. The [pinned Superset dashboard implementation](https://github.com/apache/superset/blob/6.1.0/superset-frontend/src/dashboard/containers/DashboardPage.tsx) is the reference for native-filter URL hydration.

## Questions and report pages

### Business-facing presentation — ADR-016

The user's later feedback replaces the document-like dashboard chrome. The title and one concise context line precede a compact six-link navigation strip; KPIs, computed findings and charts take priority. There are no repeated `Dùng để`, `Cách đọc & phân tích sâu` or `Giới hạn kết luận` panels. Business pages do not display release/source-cut/SQL Lab implementation details. A short source/definition footnote preserves necessary interpretation; full reading/limitations guides remain in chart descriptions and this documentation. Customer cutoff stays visible, and trust/provenance remains on its dedicated page.

Scope is presentation only: no new Warehouse migration, source mutation, metric expression, narrative calculation or release publication. Navigation markup uses version 2; narrative wording uses version 3 to shorten follow-up and remove SQL Lab directions from business pages. Older virtual definitions are retained. Verification requires all six pages to omit rejected boilerplate, overview KPIs to fit the first desktop viewport, exact numeric/metric parity, and unchanged month/release/fixed-window navigation. Mobile layouts and production rollout remain outside scope.

| Page | Questions | Evidence and grain |
|---|---|---|
| Sales overview | How much delivered merchandise, how many orders/customers, AOV, cancellations? How does the selected month compare with earlier periods? | Existing five governed MetricFlow exports; month/day grain. Monthly distinct is not additive |
| Products and sellers | Which categories/sellers contribute most? How concentrated is merchandise value? Which buyer states contribute? | Item-grain exports; category/month, seller/month, buyer-state/month. No invented product names or product-level order AOV |
| Customer behavior | How many observed customers return? How much value comes from repeat customers? How do purchase cohorts retain customers? | Published order-level analytical view; customer identity SK, delivered orders; lifetime counts and cohort denominator explicit |
| Delivery and payments | How often are known deliveries on time? How long do deliveries take by buyer state? What payment methods/installments occur? | Orders with known eligible milestones; payment-record grain. Payment value is not merchandise revenue |
| Data trust and pipeline | Which source problems remain? Which runs succeed/fail? What version/source cut is shown? | Explicit published release and producer run; operations records labeled as live operational audit |

Default selected month is 2018-07 to avoid presenting the final observed month as a complete period. Trends retain 2017-01 to 2018-08 context when month KPIs change. July is an analytical choice, not a guarantee of source completeness. Source has partial boundary periods and right-censored outcomes.

## Data/metric contracts

- Eight existing business KPIs remain owned by MetricFlow; executive/commercial charts consume its validated exports.
- Governed SQL views expose additional published order/payment analysis. SQL definitions are versioned in migration 005 and documented; these additional analyses are not falsely called new MetricFlow metrics.
- Orders, payments and items are never joined atomically to calculate measures. Customer/fulfillment analyses use fct_orders; payment analyses use fct_payments and conformed dimensions only.
- Every business dataset is explicitly pinned to one ever-published release literal. A new publication does not change an open dashboard. Rebootstrap creates release-specific assets; retained links continue to work.
- Cohort: first observed delivered purchase month; activity: distinct customer with a delivered purchase in offset month; denominator: original observed cohort size. Future/unobserved cells remain absent, not zero. No causal churn/retention claim.
- Repeat customer: at least two observed delivered orders through the fixed analysis cutoff 2018-08-31. Customers with one order are not labeled churned. Recency, frequency and observed monetary value use that cutoff, not today's date; segment rules are descriptive, not predictive scores or a claimed full RFM scoring model.
- Delivery denominator: known nonnegative purchase-to-delivery duration, with promised delivery date, following existing fact eligibility. Missing/invalid dates are shown as coverage, not imputed.
- Payment methods/installments use records or recorded payment amount; they do not imply unique orders or collected/refunded cash.

## Verification

`make verify-bi` provisions real Superset assets and queries every chart. `make verify-browser` opens every report, checks chart responses, screenshots and native month filtering. `make analyze` writes SQL-backed findings plus machine-readable results and CSVs. V-006 checks MetricFlow parity, non-additive handling, analytics grain/reconciliation and release pinning; make verify-design remains independent offline validation.

## Commentary is part of the report, not an external caption

Every page has a concise business context and a **Điểm nhấn** table: three computed findings with period and follow-up. Full purpose/reading/limitations guidance is available in chart descriptions/documentation instead of repeated panels (ADR-016). The observation/inference distinction remains: a high contribution is not a profit claim, one observed purchase is not churn, and on-time performance is not good/bad without an agreed target.

`bi/superset_narratives.py` compiles versioned, pinned, read-only virtual datasets from governed exports/published analytical views. Sales/commercial/service narratives carry `purchase_month` and receive the same native filter as their corresponding charts. They are not hardcoded July captions. Customer commentary is full-window through 31/08/2018; the M1 figure weights original cohort sizes for eligible cohorts from 2017 onward. Trust commentary binds its release/producer; live attempts remain explicitly separate. Missing bases/zero denominators render “không đủ dữ liệu”, not invented 0% values.

API verification checks actual narrative numbers using separate analytical queries and arithmetic, including June/July, missing prior-period comparisons and a month with no delivered orders. Browser verification checks that all three answers are visible without horizontal clipping and change with native filters on all three monthly pages. Narrative text does not require AI inference or a paid service.

## Non-goals

Production infrastructure, reviews/clinical/telesales data, invented customer/product names, attribution across payment/items, forecasting/causal claims and fabricated historical SCD2. Prior Metabase artifacts are retained for audit, outside the default demo path.

## Open issues

Superset 6.1.0 is pinned and booted. The active catalog has 60 objects: 48 KPI/plots, six query-backed commentary tables and six query-backed navigation strips. Runtime results are in docs/evidence/superset/. Historical publication-transition proof covers the original ten sales charts; overview/commentary/navigation have separate explicit release/API/filter/click checks, not a newly claimed concurrent publication drill. Remaining production concerns are intentionally outside this local-demo revision.
