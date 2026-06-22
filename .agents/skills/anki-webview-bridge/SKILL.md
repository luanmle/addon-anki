---
name: anki-webview-bridge
description: Use this skill when injecting CSS or JavaScript into Anki webviews, registering assets with setWebExports, implementing a pycmd JS-to-Python message bridge, or sanitizing HTML inserted into reviewer, editor, or deck browser; for lifecycle hook wiring use anki-hooks-integrator.
---

# Anki WebView Bridge

## Goal

Integrate JavaScript and web assets with Anki webviews through documented hooks and a secure, version-aware bridge.

## Workflow

1. Identify the exact webview context and lifecycle event.
2. Verify the relevant hooks and their callback signatures.
3. Register packaged web assets with verified `setWebExports()` usage.
4. Inject CSS/JS only into intended contexts.
5. Prefix every JS→Python command with an add-on-specific namespace.
6. Parse and validate message payloads before dispatch.
7. Return the correct hook/filter values according to the verified signature.
8. Treat JavaScript evaluation as asynchronous unless the verified API proves otherwise.
9. Escape or sanitize user/remote content before inserting HTML.
10. Test question, answer, preview, editor, night mode, and repeated navigation when applicable.

## Message protocol

Prefer a versioned JSON payload carried under a unique prefix:

```text
my_addon:v1:{"type":"open_item","item_id":123}
```

Dispatcher requirements:

- reject messages without the prefix;
- enforce a size limit;
- parse JSON with error handling;
- allowlist message types;
- validate field types and identifiers;
- never evaluate payload content as code.

## Asset rules

- Keep source assets inside the add-on package.
- Export the narrowest path/extension pattern possible.
- Avoid remote script execution and inline secrets.
- Scope CSS selectors to an add-on root class to reduce conflicts.

## Constraints

- Do not assume a DOM node exists when a reviewer hook fires; confirm lifecycle timing.
- Do not override Anki's global `pycmd` protocol or consume unrelated messages.
- Do not use unverified private webview methods.
- Do not concatenate untrusted values into HTML or JavaScript source.
