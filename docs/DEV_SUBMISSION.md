<!-- WORKING DRAFT — NOT READY TO PUBLISH.
Missing: GitHub authentication and verified push,
verified public screenshot links and article review.
No repository/video links or results are invented here.
-->

Title: Everyone Wanted to Help. Nobody Had the Whole Plan.

Tags: devchallenge, hf26challenge, ai, opensource

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19)*

## What I Built

Alex sees the appointment change. Maya sees the request for a ride. Sam assumes someone else has the groceries covered. Robin checks the chat after work and scrolls through yesterday's messages, trying to find which plan is still current.

These are fictional people in CareRelay's synthetic demonstration. The burden they represent is familiar: the work of helping includes a second, repetitive job of remembering who said what, checking what changed, and finding out whether someone actually agreed to help.

CareRelay is a local family coordination prototype. It turns pasted messages into suggested appointments, transport, errands, pickups and confirmation tasks. A person reviews the evidence and approves each item before it reaches the shared plan. A caregiver then accepts their own responsibilities. Those are two different decisions, and the application keeps them separate.

## Demo

{% youtube ylEdw_ICXTU %}

[Watch the complete CareRelay demonstration on YouTube](https://youtu.be/ylEdw_ICXTU).

The demonstration was recorded at 1920×1080 with real local model inference and synthetic family messages. The 108-second export uses Kokoro-82M narration with the `am_fenrir` voice and an English subtitle track. Only the unused closing hold was trimmed; the visible actions and model-processing wait were preserved. The recording script, silent source, narration, captions and final video are included with the project.

The recorded journey follows a clinic appointment change, a proposed driver whose work shift overlaps the journey, and an unassigned return ride. Robin explicitly accepts her own library pickup. The original appointment becomes cancelled when its replacement is approved. The final handoff keeps that accepted commitment separate from the unresolved replacement appointment and its transport question.

Actual screenshots are saved locally as `01-overview.png`, `02-source.png`, `03-evidence.png`, `04-board.png`, `05-reschedule.png`, `06-handoff.png` and `07-calendar.png` under `demo/assets/screenshots/`. Public screenshot embeds will be added only after an authorized repository push provides real stable URLs.

## Code

The local implementation uses Next.js, TypeScript, Tailwind, a shadcn-style button component, FastAPI, Pydantic and SQLite. A repository link will be included only after the user chooses the destination and authorizes publication.

The selected destination is the public repository `syncaimain/CareRelay`; authenticated access and the actual repository push are still pending. This working draft is not a published submission.

## How I Built It

I used Ministral 3 14B through Ollama, an Apache 2.0 open-weight model. The core inference operation produces structured coordination suggestions from actual source text. There is no fake-response fallback in the application.

A typed JSON schema constrains the response, but valid JSON alone is insufficient evidence. The backend checks that every quote is an exact contiguous substring of the imported source and that the source ID matches. A failed evidence check rejects the result before suggestions are written. Interpreted dates carry an explicit review warning. A name in a model result does not constitute consent.

The review queue is deliberately central. The reviewer can correct the title, date, location, proposed owner and unresolved details. Approval places an item on the plan. Acceptance is a separate action reserved for the proposed caregiver, or a volunteer when the task is unassigned.

That distinction changes the familiar task-board interaction. A task can be perfectly understandable and approved while still having nobody committed to doing it. CareRelay displays that gap instead of filling it with a reassuring name. Unclaimed transport gets an explicit warning; the calendar is a view of the approved plan rather than a second independent source of truth.

Availability is intentionally modest. Caregivers record windows when they are unavailable. The conflict check compares proposed tasks against those windows and against each other, using a documented one-hour planning window. It does not pretend to know travel times, appointment duration or whether two nearby errands are realistically compatible. A warning is a reason to check with someone, not a scheduling verdict.

Cancellation and rescheduling retain the original record. A reviewer chooses the original approved item, which is cancelled when its replacement is approved. Acceptance resets for the replacement. Transport remains a separate responsibility; changing an appointment never silently means a driver has accepted a different journey.

Handoffs take a conservative approach to factuality. The local model returns references to supplied approved tasks. The backend validates those references and renders the brief deterministically from approved records, including all relevant tasks to prevent omissions. Private sources never enter a shareable brief. Draft approval records task versions; if the plan changes, the user must generate a fresh handoff.

I deliberately avoided asking the model to turn the board into unrestricted prose. A beautifully written handoff that quietly drops an unassigned ride is worse than a plain list that keeps it visible. The model can help select references, but it cannot introduce new facts into the renderer or erase approved tasks by leaving them out. The resulting message is less literary and easier to audit.

The backend also draws a boundary around each imported source. A source is shared with the circle or private to its importer. A coordinator is not automatically allowed to read another person's private material. Import, review and briefing permissions are checked on the server, and responsibility acceptance is restricted to the person concerned. The activity view shows the signed-in person's own events. None of these decisions depend on a hidden button in the browser.

The implementation stays small enough to run locally: parameterized SQLite queries and transactions, explicit state transitions, Pydantic request validation, and an in-process inference job. An identical source with the same reference timestamp is not repeatedly imported. If inference fails, the job remains visibly failed and can be retried. A server restart marks unfinished jobs for retry instead of presenting them as completed work.

The current prototype is intended for fictional data on a trusted local machine. It does not yet provide production identity verification or encrypted storage. The demo's profile switcher exists to demonstrate consent and permission boundaries, not to claim independent authentication for real households.

The interface was revised after visual review: white and slate surfaces, teal accents, sans-serif headings, larger controls, and clearer secondary text. A full production build and a genuine Chromium journey pass. Desktop and mobile screenshots were inspected at 1440×1000 and 390×844, with no detected horizontal mobile overflow or browser page errors. The browser runs in its own process so unrelated projects and browser tabs stay untouched.

Measurement also changed the implementation. The initial 32-message synthetic evaluation scored 77.8% strict category precision and recall. Confirmations were sometimes classified as appointments; cancellations sometimes changed the task category; the model sometimes assumed UTC even though the source reference carried a local timezone.

The extraction instructions now define categories by the requested action and explicitly supply the reference timezone. A later development run measured 92.9% precision and 96.3% recall, with 26 true positives, two false positives and one false negative. Owner attribution was 11/12, explicit timestamps 21/22 and change operations 3/3. The complete outputs and code/dataset hashes are preserved in the project.

Those are development-set measurements, not held-out accuracy: the prompt was refined after inspecting the same corpus. One remaining disagreement concerns whether collecting groceries should be a pickup or an errand; the original reference label was retained. A separate extra suggestion arose from a request to check availability. Missing or multiple predictions count against the applicable field metrics rather than disappearing from the denominator.

The recorded reschedule also produced an unsupported ride cancellation suggestion. The quote was genuine, but the source had requested a separate transport check, not cancellation. That suggestion was rejected. This is why source provenance and semantic correctness are different checks, and why approval remains a real decision rather than a decorative button.

## Why Does Open Innovation Matter?

Local weights let this coordination workflow run without sending family messages to a paid inference service. The model can be replaced and the extraction measured against the included labeled synthetic corpus. The schemas, validators, prompts and decision boundaries are visible in the source rather than hidden behind a claim that the model will simply get the details right.

The useful question is not whether an AI can produce a plausible plan. It is whether the people doing the work can see why an item exists, correct it, and decide whether they are willing to own it.

There is also value in being able to keep the successful and unsuccessful runs side by side. The initial model report has not been replaced with a polished headline number. Its mistakes explain the stronger timezone instruction, category editing, and the continued need for review. The prompts, raw structured outputs, validators and measured results travel with the source, so another builder can reproduce the exercise rather than accepting my preferred example.

Open weights do not make the application trustworthy by themselves. They make inspection and replacement possible. The trust comes from the smaller surrounding decisions: preserve the quote, expose uncertainty, distinguish approval from consent, and refuse to call an unfinished responsibility resolved.

## The Lazy Payoff

The intended payoff is fewer rounds of reconstructing the same conversation. Imported messages become a single review queue, approved responsibilities appear together, and the next caregiver can start from a brief that distinguishes commitments from unresolved details.

No household time savings have been measured. The included examples are synthetic demonstrations, not live-family trials or evidence of improved health outcomes.

## Prize Categories

The official challenge page was checked on October 24, 2026. The post is intended for the overall Week 3 challenge; no partner prize category is claimed because no qualifying partner integration is implemented. Gemma is excluded. The public repository, hosted screenshot links and article review are still pending in this working draft.
