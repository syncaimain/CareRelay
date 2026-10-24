# CareRelay implementation plan

1. Inspect local tooling and model licensing. Use the user-selected Ministral 3 14B through Ollama (Apache 2.0); no Gemma models.
2. Build and test a P0 slice: fictional circle → text import → genuine structured extraction → exact source validation → review → approved board.
3. Add consent-aware assignment, availability conflicts, cancellation/rescheduling, calendar, grounded handoffs, permissions and audit events.
4. Build the accessible Next.js interface and verify the complete browser journey against the real backend/model.
5. Record reproducible evaluation and actual demo assets. Document limitations and manual/Docker setup.
6. Only after the app is verified, request the required GitHub destination, Kokoro voice and YouTube handoff at their respective publication checkpoints in BUILD_PROMPT.md.
7. Add the user-selected Temporal partner integration: persistent service, durable extraction workflows, idempotent commits, bounded retries and real API/worker crash recovery. Preserve human review, consent and private-source boundaries. Verify the integration before claiming Best Use of Temporal.

## Environment inspection

- Windows; Python 3.12.7; Node 22.14.0; Ollama available.
- NVIDIA RTX 4090, 24,564 MiB VRAM.
- User chose `ministral-3:14b`, 9,082,537,546 bytes. Download completed and SHA-256 integrity verification passed. Genuine schema-constrained extraction passed; metadata and result are in `model-verification.json`.
- Upstream: https://ollama.com/library/ministral-3 (Apache 2.0, JSON output support).
- Original prompt's Qwen default is superseded by the user's model selection.
