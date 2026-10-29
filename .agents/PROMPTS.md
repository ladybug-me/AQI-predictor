# Optimized Invocation Prompts for Agent Skills
*Engineered using [prompt-master/SKILL.md](file:///home/ladybug-me/health-alert-system/prompt-master/SKILL.md) for Antigravity IDE.*

---

### Prompt 1: Documentation Audit & Drift Detection

```markdown
## Objective
Run a comprehensive, read-only documentation drift audit across this repository by activating the docs-sync-audit skill.

## Context
- Repository: Vellore Health Alert System codebase
- Active skill: .agents/skills/docs-sync-audit/SKILL.md
- Baseline verification script: .agents/skills/docs-sync-audit/scripts/docs_drift.py

## Target State
A structured audit report identifying confirmed and inferred documentation drift across README, guides, API surfaces, and configuration files, ranked by P0-P3 severity.

## Scope
- Work only in: read-only inspection of repository files and documentation.
- Do NOT touch: do not modify, create, or delete any source code, configs, or documentation during the audit.

## Constraints
- MUST activate and adhere strictly to .agents/skills/docs-sync-audit/SKILL.md.
- MUST run `python .agents/skills/docs-sync-audit/scripts/docs_drift.py` for automated baseline drift metrics.
- Every reported finding MUST cite concrete evidence with line-exact references: source `<path>:<line>` and docs `<path>:<line>`.
- MUST use P0-P3 severity classification.
- If uncertain about any claim, state [uncertain].

## Acceptance Criteria
- [ ] Automated drift script executed and reported under Checks Run.
- [ ] Every finding grounded with verified `<path>:<line>` citations.
- [ ] P0-P3 severity tags assigned to all findings.
- [ ] No repository files modified (read-only audit invariant).

## Action Boundaries
- Inspect repository files and execute read-only verification scripts autonomously.
- Stop and ask before modifying any files or applying recommended fixes.

## Progress Evidence
Ground completion claims in tool execution outputs from docs_drift.py and inspected line references.
```

🎯 Target: Antigravity IDE (Gemini 3 Pro)
💡 Optimized with Template M structure, strict read-only scope lock, and line-exact evidence requirements to eliminate hallucinated documentation citations.

> [!WARNING]
> This prompt is for an agentic tool with real system access. Review the scope locks, forbidden actions, and stop conditions before pasting. Confirm file paths, directories, and permissions match the actual project.

---

### Prompt 2: Intentional Product UI Craftsmanship (Anti-UI-Slop)

```markdown
## Objective
Design and implement a product-specific, intentional interface for the Health Alert System adhering strictly to the anti-ui-slop skill and playbooks.

## Context
- Active skill: .agents/skills/anti-ui-slop/SKILL.md
- Project domain: Vellore Air Quality & Health Alert System
- Reference playbook: .agents/skills/anti-ui-slop/reference/new-work.md (or operate.md for dashboards)

## Target State
A clean, grounded interface extending the product's actual data model, workflows, and local tokens without generic boilerplate or visual slop.

## Scope
- Work only in: designated frontend source directories (e.g., `src/`, `components/`, `styles/`, or root HTML/CSS/JS).
- Do NOT touch: backend infrastructure or database configurations without approval.

## Constraints
- MUST activate and strictly adhere to .agents/skills/anti-ui-slop/SKILL.md.
- NEVER produce generic, template-cloned, unopinionated, or superficial UI slop.
- MUST select at most ONE reference playbook from `reference/` (do NOT load multiple playbooks).
- MUST implement complete UI states: loading, empty, error, success, disabled, and recovery when applicable.
- Familiar interaction conventions must remain familiar; distinction comes from data structure, hierarchy, typography, and clear workflows.
- MUST execute a hard finish gate: verify rendered UI at 375px and 1440px viewports, eliminating clipping, overflow, contrast issues, or inert controls.

## Acceptance Criteria
- [ ] Product-specific interface implemented without AI-generated visual slop.
- [ ] Exactly one playbook referenced and applied.
- [ ] All essential component states covered (empty, error, loading, interactive).
- [ ] Hard finish gate completed across mobile and desktop viewports.

## Action Boundaries
- Create and edit frontend files autonomously within the scope.
- Ask before installing unapproved external packages or introducing breaking changes.

## Progress Evidence
Ground all UI additions in verified component code and finish-gate inspection results.
```

🎯 Target: Antigravity IDE (Gemini 3 Pro)
💡 Formulated to enforce product-grounded design, single-playbook focus, complete state handling, and finish-gate validation while blocking generic UI slop.

> [!WARNING]
> This prompt is for an agentic tool with real system access. Review the scope locks, forbidden actions, and stop conditions before pasting. Confirm file paths, directories, and permissions match the actual project.

---

### Prompt 3: Project README Generation

```markdown
## Objective
Perform a full codebase inspection of the Health Alert System and generate a comprehensive, appealing, senior-engineer-level README.md.

## Context
- Active skill: .agents/skills/create-readme/SKILL.md
- Workspace: Vellore Health Alert System repository
- Reference style: High-standard open-source documentation (Azure samples, sinedied patterns)

## Target State
A complete, structured `README.md` at the workspace root covering project purpose, architecture overview, prerequisites, setup instructions, configuration, and usage guide.

## Scope
- Target file: `README.md` at workspace root.
- Do NOT touch: codebase implementation logic or configuration files.

## Constraints
- MUST activate and strictly adhere to .agents/skills/create-readme/SKILL.md.
- MUST inspect workspace files and dependencies before writing to ensure complete factual accuracy.
- Maintain a concise, high-signal tone without emoji overuse.
- Structure must include: Overview, Key Features, Architecture/Data Flow, Prerequisites, Installation & Setup, Environment Variables, and Verification/Testing.
- Base claims strictly on verifiable workspace code; never extrapolate unbuilt features.

## Acceptance Criteria
- [ ] Workspace inspected prior to drafting.
- [ ] Concise, informative structure without emoji spam.
- [ ] Installation commands and environment variables match active codebase.
- [ ] Clean markdown links and formatted code blocks throughout.

## Action Boundaries
- Inspect workspace and write the root `README.md` autonomously.
- Stop and ask before modifying any files other than `README.md`.
```

🎯 Target: Antigravity IDE (Gemini 3 Pro)
💡 Tuned with full workspace grounding and senior open-source standards to prevent boilerplate README outputs.

> [!WARNING]
> This prompt is for an agentic tool with real system access. Review the scope locks, forbidden actions, and stop conditions before pasting. Confirm file paths, directories, and permissions match the actual project.
