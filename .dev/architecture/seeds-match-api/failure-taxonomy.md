Section:      failure-taxonomy
Version:      1.0.0
Last updated: 2026-05-28

Taxonomy version: 1.0.0
Last updated:     2026-05-28

## Layer framework

```
L0  Input integrity   — failures attributable to input data before any processing begins
L2  Model behavior    — failures in model output relative to the prompt
L3  Output validation — failures in structural or semantic validity of output
L5  Infrastructure    — failures in external systems or environment
```

[none at this time — fill per project via addition protocol during user interview]

**Observed failure handling in code (not yet registered as cause classes):**

- Missing `OPENAI_API_KEY` → pydantic `ValidationError` at import (L5)
- Agent/tool unhandled exception in route → HTTP 500 with `Agent execution failed` (L5/L2)
- Unknown `conversation_id` on GET → HTTP 404 (L0 client id)
- Invalid/missing Yahoo ticker → tool returns user-facing string, loop continues (L0/L5)
- `MAX_ITERATIONS` exhausted → fixed fallback string reply (L2/L3)
