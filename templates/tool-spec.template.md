# Tool Spec — <tool_name>

> One per tool. A good spec reads like a docstring written for a new hire:
> implicit context made explicit, no ambiguity.

## Name & namespace
- **Name:** `<service_resource_action>`  (e.g., `asana_projects_search`)
- **Why this namespace:** <how it disambiguates from sibling tools>

## Purpose (1–2 sentences)
<What real task this enables. Consolidates which underlying operations?>

## When to use vs. when NOT to
- **Use when:** <…>
- **Do NOT use when:** <point to the sibling tool that fits instead>

## Inputs
| Param | Type | Required | Description | Guardrail (poka-yoke) |
|---|---|---|---|---|
| `<id>` | string | yes | <unambiguous; e.g., `user_id` not `user`> | <e.g., must be absolute path / enum> |

- **Strict schema:** <JSON schema or equivalent; reject unknown fields>

## Output
- **Shape:** <fields returned — high-signal, human-legible; avoid raw UUIDs/mime>
- **Verbosity control:** `response_format`: `concise` | `detailed` (default: `<…>`)
- **Token bound:** <max tokens; pagination/filter/truncation defaults>
- **Example (concise):**
```json
<small example>
```

## Errors (actionable)
| Condition | Message returned to the agent |
|---|---|
| <invalid input> | `<states the exact fix, e.g., "date must be YYYY-MM-DD">` |
| <not found> | `<what to try instead>` |
| <rate/limit> | `<how to back off or paginate>` |

## Side-effect class
- [ ] **read** (no state change)
- [ ] **write** (reversible state change)
- [ ] **destructive/irreversible**  → requires <approval gate / HITL>

## Privilege & sandboxing
- **Scope:** <least-privilege credentials/permissions this tool needs>
- **Sandbox:** <isolation for any code/network/file access>

## Test cases (for the tool eval)
1. <realistic task that should call this tool, with expected outcome>
2. <edge case / common mistake to verify the error message helps>
