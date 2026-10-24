# AI CODING AGENT INSTRUCTIONS

You are a principal engineer, AI researcher, product designer, QA lead and hackathon storyteller. Produce a COMPLETE runnable application, not a landing page or fake demo. Start with an implementation plan, then implement a thin end-to-end P0 vertical slice and test it before P1/P2. Keep no fake model responses in production. Synthetic demonstration inputs are allowed but must be explicitly labelled.

This is for Hacktoberfest 2026 Week 3 “Slow and Steady”: solve an actual repetitive burden and clearly prove the lazy payoff. Build local-first using non-Gemma open-weight AI (e.g. appropriately licensed Qwen via Ollama). Local AI is core, not a decorative API call. Validate tool availability, model license, and specs before writing code. Never submit to the Gemma category.

Frontend: Next.js, TypeScript, Tailwind CSS, shadcn/ui, accessible responsive polished UI. Backend: Python FastAPI, typed Pydantic schema, SQLite/SQLAlchemy as appropriate. Docker Compose if feasible, plus easy manual local instructions. Ensure robust validation, privacy, visible model-status indicator, progress/error feedback, proper tests and README. No unnecessary paid/cloud dependency.

# PROJECT: CareRelay — The Family Care Coordination Assistant

## Story, problem and product
Four relatives all want to help; an appointment shift gets buried in a group chat and no one books transport. Create a consent-based family COORDINATION assistant, not a medical advisor. It turns scattered messages into a shared approved plan with human accountability.

## Genuine P0 journey
1. Create a fictional care circle and four caregiver profiles with specified availability. 2. Paste or upload synthetic text messages, appointments and notes. 3. Local non-Gemma Qwen identifies tasks/events (transport, errands, appointment confirmation, pick-ups), due time, owner if specified, location, uncertainty, source quote. 4. Validate quotes and timestamps; show approve/edit/reject queue. 5. Approved items feed shared responsibility board and week/day calendar. 6. Highlight unassigned travel tasks and conflicting schedules. 7. Generate evidence-linked day brief and handoff message that distinguishes verified from unresolved; human approves before sharing. No automatic external sending.

## Architecture and UI
Next.js + FastAPI + SQLite + SQLAlchemy + local Ollama Qwen, optional embeddings and faster-whisper P2. Models: CareCircle, Caregiver, Availability, SourceMessage, Evidence, CareTask, Appointment, Assignment, Consent, MessageDraft, AuditEvent. Pages: Home, Import Inbox, Review Queue, Calendar, Responsibility Board, Handoffs, Availability, Privacy/Permissions. Clear statuses suggested, confirmed, needs clarification, cancelled, done.

## Guardrails
No diagnosis, dosing, treatment suggestions or invented medication adherence. Appointment reminders are organizational only. No sensitive information in public demos. Granular permission checks and audit logging; household membership does not automatically confer universal access. Do not assign responsibilities without consent; uncertainties remain visible. Change propagation must track cancelled/rescheduled tasks.

## Demo and tests
Generate fictional 2-week dataset, four caregivers, 30+ messages, appointments, errands, conflicting availability, at least 10 seeded coordination problems, explicit expected labels. Test extraction precision/recall, attribution, date disambiguation, rescheduling and duplicate handling, conflicts, permission boundaries, AI briefing factuality and Playwright end-to-end journey. Demo: rescheduled appointment, unassigned transportation, approved handoff plan.

## Story-specific article and video hook
Suggested title: “Everyone Wanted to Help. Nobody Had the Whole Plan.” Human impact is less confusion, not questionable promises of improved health outcomes. Distinguish seeded demo from live trials.


# MANDATORY SUBMISSION AND PUBLICATION PIPELINE

These requirements are non-optional for the finished project, with explicit user approval at every external publishing step. No automatic account selection, no fabricated assets or measurements. Build and test the working application before running this pipeline. Never use Gemma models or target the Gemma prize category.

## A. Verify the finished application
- Run backend and frontend, end-to-end Playwright tests, tests of the real open-weight AI pipeline, and the seeded demonstration.
- Produce reproducible evaluation measurements and distinguish measured data from examples. Preserve privacy and do not commit credentials, confidential datasets, or `.env` files.
- Prepare README.md, LICENSE, .env.example, docs/ARCHITECTURE.md, docs/EVALUATION.md, docs/DEMO_SCRIPT.md, docs/DEV_SUBMISSION.md, docs/PUBLISHING_CHECKLIST.md, and demo/assets/{screenshots,video,audio}/.
- Record evidence: actual screenshots, model and version, how to run locally, genuine limitations, and tested claims.

## B. GitHub account selection (MANDATORY CHECKPOINT)
- Regardless of which GitHub user is already signed in using gh, git, SSH, browser, environment variables, or stored tokens, NEVER silently pick that account or organization.
- Ask the user: **“Which GitHub username or organization should I publish this project under, and should the repository be public?”**
- Stop before any repository creation, remote changes, push, or publication until the user answers. Check authorization and existing remote. Do not overwrite an existing remote or repository without explicit approval.
- Inspect files for sensitive information. Confirm destination and then push only after permission. Verify returned GitHub URL/branch.
- Create a polished README, screenshots, reproducible setup, architecture diagram, and working examples. Use screenshots from the actual running application, never fabricated UI screenshots.
- Host screenshots in the chosen GitHub repository; use working stable URLs (prefer `raw.githubusercontent.com/ACCOUNT/REPO/COMMIT_SHA/...`) and verify each URL when possible.

## C. Playwright demonstration recording
- Once application is functional, automate the full user journey with Playwright (a real browser, real backend, real model inference, synthetic/private-safe data). Record a 16:9, ideally 1920x1080, approximately 90–150-second video with readable interactions and enough pauses to follow the story.
- Show protagonist/problem, original effort, import/input, open-source AI processing, real resulting action, approval/safety and measurable or reproducible payoff.
- Save the reproducible recording script as `demo/record_demo.ts` (or `.py`), silent video as `demo/assets/video/demo_silent.mp4`, and screenshots under `demo/assets/screenshots/`.
- Convert recorded WebM via FFmpeg if needed. Verify the file plays. Give the user the EXACT local file path or real available download link; do not claim completion if unsupported.

## D. Kokoro-82M narrated video (MANDATORY CHECKPOINT)
- Once the silent demo exists, draft a distinctive professional narration script and save it in `demo/assets/audio/narration_script.md`.
- Inspect the installed Kokoro-82M configuration and REAL supported voices; then ask the user: **“Which Kokoro-82M voice should narrate the demo? Here are the available voices: ...”** Offer previews where possible. Do not select a final voice without user input.
- Following voice choice, synthesize with genuine Kokoro-82M, not a substituted service. Save `demo/assets/audio/kokoro_voiceover.wav`; time-align with footage using FFmpeg, write `demo/assets/audio/subtitles.srt`, and export `demo/assets/video/final_demo.mp4`.
- Verify narration, subtitles, synchronisation, and file existence. Provide the precise video path to user.

## E. YouTube handoff (MANDATORY CHECKPOINT)
- Do NOT automatically choose a YouTube account or upload the video. Ask user to upload `final_demo.mp4` as Public or Unlisted and return the actual YouTube URL.
- Do not invent video links. Once user supplies it, verify the usable video ID and embed it inside DEV Markdown with `{% youtube ACTUAL_VIDEO_ID %}`.
- If user does not provide a URL, save a clearly marked pending draft; do not claim final submission is ready.

## F. Create highest-quality DEV Challenge post
- Create a polished, original, specific, compelling post based on the actual implementation. Start from a human protagonist and a concrete avoidable burden; use a real before/after demonstration, measured outcomes (when available), architectural details, tradeoffs, safety, limits, technical substance, and an emotionally resonant ending. Aim around 1,500–2,300 meaningful words when warranted, avoiding filler and marketing exaggerations.
- Embed at least four actual screenshots when useful, hosted on the selected public GitHub repo, including hero screen, input/problem, processing/evidence, and completed outcome. Verify URLs. Include actual repo link and actual YouTube embed. Use DEV-supported embeds only; never invent a DevRelay session.
- Use the required challenge template EXACTLY in this order (optional sections may be omitted if unsupported):

  *This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19)*

  ## What I Built
  <!-- What does it do, and what effort does it save? Who gets to be a little lazier because of it? -->

  ## Demo
  <!-- Share a deployed link or a video demo. -->

  ## Code
  <!-- Show us the code! You can embed a GitHub repo directly into your post. -->

  ## How I Built It
  <!-- Which open-source AI did you use (open-weight models, agent harnesses, frameworks, local inference), and how is your project built around it? -->

  ## Why Does Open Innovation Matter?
  <!-- Why does open innovation matter for what you built? What did it make possible that a closed API wouldn't? -->

  ## My Agent Session
  <!-- Optional: include genuine publicly shareable DevRelay agent-session embed or link, otherwise omit. -->

  ## The Lazy Payoff
  <!-- Optional: report only evidenced time/effort reduction or explicitly labeled synthetic demonstrations; remove if unsupported. -->

  ## Prize Categories
  <!-- Include only verified eligible categories matching REAL implemented integrations; exclude Gemma. -->

- Include selected DEV tags and a compelling title outside the body. Write the complete ready-to-paste article in `docs/DEV_SUBMISSION.md` and display its ENTIRE Markdown content in chat, with no invented links or placeholders in the FINAL version.
- Finalize only after authentic GitHub account selection and verified push, actual screenshots hosted, Playwright video recorded, voice selected, Kokoro narration generated, user-supplied YouTube URL embedded, and article reviewed by user. Never automatically publish the DEV article. If the challenge deadline makes finishing everything impossible, prioritize tested application + repository and transparently state remaining steps; do not bypass approvals.
