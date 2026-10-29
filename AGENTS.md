# Workspace Skill Enforcement Rules

## 1. PRIMACY ZONE — Mandatory Skill Activation Invariants

When operating in this workspace, you MUST strictly adhere to the following skill-binding invariants. You MUST NOT bypass or substitute these skills with generic heuristics. Before writing code or taking action for matching tasks, you MUST read the corresponding `SKILL.md` using `view_file`.

| Domain | Trigger Condition | Mandatory Skill |
| :--- | :--- | :--- |
| **Documentation Audits & Drift** | Auditing docs, checking doc freshness, verifying API/code alignment, drift detection, PR docs review | [.agents/skills/docs-sync-audit/SKILL.md](file:///home/ladybug-me/health-alert-system/.agents/skills/docs-sync-audit/SKILL.md) |
| **Frontend UI & Web Development** | Designing, implementing, redesigning, styling, or reviewing web or mobile interfaces, UI components, HTML/CSS/JS, anti-ui-slop | [.agents/skills/anti-ui-slop/SKILL.md](file:///home/ladybug-me/health-alert-system/.agents/skills/anti-ui-slop/SKILL.md) |
| **README Creation & Updates** | Writing, updating, restructuring, or generating `README.md` | [.agents/skills/create-readme/SKILL.md](file:///home/ladybug-me/health-alert-system/.agents/skills/create-readme/SKILL.md) |

---

## 2. Mandatory Domain Specifications

### Domain A: Documentation Audit & Drift Detection
- **Trigger**: Any request to audit documentation, detect docs drift, verify README setup instructions, inspect env/API docs consistency, or review doc coverage.
- **Enforcement Directives**:
  1. **Activate Skill**: You MUST read and follow [.agents/skills/docs-sync-audit/SKILL.md](file:///home/ladybug-me/health-alert-system/.agents/skills/docs-sync-audit/SKILL.md).
  2. **Read-Only Invariant**: The audit phase MUST remain strictly read-only. NEVER edit, generate, or delete documentation files during the audit phase unless the user explicitly requests direct updates.
  3. **Automated Verification**: Run `python .agents/skills/docs-sync-audit/scripts/docs_drift.py` to establish deterministic baseline checks on links, environment variables, and scripts.
  4. **Grounding & Evidence Contract**:
     - Every finding MUST cite verified source line numbers (`<path>:<line>`) and corresponding doc line numbers (`<path>:<line>`).
     - Every finding MUST use the `P0`-`P3` severity rubric.
     - Never report unverified assumptions as facts. If uncertain, state `[uncertain]`.
  5. **Output Contract**: Structure your audit output strictly following the report template specified in `docs-sync-audit/SKILL.md`.

### Domain B: Intentional Product UI Craftsmanship (Anti-UI-Slop)
- **Trigger**: Any request to design, implement, redesign, critique, style, or review frontend interfaces, web dashboards, UI components, HTML/CSS/JS, or mobile/web screens. Trigger keywords include "anti-ui-slop", "stop UI slop", "build UI", "dashboard", "frontend", "redesign".
- **Enforcement Directives**:
  1. **Activate Skill**: You MUST read and follow [.agents/skills/anti-ui-slop/SKILL.md](file:///home/ladybug-me/health-alert-system/.agents/skills/anti-ui-slop/SKILL.md).
  2. **Anti-Slop Invariant**: NEVER output generic, template-cloned, unopinionated, or superficial UI slop. Ground every interface strictly in the actual product brief, local design tokens, components, and real domain requirements.
  3. **Playbook Selection Rule**: Select at most ONE playbook from `reference/` for the task (`new-work.md` for new surfaces/redesigns, `operate.md` for dashboards/tools, `polish.md` for refinement, `distill.md` for simplification, `audit.md` for reviews, `ios.md` for native iOS). Do NOT load multiple playbooks.
  4. **Complete State Coverage**: All generated UI MUST cover necessary states: loading, empty, error, success, disabled, and recovery when they can occur.
  5. **Hard Finish Gate**: Inspect and verify the rendered UI at representative sizes (e.g. 375px mobile, 1440px desktop). Eliminate clipping, overlap, contrast failures, and inert interactions before completing the task.

### Domain C: README Creation & Maintenance
- **Trigger**: Any request to create, rewrite, enhance, or overhaul `README.md`.
- **Enforcement Directives**:
  1. **Activate Skill**: You MUST read and follow [.agents/skills/create-readme/SKILL.md](file:///home/ladybug-me/health-alert-system/.agents/skills/create-readme/SKILL.md).
  2. **Full Workspace Analysis**: You MUST conduct a comprehensive scan of the workspace (file structure, dependencies, APIs, documentation) before formulating the README.
  3. **Structure & Tone**:
     - Maintain the standards of top-tier open-source projects (inspired by reference repositories in `create-readme/SKILL.md`).
     - Structure logically: Title, High-level Architecture, Prerequisites, Quickstart/Installation, Configuration/Environment Variables, Usage, and Verification/Testing.
     - NEVER overuse emojis. Keep tone concise, professional, informative, and authoritative.

---

## 3. Action Boundaries & Safety Lock

- **Autonomous Actions**: Inspection of workspace code, executing read-only scripts, creating/updating approved target files within scope, and running non-destructive test commands.
- **Confirmation Required**: Stop and request user approval before deleting any file, installing external unapproved packages, or making breaking schema/architectural shifts.
