# Documentation Governance

## 1. Route Content to the Correct File

Route documentation based on its nature:

- Design decisions → `design-system.md`
- Code patterns → `code-style.md`
- Architecture decisions → [`architecture.md`](architecture.md)
- Operational or workflow rules → [`workflow.md`](workflow.md)
- Documentation governance rules → [`meta.md`](meta.md)

Rule filenames are resolved relative to `.codex/rules/`. Create a focused rule file before placing detailed content elsewhere when the routed file does not yet exist.

## 2. No Duplication

If content belongs in one file, write it only there. Other files must reference or link to that source instead of repeating the same content. Update the canonical source and its references in the same commit when a rule or workflow changes.

## 3. Write at a Durable Abstraction Level

Keep rules, decisions, conventions, and patterns that remain valid over time. Omit one-off events, temporary notes, session-specific details, task execution logs, deployment IDs, process IDs, and transient verification output.

## 4. Split Large Documentation Updates

If an update would significantly expand an existing file, stop and propose creating a new focused file before writing. Explain the proposed filename, purpose, and relationship to existing documents.

## 5. AGENTS.md Is a Top-Level Index Only

Keep `AGENTS.md` as a concise navigation and reference file. Do not add detailed rules, implementation notes, design explanations, or long-form documentation directly to `AGENTS.md`. Place detailed content in the appropriate documentation file and reference it from `AGENTS.md`.
