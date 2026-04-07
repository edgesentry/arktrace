# Annex A — Submission of Statement of Work
# Cap Vista Accelerator Solicitation 5.0 — Challenge 1: Maritime Security Data Analytics
# Applicant: Yohei Onishi (trading as edgesentry)

---

## GENERAL SUBMISSION FOR ASSESSMENT

### Tech Solution

**Relevance**

arktrace addresses Challenge 1 directly: it identifies shadow fleet vessels operating in the grey zone through AIS manipulation, flag/name laundering, and illicit ship-to-ship transfers. The system ingests public AIS, sanctions, vessel ownership, and bilateral trade flow data, and produces a ranked watchlist of candidate shadow fleet vessels for patrol officer dispatch.

The primary technical contribution is the **C3 Causal Sanction-Response Model** — a Difference-in-Differences (DiD) regression framework that tests whether each vessel's evasion behaviour was causally triggered by a specific sanction announcement event. This is distinct from conventional anomaly detection: rather than flagging vessels that look statistically unusual, the model identifies vessels whose behaviour changed specifically because of a sanction event, separating genuine evasion responses from ordinary commercial route variation.

On top of the causal layer, an **unknown-unknown detector** surfaces vessels with no current sanctions link but evasion-consistent causal signatures — detecting threats 60–90 days before they appear on public OFAC listings (backtested on historical sanction announcements).

A network-based **backtracking propagation** module traverses the ownership graph from confirmed evaders to predict next-designation candidates among connected entities.

**Innovativeness**

| Capability | arktrace | Windward | Pole Star | MarineTraffic Enterprise |
|---|---|---|---|---|
| Causal inference (DiD) | ✅ | ✗ | ✗ | ✗ |
| Unknown-unknown detection | ✅ | ✗ | ✗ | ✗ |
| Pre-designation lead time | 60–90 days | — | — | — |
| Ownership graph | ✅ | Partial | ✗ | Partial |
| SHAP explainability | ✅ | ✗ | ✗ | ✗ |
| Edge-deployable (no cloud) | ✅ | ✗ | ✗ | ✗ |
| Annual software licence | $0 | ~$100k+ | ~$50k+ | ~$80k+ |

No known commercial maritime intelligence platform applies Difference-in-Differences causal inference to AIS event data around sanction announcement windows. The 60–90 day pre-designation lead time is a direct result of the causal model detecting evasion responses before sufficient evidence accumulates for a formal OFAC designation.

The solution does not rely on the disqualified methodologies listed in the challenge brief (vessel behaviour profiling, risk scoring, geofencing, or off-the-shelf behavioural analytics models) as its primary discriminator. AIS anomaly signals and sanctions screening serve as the evidentiary substrate that feeds the causal model — not the output claim.

**On proprietary datasets:** The challenge asks for "relevant proprietary datasets." arktrace uses no proprietary feeds by design — not as a gap. OpenSanctions fuses OFAC SDN + EU FSF + UN 1267 (500k+ entities, weekly updates) — broader and more timely than most commercial feeds. The novel signal fusion (AIS + sanctions ownership graph + Equasis vessel registry + UN Comtrade trade flows + GDELT geopolitical events) is not available in any single commercial product. The Precision@50 = 0.62 result — a 6× lift over random — was achieved entirely on open-access data, demonstrating that the methodological innovation, not data exclusivity, drives performance. Proprietary feeds (Windward vessel intelligence, Lloyd's cargo manifests) can be integrated as additive signal sources in a future scale-up phase without architectural changes.

**Challenge terminology alignment:** arktrace directly detects all three behaviours named in Challenge 1: AIS spoofing (`position_jump_count`), name/flag changes (`name_changes_2y`, `flag_changes_2y`, `high_risk_flag_ratio`), and illicit ship-to-ship (STS) transfers (`sts_candidate_count`, `sts_hub_degree`). These are the evidentiary features that feed the causal model, not the final output signal. Coverage extends to the full challenge geographic scope: up to 1,600 nm from Singapore to the 200 m bathymetric boundary (GEBCO depth mask applied during STS candidate detection).

**Current tech maturity:** Working implementation. Full pipeline deployed and validated on Singapore / Malacca Strait dataset. Measured Precision@50 = 0.62 on first run (target ≥ 0.60). Deploys via `docker compose up` on a standard laptop (4 vCPU / 8 GB RAM). No GPU, no cloud dependency, no proprietary data feeds.

GitHub: https://github.com/edgesentry/arktrace

---

### Impact

arktrace is a new open-source project built specifically for this challenge. It has not yet been deployed with external clients. The following demonstrates technical impact through validated metrics:

- **Precision@50 = 0.62** on the Singapore / Malacca Strait dataset — a 6× lift over the ~0.10 random baseline for the monitored population
- **60–90 day pre-designation lead time** backtested against historical OFAC sanction announcements
- **Full pipeline runtime ~45 minutes** from raw public data to ranked watchlist on a standard laptop
- **Incremental re-score under 60 seconds** per batch during live monitoring

The solution is fully open-source (Apache-2.0 / MIT), meaning any successful trial result can be adopted and scaled by Cap Vista or its nominees at zero software licensing cost.

---

### Others

**Team**

Solo practitioner: Yohei Onishi (Singapore Permanent Resident), applying as an individual under the trading name edgesentry.

20 years of experience in software engineering, data platform engineering, and AI platform development. The full arktrace pipeline — causal inference model, ownership graph (Lance Graph), scoring engine (HDBSCAN + Isolation Forest), FastAPI + HTMX dashboard, and patrol handoff workflow — was designed, built, and validated by a single engineer.

The scope of work will be executed outside business hours. All IP is owned by Yohei Onishi personally. Should Cap Vista elect to proceed to a full-scale engagement requiring a corporate counterparty, incorporation will be completed prior to that contract signature.

**Financial**

The proposed scope of work is costed at $5,000 SGD, covering infrastructure, data API, and miscellaneous costs only. The founder will contribute time pro bono. No advance payment is required. The founder has sufficient personal financial runway to execute the proposed scope without requiring upfront capital from Cap Vista.

**Past Track Records**

arktrace is a new project with no prior commercial deployment. Technical credibility is demonstrated through the open-source repository, working implementation, and measured baseline metrics (Precision@50 = 0.62). The full codebase, pipeline documentation, and evaluation methodology are publicly reviewable at https://github.com/edgesentry/arktrace.

**Tech Risks**

| Risk | Mitigation |
|---|---|
| AIS data quality / coverage gaps | Multiple AIS sources (aisstream.io + Marine Cadastre + AISHub); gap detection built into pipeline |
| Causal model false positives | HC3 robust standard errors; p-value threshold configurable; analyst review required before dispatch |
| Equasis scraping rate limits | Batched crawling with exponential backoff; cached in Lance Graph; monthly refresh sufficient |
| Solo-practitioner execution risk | All code is open-source and fully documented; Cap Vista can fork and continue independently |
| Part-time availability | Work executed outside business hours; 45-day timeline is calibrated accordingly; no hard dependency on full-time availability |

**Scalability:** One DuckDB file per region; shared Lance Graph for global ownership data. Adding a region requires one CLI flag change and a new VM. Infrastructure cost at global scale (5 regions, ~100k active vessels/month): ~$400–$1,000/month cloud, or $0 on-premises. Software cost at any scale: $0.

---

## ANNEX A — PROPOSED SCOPE OF WORK

### Scope of Work

A 45-day proof-of-concept trial of the arktrace Causal Inference Engine for Shadow Fleet Prediction, focused on the Singapore / Malacca Strait area of interest.

**Week 1 — Deployment and baseline ingestion**
- Deploy arktrace pipeline on Cap Vista-provided VM or cloud environment using `docker compose up`
- Ingest 6 months of historical AIS data for the Singapore / Malacca Strait bounding box (aisstream.io + Marine Cadastre)
- Load OFAC SDN, EU FSF, and UN 1267 sanctions lists via OpenSanctions
- Pull vessel ownership chains from Equasis; build Lance Graph ownership network
- Run full feature engineering and scoring pipeline; generate initial `candidate_watchlist.parquet`

**Weeks 2–3 — Baseline validation**
- Run held-out evaluation against OFAC-listed vessels present in the Singapore AIS dataset
- Validate Precision@50 ≥ 0.60 target
- Demonstrate 6× lift over random baseline
- Compare causal model output against naïve AIS-gap-only baseline

**Weeks 3–6 — Live monitoring and dashboard handover**
- Connect live aisstream.io WebSocket for the Singapore / Malacca Strait bounding box
- Run continuous re-scoring at 15-minute cadence
- Provide Cap Vista with access to the FastAPI + HTMX analyst dashboard
- Conduct walkthrough session demonstrating: ranked watchlist, SHAP signal explanation, analyst chat (local LLM), patrol dispatch workflow

**Week 7 — Final report and handover**
- Deliver written trial report covering: methodology, dataset used, Precision@50 result, causal model output samples, unknown-unknown candidates identified, system performance metrics
- Deliver Docker Compose deployment package and setup documentation for Cap Vista's independent operation

---

### Deliverables

**Software (open-source, adapted from open-source):**

| Item | Type | Details |
|---|---|---|
| arktrace pipeline | Open-source software (Apache-2.0 / MIT) | On-premises deployment via Docker Compose. Python 3.12, DuckDB, Polars, Lance Graph, scikit-learn, SHAP, FastAPI, HTMX. Readiness: working implementation, Precision@50 = 0.62 validated. No GPU required. |
| C3 DiD causal model | Proprietary module (within arktrace) | `src/score/causal_sanction.py`. DiD OLS with HC3 robust SEs. Numpy/scipy only, no external causal library. |
| Unknown-unknown detector | Proprietary module (within arktrace) | `src/analysis/causal.py`. Surfaces non-sanctioned vessels with evasion-consistent causal signatures. |
| Analyst dashboard | Open-source software | FastAPI + HTMX web UI. Runs at localhost:8000. MapLibre GL JS map, ranked watchlist, SHAP explanations, SSE alerts, patrol dispatch. |
| Local LLM integration | Open-source software | Ollama / MLX provider. Context-injected analyst briefs. No external API calls. |

**Data sources (all open-access, no proprietary datasets):**

| Dataset | Source | Cost |
|---|---|---|
| AIS positions (live) | aisstream.io WebSocket | Free (API key) |
| AIS positions (historical) | Marine Cadastre | Free download |
| Sanctions entities | OpenSanctions (OFAC + EU + UN) | Free (CC0) |
| Vessel ownership | Equasis | Free (registration) |
| Bilateral trade statistics | UN Comtrade+ REST API | Free (500 req/day) |
| Geopolitical events | GDELT Project | Free |

**Documents:**
- Trial report (PDF)
- Deployment and setup documentation

No hardware deliverables. No export-controlled items. Solution is software-only, on-premises.

---

### Table A-1: Price Proposal

| S/N | Description | Qty | Unit Price (SGD) | Total Price (SGD) | Remarks |
|---|---|---|---|---|---|
| 1 | Cloud infrastructure — VM, storage, networking (45-day trial period) | 1 | $200 | $200 | AWS / GCP t3.xlarge equivalent or Cap Vista-provided VM |
| 2 | AIS streaming API (aisstream.io, live tier) | 1 | $100 | $100 | Optional if Cap Vista provides AIS feed |
| 3 | Data API costs (UN Comtrade+, Equasis registration) | 1 | $200 | $200 | One-time registration and bulk data pull |
| 4 | Miscellaneous (document preparation, incidentals) | 1 | $500 | $500 | |
| 5 | Contingency | 1 | $4,000 | $4,000 | Buffer for scope changes, additional data sources, or unforeseen API costs |
| | **Total** | | | **$5,000 SGD** | Exclusive of GST |

> All prices are in Singapore Dollars (SGD), exclusive of GST.
> This quotation includes all necessary activities and deliverables under the proposed scope of work.
> Prices are inclusive of handling and packing charges. No other charges apply.
> This offer is valid for two (2) months after submission closing date.

---

### Table A-2: Payment Schedule

| Payment Event No. | Description of Payment Event | Payment Quantum (% of Contract Price) | Payment Schedule | Documents to be Presented |
|---|---|---|---|---|
| 1 | Upon successful completion of trial and delivery of: (1) working arktrace deployment on Cap Vista environment, (2) Precision@50 validation result, (3) trial report | 100% | Contract Signature + 2 months | Electronic Invoice; Certificate of Completion duly endorsed by Cap Vista's authorised representative |

> No advance payment required.
> Single milestone payment upon full delivery — minimises Cap Vista's risk.

---

### Table A-3: Option to Purchase for Scale-Up

| S/N | Description | Qty | Unit Price (SGD) | Remarks |
|---|---|---|---|---|
| 1 | Extension to additional AoI regions (per region: Japan Sea, Middle East, Europe, US Gulf) | Up to 4 | $2,000 per region | Includes region-specific AIS data ingestion, bbox configuration, and validation run |
| 2 | Ongoing maintenance and support (per month, post-PoC) | Up to 12 months | $500/month | Bug fixes, model recalibration, dependency updates |
| 3 | Custom feature development (e.g. additional signal sources, SAR image integration) | TBD | $5,000 per feature | Scoped and agreed per feature request |

> Option to Purchase offer valid for one (1) year after completion of proof-of-concept.
> Cap Vista may exercise the Option in as many phases as it deems fit.
> All software developed under scale-up remains open-source unless otherwise agreed in writing.
