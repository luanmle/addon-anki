# Change Log Process

This directory stores one file per meaningful implementation change.

## When to add an entry

Add an entry for:

- user-visible behavior changes;
- bug fixes with observable impact;
- sync/import/export changes;
- backend API contract changes;
- local storage, config, auth, or migration changes;
- Anki hook, lifecycle, Qt UI, or background operation changes;
- packaging, install, or release changes;
- test strategy changes that explain important coverage.

No entry is required for pure formatting, comments, typo fixes, or mechanical edits with no behavior or process impact.

## File name

Use:

```text
YYYY-MM-DD-short-slug.md
```

Keep the slug short and stable. Prefer the feature or bug name over ticket numbers.

## Entry content

Copy `TEMPLATE.md` and fill every section. If a section does not apply, write `N/A` and keep the heading.

Each entry must include:

- summary;
- files or modules touched;
- behavior before and after;
- implementation notes;
- tests or checks run;
- manual Anki checks required or completed;
- risks and follow-ups.

## Maintenance

When a change alters durable behavior, update the relevant long-lived doc in the same commit. For example, a new config key updates both the change entry and `../config.md`.
