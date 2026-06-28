# Documentation Index

This folder is the source of truth for implementation decisions and operational notes for the Anki Concursos add-on.

## Core documents

- `architecture.md`: system boundaries, sync invariants, storage, and Anki integration principles.
- `installation.md`: user and developer setup.
- `next-session.md`: current handoff, test focus, known gaps, and recommended next blocks.
- `../config.md`: shipped configuration keys and examples.
- `changes/`: implementation log. Every behavior change should add one dated entry.

## Documentation policy

Every implementation change must answer four questions:

1. What changed?
2. Why did it change?
3. How was it verified?
4. What still needs manual testing inside Anki?

Use `changes/TEMPLATE.md` for each new entry.

Update long-lived docs when the implementation changes a durable contract:

- architecture or module boundary;
- config key or default;
- backend endpoint or payload shape;
- local storage schema or migration;
- sync invariant;
- Anki hook, UI entry point, or lifecycle behavior;
- packaging or installation step.

Do not let change entries become the only place where current behavior is described. They are history; long-lived docs describe the current state.
