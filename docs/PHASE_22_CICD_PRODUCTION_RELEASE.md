# PHASE 22 — CI/CD & PRODUCTION RELEASE
## Step 22.1 — Deployment Strategy Resolution (CAP-22 "container build" vs. Phase 20's locked Docker-free decision)

Status: CONTRACT/DECISION DOCUMENT ONLY — **no CI/CD implementation, workflow, script, dependency, or deployment change accompanies this document.** Phase 22 is otherwise still `NOT STARTED` (`docs\PHASE_TRACKER.md`).
Authoritative sources: `PS_26045_IP_SAKTI_COMPLETE_RESEARCH_MASTER_REFERENCE.pdf`, `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_TRACKER.md`, `config\acceptance_contract.yaml` (`CAP-22`), `docs\PHASE_20_DEPLOYMENT_ENGINEERING.md`.
Governed by: `docs\MASTER_REFERENCE_LOCK.md` Section I (Phase Isolation Rule) — this document defines an interface/strategy a later Phase 22 implementation step will use; it implements none of it.

**This document resolves exactly one thing:** whether Phase 22's own future CI/CD implementation may exclude a Docker/container-build step, given that `CAP-22`'s own text still names one. It does not design the CI pipeline, choose a CI vendor, define tests, or implement anything. `render.yaml`, `requirements-render.txt`, and every Phase 20/21 file remain byte-for-byte unchanged by this document.

---

## 1. Original CAP-22 requirement

`[OFFICIAL SOURCE]` `config\acceptance_contract.yaml`, `CAP-22` (verbatim, unedited by this document):

```yaml
- id: "CAP-22"
  name: "CI/CD & Production Release"
  owner_phase: 22
  required_behavior: "Automated tests -> evaluation gates -> container build -> staging smoke tests -> release artifact -> production deployment."
  test_requirement: "CI pipeline run producing a versioned, rollback-tested release."
  acceptance_criterion: "A release is reproducible, tested, and rollback-capable."
  status: "DEFINED"
```

`[OFFICIAL SOURCE]` `docs\PHASE_TRACKER.md`'s Phase 22 row carries the same "container build" wording in its own `Implementation` sketch. **Neither file is modified by this document** — per this project's own established pattern (`docs\PHASE_20_DEPLOYMENT_ENGINEERING.md` Section 1 similarly left `PHASE_TRACKER.md`'s stale Phase 20 sketch untouched rather than silently rewriting it), a disclosed interpretation lives in a companion document, not as a silent edit to the original contract text.

`[OFFICIAL SOURCE]` The word "container" traces to `docs\MASTER_REFERENCE_LOCK.md` Section E, **"Final Core Pipeline (from Final Architecture Decision Lock)"**: `Packaging: Docker / Docker Compose (initial deployment)`. This is important to state precisely: this line is itself part of the PDF's **locked** decision layer (the Final Architecture Decision Lock), not superseded exploratory roadmap material within the PDF. Section 3 below explains why this matters and corrects an imprecise framing used in the prior Phase 22 readiness inspection.

## 2. Phase 20's later decision

`[OFFICIAL SOURCE]` `docs\PHASE_20_DEPLOYMENT_ENGINEERING.md` Section 1, **disclosed explicitly, not discovered here**: Phase 20 built a **Render Blueprint** (`render.yaml`) targeting Render's native Python-web-service and static-site runtimes directly — no Docker, no Compose, no container image, anywhere. Enforced structurally, today, by Phase 20's own test suite (`tests\test_phase_20_deployment.py`, all 16 passing, reconfirmed during this step):
- `test_render_yaml_declares_exactly_two_free_services_no_database_no_docker`
- `test_no_docker_or_procfile_artifacts_were_introduced`

`[OFFICIAL SOURCE]` Render's Blueprint spec (`render.yaml`, `[EXTERNAL RESEARCH]`-verified against `render.com/docs/blueprint-spec`) supports `runtime: docker` as one option among several; Phase 20 deliberately chose `runtime: python`/`runtime: static` instead, and no `runtime: docker` value exists anywhere in `render.yaml`. A container image, if one were built by a CI pipeline, would be consumed by nothing in the actual deployment path — Render never asks for or accepts one under the current Blueprint.

## 3. Precedence rule supporting the resolution

`[ENGINEERING RECOMMENDATION]` — a corrected, more precise basis than the prior readiness inspection's shorthand. That inspection cited `MASTER_REFERENCE_LOCK.md` Section B ("the later locked decision... takes precedence") as if it directly authorized this resolution. On closer reading here, **that citation is imprecise and is corrected rather than repeated**: Section B governs conflicts *within the source PDF itself* (its earlier "Deep Technical Research & Roadmap" section vs. its later "28-Part Research Compendium" / Final Architecture Decision Lock / Final Decision Lock). The Docker/Compose packaging line is *itself* part of that later, locked layer (Section 1 above) — it is not exploratory material the PDF's own Final Decision Lock superseded. Section B, read narrowly and honestly, does **not** by itself license dropping it.

The actual, sourced basis for this resolution is the combination of three things, none of which is Section B alone:

1. `[OFFICIAL SOURCE]` `docs\DEVELOPMENT_RULES.md` Rule 6 (No Premature Dependencies): "No dependency is added because it 'may be useful later.' Every dependency must be justified by the needs of the current phase." A Docker image built by a CI pipeline but consumed by nothing in Phase 20's actual (already complete, already locked-in-practice) deployment path would be exactly such an unjustified dependency/artifact.
2. `[OFFICIAL SOURCE]` `docs\DEVELOPMENT_RULES.md` Rule 2 (Clean Implementation): "Prefer the simplest approach that satisfies the phase's acceptance gate." CAP-22's acceptance criterion is "reproducible, tested, and rollback-capable" — it does not require the release mechanism to be container-shaped; a release artifact and rollback mechanism can satisfy this against Render's native runtimes without a container.
3. `[ENGINEERING RECOMMENDATION]`, evidenced by this project's own repeated, already-approved practice of a later phase disclosing an explicit amendment to an earlier constraint rather than treating it as immutable — cited directly in this project's own Phase 21 contract (`docs\PHASE_21_OBSERVABILITY_BACKUP_CORPUS_REFRESH.md` Section 30): "Phase 6 relaxing Phase 4/5's dependency checks, Phase 17 dropping `fastapi` from ten earlier forbidden-dependency lists." Phase 20's own Docker exclusion fits this exact, established pattern: explicit (its own Section 1), disclosed (calls itself "a disclosed deviation... not an oversight"), and enforced by tests (Section 2 above) — never a silent edit.

`[ASSUMPTION]` This resolution treats Phase 20's already-complete, already-tested state as the binding *current reality* Phase 22 must build against (per `docs\MASTER_REFERENCE_LOCK.md` Section I, Phase Isolation: each phase builds on the real, completed state of prior phases) — not as a fresh re-litigation of whether Phase 20 was "allowed" to make that choice in the first place. That original choice is Phase 20's own, already-accepted deliverable and is explicitly out of this document's scope to reopen (the Strict No-Implementation Rule for this step forbids modifying Phase 20).

**Conclusion:** the governing documents do not contain an explicit, generic "later phase overrides Final Decision Lock" clause, but they do contain (a) two directly-applicable general engineering rules (Rules 2 and 6) that independently argue against adding an unconsumed container-build step now, and (b) a demonstrated, repeated, already-accepted project practice of exactly this kind of disclosed amendment. Together these are sufficient to resolve the contradiction for Phase 22's own implementation, **without claiming CAP-22's original wording was always Docker-free** (it was not — Section 1 quotes it verbatim) and **without silently reinterpreting it** (this document is that disclosure).

## 4. Final Phase 22 deployment strategy

`[ENGINEERING RECOMMENDATION]` CAP-22's lifecycle, reworded to remove the one step (`container build`) that does not connect to anything in this project's actual, locked deployment target:

```
Automated tests
  -> evaluation gates
  -> reproducible release artifact
  -> staging smoke tests
  -> production deployment
  -> rollback capability
```

Every other word of CAP-22's own acceptance criterion — "reproducible, tested, and rollback-capable" — is preserved exactly; nothing is weakened, only the packaging mechanism is changed from "container image" to "whatever Render's native Python/static runtimes already consume" (Phase 20, unchanged).

## 5. Explicit Docker/container exclusion

`[ENGINEERING RECOMMENDATION]` A Docker or container build step is **NOT** part of this project's Phase 22 implementation. No `Dockerfile`, `docker-compose.yml`/`.yaml`, container registry, or `runtime: docker` service is to be introduced by Phase 22. Should a future, explicit instruction determine a container-based release IS actually needed (e.g., a hosting-platform change away from Render), that would be a new, disclosed decision at that time — following the same pattern used here — never assumed or silently reintroduced.

## 6. Definition of "release artifact"

`[DEFERRED]` No governing source (`config\acceptance_contract.yaml`, `docs\MASTER_REFERENCE_LOCK.md`, `docs\DEVELOPMENT_RULES.md`, `docs\PHASE_20_DEPLOYMENT_ENGINEERING.md`, `docs\PHASE_21_OBSERVABILITY_BACKUP_CORPUS_REFRESH.md`) defines a concrete "release artifact" shape for this project today. `src\api\app.py`'s `API_VERSION` constant (currently `"v1"`) is a distinct, unrelated concept — an API URL-path/OpenAPI contract version, never a deployable-release identifier — and must not be conflated with one. Per this step's own instruction, this is marked `[DEFERRED]` rather than invented here; defining it (e.g., a git-tag scheme, a commit-SHA-based identity, a build manifest) is explicit future Phase 22 implementation work, not a Step 22.1 decision.

## 7. Impact on staging

`[ASSUMPTION]`, unresolved: CAP-22 still requires "staging smoke tests." Whatever staging mechanism Phase 22 eventually adopts must itself be Docker-free and Render-Free-tier-compatible (Section 10 of the readiness report) — e.g., a second Render Free native-runtime service, never a container-based staging environment. The exact mechanism (a distinct Render service, a local smoke-test run against a preview build, or something else) is `[DEFERRED]` to a later Phase 22 implementation step; this document only fixes that whatever it is, it will not be container-based.

## 8. Impact on production deployment

`[OFFICIAL SOURCE, reaffirmed]` Production deployment continues to mean the two existing Phase 20 Render services (`ipsakti-backend`, `ipsakti-frontend`) described in `render.yaml`, unchanged. Phase 22 does not introduce a new deployment target, hosting provider, or runtime — it only automates *triggering and verifying* a deployment to the target Phase 20 already built.

## 9. Impact on rollback

`[ENGINEERING RECOMMENDATION]` Rollback cannot be designed around a container-image version (e.g., "redeploy the previous image tag"), since no container image exists anywhere in this deployment path. Whatever rollback mechanism Phase 22 eventually adopts must instead work against Render's own native deployment history (e.g., Render's own redeploy/rollback-to-a-previous-build feature, `[EXTERNAL RESEARCH]`, to be verified against current Render documentation before implementation) or a git-based redeploy of a previous commit/tag. The exact mechanism is `[DEFERRED]` to a later Phase 22 implementation step; this document only fixes the constraint that it must be container-free, consistent with Section 5.

## 10. Explicit Phase 23 boundary

`[OFFICIAL SOURCE, reaffirmed]` Phase 22 may define an interface or gate a later Phase 23 (Production Validation) calls (e.g., a rollback command, a staging health-check target) but implements none of Phase 23's own acceptance battery — load tests, multilingual regression, jurisdiction isolation, the full Final Production Gate (`docs\MASTER_REFERENCE_LOCK.md` Section K) — all of which remain Phase 23's own, separately-owned scope (`docs\MASTER_REFERENCE_LOCK.md` Section I, Phase Isolation Rule). Nothing in this document starts, implies, or substitutes for Phase 23 work.

## 11. What remains for later Phase 22 steps

`[DEFERRED]`, explicitly out of scope for this document:
- Choice of CI runner/vendor (e.g., GitHub Actions) — not mandated by CAP-22's own text (it names no vendor); a later, explicit decision.
- The concrete "release artifact" definition (Section 6).
- The concrete staging mechanism (Section 7) and rollback mechanism (Section 9).
- Any workflow file, script, test, or dependency — none exists yet and none is added by this document.
- Reconciling `docs\PHASE_TRACKER.md`'s Phase 22 row and `config\acceptance_contract.yaml`'s `CAP-22` wording with this document — left for a separate, explicit update (the same disclosed-gap pattern Phase 20's own document already used for its own tracker row), not done silently here.

## 12. Step 22.7 — Rollback System (IMPLEMENTED)

`[ENGINEERING RECOMMENDATION]` This section resolves Section 9's `[DEFERRED]` rollback mechanism and the corresponding bullet in Section 11 — disclosed here as an added section, never as a silent rewrite of Sections 9/11 themselves, which remain an accurate historical record of the Step 22.1 decision point. Implementation: `.github/workflows/rollback.yml`, `scripts/rollback_target.py`, one new step in `.github/workflows/ci.yml`'s `production` job, `tests/test_phase_22_rollback.py`.

### 12.1 Known-good release definition

`[ENGINEERING RECOMMENDATION]` A commit qualifies as a valid rollback target ("known-good") ONLY when, in a single CI run for that exact commit: `backend` CI passed, `frontend` CI passed, the `evaluation` gate passed, `release-artifact` was generated, `staging` passed, AND both `production` job deploys (backend and frontend) succeeded AND both post-deploy production smoke tests passed. A commit that merely passed CI, or reached `staging`, but was never actually deployed to production is explicitly **not** a valid rollback target by this definition.

### 12.2 Recording the known-good SHA — GitHub repository variable

`[ENGINEERING RECOMMENDATION]` The durable record is a GitHub repository **variable**, `RENDER_LAST_KNOWN_GOOD_SHA` (never a secret — a commit SHA is not sensitive information). It is written by one new step appended to the end of the existing `production` job in `ci.yml`, reached only if every step before it in that job already succeeded (GitHub Actions' own default sequential-failure behavior — no additional condition was needed to express "only after both deploys and both smoke tests passed").

`[OFFICIAL SOURCE]` **Permission-model finding, verified this session against GitHub's own current documentation** (`docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions`, `docs.github.com/en/rest/actions/variables`): the complete, documented list of `permissions:` keys available to scope the built-in `GITHUB_TOKEN` — `actions`, `artifact-metadata`, `attestations`, `checks`, `code-quality`, `contents`, `deployments`, `discussions`, `id-token`, `issues`, `packages`, `pages`, `pull-requests`, `security-events`, `statuses`, `vulnerability-alerts` — contains **no `variables` entry at any level**. There is structurally no way to grant the default `GITHUB_TOKEN` the ability to write a repository Actions variable, regardless of how the `permissions:` block is configured. The REST API's own documentation additionally confirms a classic PAT would need the full, broad `repo` scope for this endpoint. Widening this job's `permissions:` block was therefore not a viable option (it would not even work), and the actual minimum privilege capable of performing this write is a fine-grained Personal Access Token scoped ONLY to "Variables: write" on this one repository.

`[ENGINEERING RECOMMENDATION]` Per this step's own explicit instruction not to create secrets or silently accept an excessive permission escalation, this is surfaced as an **optional, disclosed, human-configured** secret, `GH_VARIABLES_WRITE_TOKEN` — never created by this implementation. The recording step attempts `gh variable set RENDER_LAST_KNOWN_GOOD_SHA --body "$(git rev-parse HEAD)"` only if that secret is present; if absent, it fails closed (logs the exact manual command an operator can run themselves, with their own repo-admin credentials, and continues without failing the job) rather than guessing, printing the token, or claiming a recording that did not happen. Workflow-level `permissions:` remains `contents: read`, unchanged.

### 12.3 Rollback workflow

`[ENGINEERING RECOMMENDATION]` A separate file, `.github/workflows/rollback.yml`, triggered **only** by `workflow_dispatch` — never `push`, `pull_request`, `schedule`, or `workflow_run` — since rollback is an operator-initiated action, not a CI gate, and must never share `ci.yml`'s push-triggered chain. One required-but-optional input, `target_sha` (`required: false`, `default: ""`): an explicit value always wins; an empty value falls back to `vars.RENDER_LAST_KNOWN_GOOD_SHA`. If neither is available, resolution fails closed before any git or Render action is taken.

### 12.4 Target SHA validation

`[ENGINEERING RECOMMENDATION]` `scripts/rollback_target.py`, standard-library-only, reusing (never redefining) `build_release_manifest.REPO_ROOT`. Validation runs in strict order, raising `RollbackTargetError` on the first failure: (1) exactly 40 lowercase hexadecimal characters; (2) a real commit object in this repository (`git cat-file -e <sha>^{commit}`); (3) reachable from the triggering branch's history (`git merge-base --is-ancestor <sha> HEAD`) — rejecting a syntactically valid but foreign, unmerged, or unrelated SHA. No arbitrary, unvalidated input is ever accepted.

### 12.5 Release manifest validation

`[ENGINEERING RECOMMENDATION]` The validated target commit is checked out first (`git checkout <target_sha>`); `scripts/build_release_manifest.py` — the same, unmodified Step 22.4 script, never a second manifest format — is then run against that checked-out tree, and its own `release_id` is cross-checked against `target_sha` before any deploy hook is called.

### 12.6 Backend/frontend consistency

`[ENGINEERING RECOMMENDATION]` Both of Step 22.6's existing secrets are reused unchanged (`RENDER_BACKEND_DEPLOY_HOOK_URL`, `RENDER_FRONTEND_DEPLOY_HOOK_URL`) — no new hook secret is created. A pre-flight step verifies **both** are configured before either is called; if either is absent, the workflow fails closed before attempting any deployment at all (never a partial deploy caused by missing configuration). When both are present, each deploy-hook call uses the identical `ref=<target_sha>` value, so both services are always targeted at the same commit.

### 12.7 Partial failure behavior

`[ENGINEERING RECOMMENDATION]` Both deploy-hook steps use `continue-on-error: true` so both are always attempted regardless of the other's outcome, and their `steps.<id>.outcome` (the true pre-override result) is compared afterward. If the two outcomes differ, the workflow fails loudly, names both outcomes explicitly, and states that the two production services are now inconsistent — it never retries and never performs an automatic corrective second deployment; manual investigation is required.

### 12.8 Post-rollback verification and its limitation

`[ENGINEERING RECOMMENDATION]` Reuses `scripts/staging_smoke_test.py` completely unmodified (the same Step 22.5/22.6 script) against `vars.RENDER_BACKEND_PRODUCTION_URL`/`vars.RENDER_FRONTEND_PRODUCTION_URL`, run only if both rollback deploys succeeded. **Disclosed limitation**: `GET /health` (`src/api/schemas.py::HealthResponse`, Phase 17, unchanged) carries no git-commit field, so a passing smoke test proves the service is alive and answers its documented contract — it does **not** independently prove the exact deployed commit is `target_sha`. That would require either trusting Render's own `ref=` deploy-hook mechanism, or a Render API call this project holds no credential for. The manifest-validation step (12.5) is the strongest verification available before triggering the deploy; the smoke test verifies liveness only, afterward.

### 12.9 Live rollback testing — deferred

`[DEFERRED]` This workflow cannot be exercised end-to-end against a real Render service until Step 22.6's own production deployment has succeeded at least once — as of this writing, no live production deployment has occurred and no deployment credentials are configured (Step 22.6's own report). Validation to date is structural (`tests/test_phase_22_rollback.py`) and unit-level (`scripts/rollback_target.py` against this repository's own real git history) only — never against a live Render endpoint. `[ASSUMPTION]`, unresolved: whether Render's `ref=` deploy-hook parameter correctly handles rolling **backward** to an older commit than what is currently deployed was not verified live this session (only its documented existence and forward-deploy behavior were confirmed in Step 22.6).
