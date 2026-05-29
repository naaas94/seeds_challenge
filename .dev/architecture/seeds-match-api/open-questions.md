Section:      open-questions
Version:      1.0.0
Last updated: 2026-05-28

```
Question:     Should blocking LLM invoke run off the event loop (asyncio.to_thread / ainvoke) given async FastAPI routes?
Impact:       app/main.py, app/agent/loop.py — latency under concurrent requests; spec mentions to_thread but implementation awaits sync invoke directly
Closes when:  Team accepts blocking-in-async for demo scope OR implements thread pool / async invoke with tests updated
```

```
Question:     Is empty-string OPENAI_API_KEY a supported failure mode at lifespan (RuntimeError) or only missing-key ValidationError at import?
Impact:       app/config.py, app/main.py lifespan, tests — T6/T8 changelog notes gap on empty-string falsifier
Closes when:  Explicit test + documented expected behavior, or field constrained to reject empty strings in Settings
```

```
Question:     Production memory backend (Redis vs other) and session TTL when moving beyond single-worker demo
Impact:       app/memory/store.py, Dockerfile worker count, deployment topology
Closes when:  Backend chosen and ConversationStore interface reimplemented with migration plan
```

```
Question:     Pin dependency versions in requirements.txt for reproducible builds?
Impact:       dependency-graph.md external table, CI, Docker builds
Closes when:  Policy decision recorded and requirements locked or lockfile adopted
```

none at this time — additional unresolved architectural forks pending user input (2026-05-28)
