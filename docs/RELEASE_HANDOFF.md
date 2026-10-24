# Release handoff

## Verified local artifacts

- App: http://127.0.0.1:3104 (backend port 8104).
- Final video: `demo/assets/video/final_demo.mp4`, 1920×1080, 108.08 seconds.
- Narrator: genuine Kokoro-82M `am_fenrir`, selected under the user's delegated non-default voice direction.
- Voiceover: `demo/assets/audio/kokoro_voiceover.wav`.
- Captions: `demo/assets/audio/subtitles.srt`; also embedded as an English subtitle track.
- Verification: `docs/final-video-verification.json`.
- Article: `docs/DEV_SUBMISSION.md`, complete Markdown with real repository/video links and five verified screenshots; ready for user review.

## GitHub checkpoint

Public repository: https://github.com/syncaimain/CareRelay. Authentication was verified as the explicitly selected `syncaimain` account, and an authenticated lookup confirmed the destination did not already exist before creation. The application and demonstration assets are pushed on `main`.

The portable official GitHub CLI is installed at `.tools/gh/bin/gh.exe`. The downloaded v2.103.2 archive passed its upstream SHA-256 checksum. Task authentication uses `.cache/github-auth` without changing the default CLI account or global Git credentials.

For future repository operations, use the task-specific configuration:

```powershell
cd G:\Hacktoberfest-2026-Week3\04-CareRelay
$env:GH_CONFIG_DIR = Join-Path (Get-Location) '.cache/github-auth'
.\.tools\gh\bin\gh.exe api user --jq .login
```

The final command must return `syncaimain`. `.cache/`, `.tools/`, local environments, runtime databases and `.env*` files are ignored; `.env.example` remains publishable. The pre-push scan found no credential patterns in 65 text files. Git author identity is configured only in this repository, using the verified account's GitHub noreply address.

The five article screenshots are pinned to asset commit `d4b6c28039f7481b8912cf414ef8ef28afadf011`. Every public raw URL returned HTTP 200 with PNG content identical to the local file; see `docs/github-publication-verification.json`.

## YouTube and article checkpoint

The user uploaded the demonstration to https://youtu.be/ylEdw_ICXTU. YouTube's public oEmbed endpoint verified the title “Care Relay” and author “Syncai”; the canonical watch page also returned successfully. Upload the separate SRT as captions if needed; the MP4's embedded subtitle track is not a guarantee that YouTube will import captions automatically.

The verified YouTube embed and screenshot links are in the article. Display the entire Markdown for user review before manual DEV publication. User article review remains pending; no DEV post has been published automatically. The application remains a local prototype, with no hosted application deployment.
