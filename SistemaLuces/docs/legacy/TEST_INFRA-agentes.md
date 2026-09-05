# [SUPERSEDIDA] TEST INFRASTRUCTURE & MATRIX SPECIFICATION: SISTEMA DE LUCES (V1 US500)

## 1. Overview and Test Philosophy

The **Sistema de Luces (V1 US500)** test infrastructure implements an authoritative, opaque-box, test-driven verification harness designed strictly around the domain specifications in **SPEC-001** and architectural decisions in **ADR-001**.

### Core Principles
1. **Opaque-Box Verification**: Tests exercise behavior exclusively through public module seams and domain contracts, asserting on observable outputs, deterministic state transitions, and error receipts rather than private implementation details.
2. **Deterministic Reproducibility**: All tests execute with fixed UTC timestamps, explicit pseudo-random seeds (`clock_seed=20260829`), isolated in-memory fixtures, and zero non-deterministic network, clock, or disk side-effects.
3. **Pure Standard Library Runtime**: Verification relies exclusively on Python 3.11.16 standard library (`unittest`, `dataclasses`, `datetime`, `zoneinfo`, `hashlib`, `json`, `sqlite3`, `pathlib`) without external test frameworks or third-party dependencies.
4. **Fail-Closed Security & Zero-Order Guarantees**: Security invariants (rejection of `LIVE` with `ENVIRONMENT_NOT_ALLOWED`, zero broker order-placement symbols, strict read-only allowlists, loopback UI binding) are structurally and dynamically verified across all test tiers.
5. **Progressive Testability**: The acceptance test suite is structured into modular tiers that validate domain behaviors, boundary conditions, cross-subsystem interactions, realistic market sessions, and explicit acceptance criteria (CA-1 through CA-28).

---

## 2. Test Architecture and Directory Layout

The testing tree is organized into co-located, specialized test packages under `tests/`:

```text
tests/
├── architecture/                     # Structural, security, and packaging integrity guards
│   ├── policy_check.py               # AST and security policy analyzer
│   └── test_forbidden_capabilities.py# Structural scans for forbidden symbols, scopes, live env
├── domain/                           # Pure domain logic, DTOs, schemas, and FSM tests
│   ├── test_api_dtos.py              # Root DTO serialization and validation
│   ├── test_event_envelope_and_canonical_json.py # Canonical JSON and event hash chaining
│   ├── test_metric_and_manifests.py  # Manifest schemas and metric definitions
│   ├── test_result_and_error.py      # Result[T] monad and DomainError code catalog
│   ├── test_schemas_roundtrip.py     # JSON schema validation and round-tripping
│   ├── test_signal_and_simulation.py # Signal V1 and Simulation V1 invariants
│   ├── test_state_machine.py         # Feed, Lights, and Simulation state machine transitions
│   └── test_vocabulary.py           # Domain enums, scaled integers, and environment parser
├── acceptance/                       # End-to-End Acceptance Test Suites (Tiers 1–4 & CA Matrix)
│   ├── __init__.py                   # Acceptance test package
│   ├── helpers.py                    # Shared test harness fixtures, generators, and spies
│   ├── test_tier1_features.py        # Tier 1: Feature Coverage (≥5 cases per feature category)
│   ├── test_tier2_boundaries.py      # Tier 2: Boundary & Corner Cases (limits, edge cases)
│   ├── test_tier3_interactions.py    # Tier 3: Cross-Feature Subsystem Combinations
│   ├── test_tier4_scenarios.py       # Tier 4: Real-World Market & Replay Scenarios
│   └── test_ca_matrix.py             # Acceptance Criteria Matrix (CA-1 through CA-28)
└── conftest.py                       # Suite-wide path initialization and test runner configuration
```

---

## 3. Test Tier Classification

The acceptance suite is partitioned into four distinct verification tiers plus the explicit Acceptance Criteria matrix:

### Tier 1: Feature Coverage (`test_tier1_features.py`)
Validates happy-path equivalence class representatives across all 34 features of the system inventory, ensuring that each core functional capability performs as specified under normal conditions:
- **Environment & Security**: Strict acceptance of `REPLAY`, `SHADOW`, `BROKER_DEMO_OBSERVED`; read-only capabilities.
- **Event Storage & Hash Chaining**: Canonical serialization, SHA-256 payload hashing, append-only sequencing.
- **Feed Health & Depth Gate**: Bid/ask processing, session monitoring, depth gate quarantine evaluation.
- **Causal Cases & Labeling**: S30/S60 temporal window aggregation, triple-barrier labeling (5 pt stop / 20 pt target).
- **Model Calibration & Gates**: Out-of-fold probability scaling, Brier/ECE score gating, drift detection.
- **Lights Policy & Signals**: 3-state machine transitions, valid signal emission with `valid_until_utc`.
- **Risk Engine & Paper Simulator**: USD 50 per-trade risk, lot sizing, paper order lifecycle simulation.
- **Import & Reconciliation**: Staged demo execution import, matching against simulated trades.
- **Observability & Metrics**: 8-plane metric calculation and snapshot generation.

### Tier 2: Boundary, Limit & Corner Cases (`test_tier2_boundaries.py`)
Validates edge cases, numerical boundaries, extreme values, off-by-one conditions, and error paths:
- **Environment & Live Rejection**: `LIVE`, `live`, `Live`, ` LIVE `, empty string, unknown environment strings.
- **Feed Quality Degeneracies**: Stale feeds at exact threshold (5000ms vs 5001ms), sequence gaps, clock rollbacks.
- **Risk Guardrails**: Exact risk limits ($50.00 vs $50.01), daily loss threshold ($249.99 vs $250.00), 2 vs 3 consecutive losses, 10 vs 11 daily openings, maximum 1 open position guard.
- **News Blackout Window**: Exact inclusive boundary timestamps (`[blackout_start, blackout_end]`).
- **Numerical & Floating Point Precision**: Strict rejection of `NaN`, `+Infinity`, `-Infinity`, non-scaled floats.
- **Ambiguous Labeling**: Concurrent stop and target hit within atomic quote tick (`AMBIGUOUS_STOP_FIRST`).
- **Path Traversal & Schema Quarantine**: Staged file paths containing `../`, unknown schema payloads.

### Tier 3: Cross-Feature Subsystem Combinations (`test_tier3_interactions.py`)
Validates pairwise and multi-feature interactions across subsystem seams:
- **Feed Degradation → Lights State Machine**: Stale/gapped feed immediately forcing `YELLOW` and blocking simulation opens.
- **Lights Policy → Risk Engine → Simulator**: `GREEN` signals passing risk checks vs `YELLOW` signals forcing `MONITOR` direction.
- **Causal Window → Labeling → Purged Splits**: Strict adherence to temporal cutoff (OPT-7) and zero leakage across embargoed folds.
- **Storage Event Sourcing → Hash Chaining → Backup/Restore**: Cryptographic chain verification during sequential appends and backup restore.
- **Paper Simulation → Single Position Guard → Kill Switch**: Active position rejecting overlapping proposals; cumulative daily drawdown triggering fail-closed kill switch.
- **Demo Trade Import → Staged Validation → Reconciliation**: Reconciling manual broker demo logs with simulated trades, flagging `UNMATCHED`.
- **Metrics Engine → Projection Views**: Aggregating state across all 8 metric planes without data corruption, preserving null reason codes.

### Tier 4: Real-World Application Scenarios (`test_tier4_scenarios.py`)
Validates comprehensive end-to-end multi-step operational workflows simulating realistic market sessions:
1. **Scenario 1 (Full NY Trading Session)**: Normal morning trading session with market open, S30 feature aggregation, GREEN signal emission, paper trade execution, target profit (+20 pts) take profit exit, and metric update.
2. **Scenario 2 (Adverse Market Volatility & Stale Feed)**: Flash volatility event resulting in a 5500ms feed stall; feed quality monitor transitions to STALE; lights force YELLOW; simulation proposals rejected with MONITOR direction.
3. **Scenario 3 (Loss Streak & Daily Drawdown Kill Switch)**: Series of 3 consecutive stopped trades triggering streak pause, followed by cumulative daily loss reaching USD 250 triggering fail-closed kill switch, blocking all subsequent trades until verified recovery.
4. **Scenario 4 (End-of-Day Demo Reconciliation & Metric Snapshot)**: Batch import of manual cTrader demo broker trades via staged copy, automated reconciliation against paper simulations, marking unmatched trades, and generating the full 8-plane metric report.
5. **Scenario 5 (Disaster Recovery & Deterministic Replay)**: Simulated process interruption, full database restore from snapshot, cryptographic hash chain validation, and deterministic replay from `clock_seed=20260829` reproducing identical output.

### CA Matrix Suite (`test_ca_matrix.py`)
Provides explicit 1-to-1 automated test coverage for Acceptance Criteria **CA-1 through CA-28** as specified in SPEC-001 §12.

---

## 4. Feature Inventory Mapping Matrix

| Feature # | Feature Name | Test Suite & Test Method | Tier | Acceptance Criteria |
|---|---|---|---|---|
| 1 | Closed Environment Model | `test_tier1_features.TestEnvironmentSecurityFeatures.test_allowed_environments` | Tier 1, 2 | CA-1 |
| 2 | Zero Order-Writing Capability | `test_forbidden_capabilities.ArchitectureGuardTests.test_current_repository_satisfies_security_policy` | Tier 1 | CA-2 |
| 3 | Demo Account Verification | `test_tier1_features.TestEnvironmentSecurityFeatures.test_demo_account_validation` | Tier 1, 2 | CA-3 |
| 4 | Read-Only Capabilities Allowlist | `test_tier1_features.TestEnvironmentSecurityFeatures.test_read_only_capabilities_allowlist` | Tier 1 | CA-2 |
| 5 | Read-Only Loopback UI | `test_ca_matrix.TestAcceptanceCriteriaMatrix.test_ca24_read_only_loopback_ui_and_csp_headers` | Tier 1, 2 | CA-24 |
| 6 | XSS Resilience (BUG-1) | `test_tier2_boundaries.TestBoundaryAndCornerCases.test_ui_xss_escaping_resilience` | Tier 2 | CA-24 |
| 7 | Append-Only Event Log | `test_tier1_features.TestStorageAndEventLogFeatures.test_event_envelope_persistence_and_serialization` | Tier 1 | CA-4 |
| 8 | Cryptographic Hash Chaining | `test_tier1_features.TestStorageAndEventLogFeatures.test_cryptographic_hash_chaining` | Tier 1, 3 | CA-4, CA-21 |
| 9 | Idempotent Ingestion & Conflict Rejection | `test_tier1_features.TestStorageAndEventLogFeatures.test_idempotent_ingestion_and_conflict_rejection` | Tier 1, 2 | CA-5 |
| 10 | Unknown Schema Quarantine | `test_tier1_features.TestStorageAndEventLogFeatures.test_unknown_schema_quarantine` | Tier 1, 2 | CA-6 |
| 11 | Backup, Restore & Rebuild Verification | `test_tier3_interactions.TestCrossFeatureInteractions.test_storage_backup_restore_and_hash_verification` | Tier 3, 4 | CA-21 |
| 12 | Feed Quality Monitor | `test_tier1_features.TestFeedQualityFeatures.test_feed_quality_transitions_and_stale_detection` | Tier 1, 2 | CA-7 |
| 13 | Depth Gate Quarantine | `test_tier1_features.TestFeedQualityFeatures.test_depth_gate_quarantine_evaluation` | Tier 1, 2 | CA-25 |
| 14 | Causal Case Builder (S30/S60) | `test_tier1_features.TestCaseBuilderAndLabelingFeatures.test_causal_case_builder_s30_s60` | Tier 1, 3 | CA-9 |
| 15 | Triple-Barrier Labeling | `test_tier1_features.TestCaseBuilderAndLabelingFeatures.test_triple_barrier_labeling_conventions` | Tier 1, 2 | CA-13, CA-14 |
| 16 | Purged & Embargoed Splits | `test_tier1_features.TestCaseBuilderAndLabelingFeatures.test_purged_and_embargoed_dataset_splits` | Tier 1, 3 | CA-26 |
| 17 | Out-of-Fold Model Calibration | `test_tier1_features.TestModelRegistryAndEvaluationFeatures.test_out_of_fold_model_calibration` | Tier 1 | CA-26 |
| 18 | Model Gate Policy & Promotion | `test_tier1_features.TestModelRegistryAndEvaluationFeatures.test_model_gate_promotion_evaluation` | Tier 1, 2 | CA-26 |
| 19 | Lights Policy & Hysteresis | `test_tier1_features.TestLightsPolicyAndSignalFeatures.test_lights_policy_transitions_and_hysteresis` | Tier 1, 2 | CA-8 |
| 20 | Signal Expiration & Non-Reuse | `test_tier1_features.TestLightsPolicyAndSignalFeatures.test_signal_expiration_and_non_reuse` | Tier 1, 2 | CA-11 |
| 21 | Yellow Signal Abstention | `test_tier1_features.TestLightsPolicyAndSignalFeatures.test_yellow_signal_abstention` | Tier 1, 3 | CA-12 |
| 22 | Paper Simulator | `test_tier1_features.TestRiskAndSimulationFeatures.test_paper_simulator_lifecycle` | Tier 1, 4 | CA-12, CA-15 |
| 23 | Single Position Invariant | `test_tier1_features.TestRiskAndSimulationFeatures.test_single_position_invariant` | Tier 1, 2 | CA-16 |
| 24 | Multi-Tripwire Risk Engine | `test_tier1_features.TestRiskAndSimulationFeatures.test_multi_tripwire_risk_evaluation` | Tier 1, 2 | CA-17 |
| 25 | Fail-Closed Kill Switch & Recovery | `test_tier1_features.TestRiskAndSimulationFeatures.test_fail_closed_kill_switch_and_recovery` | Tier 1, 3 | CA-18 |
| 26 | NY Session Midnight Reset | `test_tier2_boundaries.TestBoundaryAndCornerCases.test_ny_session_midnight_risk_reset` | Tier 2 | DM-12 |
| 27 | Read-Only Demo Trade Import | `test_tier1_features.TestImportAndReconciliationFeatures.test_read_only_demo_trade_import` | Tier 1, 2 | CA-19 |
| 28 | Execution Reconciliation | `test_tier1_features.TestImportAndReconciliationFeatures.test_execution_reconciliation` | Tier 1, 3 | CA-19 |
| 29 | Optional Journal V1 Extension | `test_ca_matrix.TestAcceptanceCriteriaMatrix.test_ca20_optional_journal_v1_isolation_and_not_included_status` | Tier 1 | CA-20, CA-28 |
| 30 | 8-Plane Reproducible Metrics | `test_tier1_features.TestObservabilityAndMetricsFeatures.test_eight_plane_metric_calculations` | Tier 1, 2 | CA-22 |
| 31 | Rebuildable Projections | `test_tier3_interactions.TestCrossFeatureInteractions.test_metrics_and_rebuildable_projections` | Tier 3 | CA-21 |
| 32 | Deterministic Replay Engine | `test_ca_matrix.TestAcceptanceCriteriaMatrix.test_ca23_golden_corpus_replay_determinism` | Tier 1, 4 | CA-23 |
| 33 | Daily Signal Target Non-Quota | `test_ca_matrix.TestAcceptanceCriteriaMatrix.test_ca27_daily_signal_target_non_quota_invariance` | Tier 1 | CA-27 |
| 34 | Root API Narrow Surface | `test_forbidden_capabilities.RootApiTests.test_root_api_exports_exactly_four_use_cases` | Tier 1 | CA-2, CA-28 |

---

## 5. Acceptance Criteria Traceability Matrix (CA-1 through CA-28)

| CA Code | Specification Requirement | Primary Test Method in `test_ca_matrix.py` |
|---|---|---|
| **CA-1** | Rejection of `LIVE` across all parsers, configs, DTOs, and queries with `ENVIRONMENT_NOT_ALLOWED` | `test_ca01_live_environment_rejected_at_all_layers` |
| **CA-2** | Zero order writing capabilities, endpoints, CLI commands, or scopes exist | `test_ca02_zero_order_writing_capabilities_and_scopes` |
| **CA-3** | Rejection of non-demo account metadata with `SOURCE_NOT_DEMO` | `test_ca03_demo_account_verification_and_hash_matching` |
| **CA-4** | Append-only event log with 3 UTC clocks, payload hash, and zero UPDATE/DELETE | `test_ca04_append_only_event_log_hash_chaining_and_clocks` |
| **CA-5** | Idempotent event ingestion; conflicting duplicate raises `INTEGRITY_ERROR` | `test_ca05_idempotent_ingestion_and_conflict_rejection` |
| **CA-6** | Unknown schema payload quarantined without mutating operational state | `test_ca06_unknown_schema_quarantine_without_state_mutation` |
| **CA-7** | Feed gap, stale (>5000ms), out-of-order, or rollback forces YELLOW and blocks sim | `test_ca07_feed_quality_degradation_forces_yellow` |
| **CA-8** | Mandatory intermediate YELLOW in lights state machine; direct `GREEN <-> RED` rejected | `test_ca08_lights_state_machine_mandatory_intermediate_yellow` |
| **CA-9** | Causal S30/S60 case builder strictly respects event cutoff without future leak | `test_ca09_causal_case_builder_temporal_cutoff_reproducibility` |
| **CA-10** | Signal envelope schema completeness (IDs, scores, probabilities, timestamps) | `test_ca10_signal_envelope_completeness_and_schema_conformance` |
| **CA-11** | Expired signal rejects simulation with `SIGNAL_EXPIRED` and is never reused | `test_ca11_signal_expiration_and_non_reuse` |
| **CA-12** | YELLOW light and `MONITOR` direction never emit `SIM_OPENED` | `test_ca12_yellow_signal_abstention_and_monitor_direction` |
| **CA-13** | Executable triple-barrier bid/ask execution conventions (LONG: ask in/bid out) | `test_ca13_triple_barrier_bid_ask_execution_conventions` |
| **CA-14** | Ambiguous stop/target touch in single tick resolves as `AMBIGUOUS_STOP_FIRST` | `test_ca14_ambiguous_stop_target_stop_first_convention` |
| **CA-15** | Incomplete economic contract rejects simulation as `REJECTED` | `test_ca15_incomplete_economic_contract_rejection` |
| **CA-16** | Maximum 1 open simulated position; overlapping proposals rejected with `OVERLAPPING_POSITION` | `test_ca16_single_position_invariant_and_overlapping_rejection` |
| **CA-17** | Deterministic risk engine tripwires matrix ($50 trade, $250 loss/DD, 3 streak, 10 open, blackout) | `test_ca17_risk_engine_tripwires_matrix` |
| **CA-18** | Fail-closed kill switch blocks new opens until verified recovery event | `test_ca18_fail_closed_kill_switch_and_recovery` |
| **CA-19** | Imported demo broker execution preserved and unmatched trades marked `UNMATCHED` | `test_ca19_demo_trade_import_and_unmatched_reconciliation` |
| **CA-20** | Optional Journal V1 isolation; reports `NOT_INCLUDED` in core without opening `tj.db` | `test_ca20_optional_journal_v1_isolation_and_not_included_status` |
| **CA-21** | Backup restore validates integrity check, hash chain, counts, and reconstructed views | `test_ca21_backup_restore_and_projection_rebuilding_verification` |
| **CA-22** | 8-Plane metric calculations conform to catalog, scaling, and null reason codes | `test_ca22_eight_plane_metric_calculations_and_null_reasons` |
| **CA-23** | Deterministic golden corpus replay from seed produces identical signal output | `test_ca23_golden_corpus_replay_determinism` |
| **CA-24** | Read-only loopback UI on 127.0.0.1, 405 on mutating verbs, CSP headers | `test_ca24_read_only_loopback_ui_and_csp_headers` |
| **CA-25** | Depth gate quarantine policy evaluation (`depth-gate-policy-v1`) | `test_ca25_depth_gate_policy_and_quarantine_evaluation` |
| **CA-26** | Model gate policy and promotion evaluation (`model-gate-policy-v1`) | `test_ca26_model_gate_policy_and_promotion_evaluation` |
| **CA-27** | Daily 5–10 signal target treated as observational metric, never forcing emissions | `test_ca27_daily_signal_target_non_quota_invariance` |
| **CA-28** | Zero runtime imports of `trading_bot` or Trading Journal package | `test_ca28_zero_trading_bot_and_journal_runtime_imports` |

---

## 6. How to Run the Tests

### Full Repository Verification
```bash
make verify
```
This executes:
1. `uv lock --check --offline`
2. `TMPDIR=.tmp TZ=UTC LC_ALL=C PYTHONHASHSEED=0 python3.11 -B -m unittest discover -s tests -t . -v`
3. `TMPDIR=.tmp TZ=UTC LC_ALL=C PYTHONHASHSEED=0 python3.11 -B -m compileall -q src tests`
4. `TMPDIR=.tmp TZ=UTC LC_ALL=C PYTHONHASHSEED=0 python3.11 -B -m tabnanny src tests`

### Acceptance Test Suite Only
```bash
python3.11 -B -m unittest discover -s tests/acceptance -t . -v
```

### Specific Acceptance Test File
```bash
python3.11 -B -m unittest tests.acceptance.test_ca_matrix -v
python3.11 -B -m unittest tests.acceptance.test_tier1_features -v
python3.11 -B -m unittest tests.acceptance.test_tier2_boundaries -v
python3.11 -B -m unittest tests.acceptance.test_tier3_interactions -v
python3.11 -B -m unittest tests.acceptance.test_tier4_scenarios -v
```
