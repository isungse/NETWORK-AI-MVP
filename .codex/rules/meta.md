# Documentation Governance Principles

## 1. Route content to the correct file based on its nature

- Design decisions -> `design-system.md`
- Code patterns -> `code-style.md`
- Architecture decisions -> `architecture.md`
- Operational or workflow rules -> `workflow.md`
- Documentation governance rules -> `.codex/rules/meta.md`

## 2. No duplication

- If content belongs in one file, write it only there.
- Other files must reference or link to that source instead of repeating the same content.

## 3. Write at a durable abstraction level

- Keep rules, decisions, conventions, and patterns that remain valid over time.
- Omit one-off events, temporary notes, session-specific details, and task execution logs.

## 4. Split large documentation updates

- If an update would significantly expand an existing file, stop and propose creating a new focused file before writing.
- Explain the proposed filename, purpose, and relationship to existing documents.

## 5. `AGENTS.md` is a top-level index only

- Keep `AGENTS.md` as a concise navigation and reference file.
- Do not add detailed rules, implementation notes, design explanations, or long-form documentation directly to `AGENTS.md`.
- Place detailed content in the appropriate documentation file and reference it from `AGENTS.md`.
