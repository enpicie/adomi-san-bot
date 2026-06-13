# General Coding Standard

*Stack-agnostic. Applies to every line of application code in every project.*
*Pair with: General Platform Spec + General API Standard + a stack spec + an app spec.*

---

## 1. Purpose

This spec encodes the code-level principles every project follows. The General Platform Spec defines what a project *contains*; this spec defines how code *inside* it is written. Claude Code applies every rule here as a non-negotiable default and bakes the CLAUDE.md block in Section 12 into every project on init.

---

## 2. Naming — Purpose Over Mechanism

Names describe **what something is for**, not how it works or what type it is.

- Functions are verbs describing the outcome: `expandSpark()`, not `processData()`. Booleans read as assertions: `isExpired`, `hasAccess`, `canRetry`.
- Variables describe the content: `unpaidInvoices`, not `list2` or `tempArr`.
- Files and directories are named by domain purpose: `billing/invoice-renderer.ts`, not `utils2/helper.ts`.
- No abbreviations except universally understood ones (`id`, `url`, `db`). No type-encoding prefixes (`strName`, `arrItems`).
- A name that needs a comment to explain it is the wrong name. Rename instead of commenting.
- Grep test: searching the domain term (e.g. "invoice") must surface every file that deals with it.

---

## 3. Single Source of Truth

Every fact lives in exactly one place. Everything else derives from it.

- **Config**: one config module per project reads environment variables, validates them at startup, and exports typed values. Application code imports from the config module — never reads `process.env` (or equivalent) directly.
- **Constants**: magic numbers and strings used more than once are named constants in one location.
- **Types/schemas**: domain types are defined once (shared package or schema file) and imported everywhere — frontend, backend, tests. Validation schemas derive types; types are never hand-duplicated from schemas.
- **Derived values are computed, not stored.** If a value can be calculated from the source of truth, calculate it.
- If changing one fact requires editing more than one file, the SSOT architecture has failed — fix the architecture, not the instance.

---

## 4. DRY — With Judgment

- Extract shared logic when the **knowledge** is duplicated, not merely the text. Two code blocks that look alike but change for different reasons stay separate.
- Rule of three: tolerate a second occurrence; extract on the third.
- Never copy-paste a block and edit it. Extract first, then call.
- Premature abstraction is also a violation — a wrong abstraction is more expensive than duplication. When uncertain, duplicate and leave a `// dedupe candidate` comment.

---

## 5. SOLID — Applied Pragmatically

Applied as design pressure, not ceremony. No interfaces-for-everything, no factory layers for single implementations.

- **Single Responsibility**: a module has one reason to change. If describing a function requires "and", split it.
- **Open/Closed**: extend behavior via new variants/strategies, not by editing stable code with new conditionals. A growing `switch` on type is the signal.
- **Liskov**: any implementation of a contract is substitutable — no implementation that throws "not supported" for part of the contract.
- **Interface Segregation**: consumers depend only on what they use. Accept narrow parameter types (the fields needed), not whole objects.
- **Dependency Inversion**: business logic depends on abstractions for I/O (db, http, clock, random). Concrete clients are injected at the edge — this is what makes logic testable.

---

## 6. Function and Module Design

- Functions do one thing. Target under ~40 lines; hard ceiling at one screen. Extract when a block needs a comment to explain *what* it does.
- Max 3–4 positional parameters; beyond that, a named options object.
- No boolean flag parameters that switch behavior — split into two functions.
- Early returns over nested conditionals. Max nesting depth: 3.
- No side effects hidden in getters or functions named as queries. Commands mutate, queries return — never both.
- Module boundaries follow the domain, not the framework: `billing/`, `sparks/` — not a giant `utils/`, `helpers/`, or `managers/`.

---

## 7. Error Handling

- Errors are handled at the boundary (route handler, job entry, UI action) — not swallowed mid-stack.
- Never catch-and-ignore. Every catch either recovers meaningfully, adds context and rethrows, or logs via the structured logger and returns a defined failure state.
- Expected failures (validation, not-found, conflict) are modeled as values/result types or typed errors — not generic `throw new Error(string)`.
- Error messages state what failed, with which inputs (never secrets), and what the caller can do.
- User-facing error text never exposes internals (stack traces, SQL, internal IDs).

---

## 8. Secure Secrets and Sensitive Data in Code

Extends the Platform Spec rule "never hardcode secrets" to code-level behavior:

- Secrets enter only through the config module (Section 3). No secret literal ever appears in code, comments, tests, fixtures, or committed files.
- Secrets are never logged, never included in error messages, never serialized into responses or analytics events. The structured logger redacts known secret keys.
- Test code uses obviously fake values (`test-key-not-real`) — never real or realistic credentials.
- Client-delivered code (frontend bundles) contains only keys explicitly designed to be public (anon/publishable keys). Anything else is a server concern — route it through the backend.
- PII is logged only as opaque IDs, never as raw values (emails, names, content).

---

## 9. Documentation Generation

Documentation is generated and maintained as part of the work, never as a separate later task.

- **Public contracts get doc comments** (TSDoc/docstrings): every exported function, type, and module states purpose, params, return, and failure modes. Internal helpers need doc comments only when non-obvious.
- **Comments explain why, not what.** `// retry: provider rate-limits burst writes` — never narrating the code.
- **Generated reference docs**: if the stack has a doc generator (TypeDoc, Sphinx, etc.), wire it to a `make docs` target on init.
- **Decision docs**: any non-obvious architectural choice made during feature work gets an ADR in `docs/decisions/` per the Platform Spec format — in the same PR as the change.
- **`docs/` learning files** (per Platform Spec) are updated whenever a pattern they describe changes. Stale docs are bugs.

---

## 10. Testing Standard

- Every behavior with branching logic has tests. Pure logic is unit-tested; boundaries (routes, db access) get integration tests against the contract.
- Tests assert behavior and contracts, not implementation details — refactors that preserve behavior must not break tests.
- Test names state the scenario and expectation: `rejects expired token with 401`.
- No test depends on execution order, real time, real network, or shared mutable state. Inject clock/random/IO per Section 5.
- `make test` runs the full suite and is the same command CI runs. A feature is not complete until its tests pass locally via `make test`.

---

## 11. Dependencies and Git Hygiene

- Adding a dependency is an architectural decision: prefer the platform/stdlib, then existing deps, then a new dep — recorded with one line of rationale in the PR (ADR if significant).
- Lockfiles are always committed. Versions are pinned or range-constrained per stack spec.
- Commits follow Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`) with imperative subject lines. Branches: `feature/`, `fix/`, `chore/` per Platform Spec.
- No commented-out code committed — delete it; git history is the archive.
- No `TODO` without an owner or issue reference.

---

## 12. CLAUDE.md Block — Installed on Init

On init (or first application to an existing repo), Claude Code adds this section to `CLAUDE.md`:

```markdown
## Coding Standards
Source: spec-coding-general v1.0

### Always Active
- Names describe purpose: verbs for functions, assertions for booleans, domain terms for files
- One source of truth: config module only (never raw env access), shared types, named constants
- Extract on third duplication; never copy-paste-edit
- One responsibility per module; inject I/O dependencies; no hidden side effects
- Errors handled at boundaries; no swallowed catches; expected failures are typed
- Secrets only via config module; never logged, never in tests, never client-side
- Doc comments on all exported contracts; comments explain why, not what
- ADR in the same PR for any non-obvious architectural choice
- Tests assert behavior; make test passes before any feature is complete
- Conventional Commits; no commented-out code; no ownerless TODOs
```

---

## 13. Anti-Patterns — Never Do These

- **Never read environment variables outside the config module.**
- **Never name by mechanism or type** (`data`, `info`, `helper`, `Manager`, `utils2`).
- **Never duplicate a type definition that exists in the shared types location.**
- **Never silence an error without logging and a defined fallback.**
- **Never put business logic in route handlers, UI components, or migrations** — handlers orchestrate, logic lives in domain modules.
- **Never write a comment that restates the code.**
- **Never commit code whose tests you did not run.**
- **Never introduce an abstraction for a single caller** "in case we need it."

---

## 14. Audit Mode

When applied to an existing repository, include in `.platform/audit.md` (per Platform Spec Section 11): raw env access outside config, duplicated types/constants, modules violating SRP, swallowed errors, secret-handling violations, undocumented exports, and untested branching logic — each with file references and proposed remediation.

---

*General Coding Standard — v1.0*
*Pair with: General Platform Spec + General API Standard + stack spec + app spec.*
