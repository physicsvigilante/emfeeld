# Verified Ensemble Evidence Table V1 — read-only Markdown presentation contract

**Classification:** R1 *presentation only*, under [Issue #28](https://github.com/physicsvigilante/emfeeld/issues/28). **Candidate base:** fully post-merge-qualified `main` `fbdf66e56b3a89a5cf1bea6c0b403c9fc8d9ebcd`, Git tree `c3bf1a28f0b97f80b722d40f9616711e1587a1f1`. No new field law, integrator, tolerance, derived observation, unit conversion, mutable cache, output file or viewer. A focused independent-context R1 review is mandatory before merge. Escalate to R2 if numerical/evidence meaning changes.

## Why a Markdown projection

`scenario_ensembles measurements` already provides a fully source-validated JSON projection of each sealed native cross-scenario comparison. Its exact source IDs, signed values, SI units, statuses, missing-operand codes and original saved SHA256 receipts are authoritative; opening individual `member-XX/comparison/result.json` files is unnecessary. This V1 formats *only that existing verified readout* into a human-readable table for a teacher or an LLM. It does not become a second independent scientific data source or teaching-acceptance assessment.

## Bounded CLI and exit contract

```text
python -m emfeeld.scenario_ensembles table ENSEMBLE_OUTPUT --store EXACT_STORE --using ORIGINAL_PARENT_RUN
python -m emfeeld.scenario_ensembles table ENSEMBLE_OUTPUT --store EXACT_STORE --using ORIGINAL_PARENT_RUN --member EXACT_DECLARED_ID
```

- Exact `--member` ID optionally filters the displayed rows only **after whole-ensemble integrity inspection**. `--member baseline` selects a real named sibling `baseline`, never the separate freshly computed common baseline. No `--baseline`, `--sample-index`, `--output`, filesystem output path or figure rendering.
- Call the existing **`read_ensemble_measurements` once**; it performs all the original `inspect_ensemble`, native comparison, source-file and read-time original `integrity.json` byte/hash checks. This command formats its resulting in-memory verified JSON object without opening any additional file or inspecting physics a second time. A changed/invalid original source must be refused before printing a completed table.
- Write one deterministic UTF-8 Markdown document to **stdout only**. Complete whole ensemble: CLI exit `0`; legitimately partial whole ensemble: exit `1` even if the selected member is complete; malformed selector, prohibited flags or source integrity refusal: exit `2` with an error on stderr and **no table on stdout**. Existing `run`, `inspect`, `view` and `measurements` commands retain their behavior.
- No write into or near the source/model-store/ensemble/template or any other saved evidence. Standard CLI shell output redirection by the *caller* is not an application-managed output or evidence seal, and is not to be confused with an authorised tool writing into a sealed study.

## Human-visible information and original precision

Header declares original `ensemble` ID, original **global** `complete/partial` status, exact member filter selection, full parent reference and source parent native `run.json` SHA256. A prominent note states **right member minus left freshly recomputed baseline** in original SI units, not a physical time transition or independent correctness certification.

The first Markdown table has one row per originally saved native comparison, maintaining original member order and original comparison order. Columns: member ID and declaration index; comparison ID; original left/right observation IDs; native comparison type; **signed original** scalar or JSON vector; original SI unit; original recorded context (coordinate/endpoints/time); original named particle ID (when any); original error bound (when any); status plus original typed reason; and original comparison result SHA256. An unavailable result is written `unavailable (no numeric value)` with the original `unknown_operand` code and reason, never numeric `0`. A rejected or native-incomplete member is displayed as an explicit `not measured: <original reason>` row without fabricated comparison IDs/values.

The second table includes exact original five source bindings **per compared member**: comparison `request.json`, `result.json`, `integrity.json` SHA256, original saved left baseline `run.json` SHA256 and right member `run.json` SHA256. Unattempted comparisons have absent (`—`) hashes, never fake zero hashes. It also declares saved original revision decision and native/comparison statuses for each member.

Numerical tokens are emitted via Python's standard shortest-round-trip JSON serialization of already-decoded original floats and exact JSON integers. This does **not** round/truncate them to display precision, convert units or alter original results. For example a signed `-0.0`, small scientific notation, positive and negative scalar, vector, exact saved observation times and ordered potential-difference convention preserve their numerical meaning; source raw bytes in sealed result.json remain authoritative if lexical formatting matters. No arithmetic, new uncertainty estimate, difference or interpolation occurs.

## Markdown text and source safety

All free-text/source-derived cell content is treated as **inert Markdown text**, not link/HTML/Markdown markup. It is converted to an ASCII JSON string representation for control-character escapes and HTML character entities for table pipes, HTML tags, backticks, Markdown emphasis, links, colons in URLs and email-address delimiters, including bare `www.` autolinks. Original `|`, `\n`, markdown link syntax and HTML-looking strings cannot inject a new Markdown row, link, script, heading, embedded screenshot or apparent source URL. The renderer deliberately creates **no hyperlinks** from arbitrary recorded text. Readers requiring exact original raw strings should inspect the sealed native JSON through existing validated commands, not reverse-engineer a display entity.

Table presentation is not an executable Markdown/HTML engine: the tool only emits text. No new remote link fetching, path navigation, template interpolation, arbitrary code, filesystem mutation or screenshot is permitted.

## Verification and residual limitations

Acceptance requires: E1 complete, G1 honest partial, T1 static, original signed vector/scalar and SI values/units/context, named member `baseline` at nonfirst index, 2–4 member order, rejected/partial native member truthful omission, `unknown_operand/null` missing baseline, exact original SHA bindings, zero-write successful/refusal cases, malformed Markdown-looking content, and B1 mid-read nested/outer integrity drift closure. Run historical PR #23 R2 grammar/hash guards and PR #25 foreign screenshot/identity guards unchanged. Run fresh Linux/Windows clean-install full/historical/real-PyVista CI, original source ZIP/tree audit and source-linked E1/G1/T1 transfer, and a separate Chat B focused review of the exact frozen source before any qualified merge. After merge, run fresh `main` CI and original archive re-audit.

The source model is prescribed analytic electrostatic or Newtonian gravitational fields, not arbitrary time-dependent electromagnetic fields, responsive conductors or interacting many-body dynamics. SHA256 inventories are **unkeyed integrity**, not authentication against a malicious party who replaces and re-seals everything; local file preflight is not hostile concurrent-writer ACID. Real PyVista offscreen rendering is not manual Windows pointer certification. No classroom observation, human independent physics certification, theorem, textbook-answer completeness or student-learning acceptance is established by a rendered table.
