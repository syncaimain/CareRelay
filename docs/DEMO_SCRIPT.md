# Demo script — synthetic data only

Status: the complete genuine workflow was recorded successfully. The verified silent MP4 is `demo/assets/video/demo_silent.mp4` (1920×1080, 118.8 seconds). The final narrated MP4 is `demo/assets/video/final_demo.mp4` (108.08 seconds), using genuine Kokoro-82M `am_fenrir` with English captions. The user-uploaded demonstration is verified at https://youtu.be/ylEdw_ICXTU.

## Prerequisites

Run Ollama with `ministral-3:14b`, FastAPI on port 8104 and Next.js on port 3104. Create a new fictional Morgan circle. The local AI indicator must be ready. No real-family information should appear in the browser or recording.

## Story

Alex, Maya, Sam and Robin all want to help. They have messages, a shifted appointment, and an unclaimed return ride. Nobody needs another group chat summary; they need a shared plan with clear evidence and consent.

1. Show the overview and four fictional profiles.
2. Open Import inbox and load the fictional conversation. For this rescheduling story, change the first line from a confirmation request to “The clinic appointment is on 2026-10-26 at 10:00 at Oak Clinic.” Show the reference date and synthetic label. Import with the real local model. The recording script makes this explicit synthetic-input edit after the source has loaded.
3. Open the review queue. Read an original quote, check its interpreted date/time, and show an unresolved question. Approve the appointment and travel tasks. Maya's proposed drive overlaps her work shift; this stays visible.
4. Open the responsibility board. Point out that proposed owners have not accepted responsibilities and that the return ride is unclaimed. Switch to the appropriate fictional caregiver in Privacy & access to accept a task, then return to Alex.
5. Copy `reschedule_text` from `demo/dataset.json` into a second import. Approve its reschedule suggestion only after selecting the original approved clinic item. Show the original marked cancelled and replacement active. Check travel independently: no ride is silently moved or assigned.
6. Show the calendar, including the replacement date and PKT timezone label.
7. Prepare a day brief for the relevant date. Show evidence IDs, accepted items and unresolved items. Approve for manual sharing. Copy only after approval; nothing is automatically sent.

## Recording

`demo/record_demo.ts` uses the installed Playwright Chromium and Node 22's built-in TypeScript stripping. It exercises the entire story above, including caregiver switching, rescheduling and approval, and records actual screenshots and WebM. It does not stub inference. Long real model latency must be transparently handled in any later edited video.

Record and convert the actual returned recording path:

```powershell
node --experimental-strip-types demo/record_demo.ts
$recordingFile = (Get-Content demo/assets/video/recording-path.txt -Raw).Trim()
ffmpeg -i $recordingFile -c:v libx264 -threads 4 -crf 20 -pix_fmt yuv420p -movflags +faststart demo/assets/video/demo_silent.mp4
```

The existing MP4 passed a full FFmpeg decode. `docs/demo-recording.json` preserves the actual UI event timeline and verified final state. Failed development takes remain ignored and are not publication assets.

The narration script, voiceover and SRT are under `demo/assets/audio/`. `docs/final-video-verification.json` records final decoding and stream checks. The YouTube embed is in the DEV article; authenticated GitHub publication, hosted screenshot links and user article review remain pending.
