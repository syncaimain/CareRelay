# Release handoff

## Verified local artifacts

- App: http://127.0.0.1:3104 (backend port 8104).
- Final video: `demo/assets/video/final_demo.mp4`, 1920×1080, 108.08 seconds.
- Narrator: genuine Kokoro-82M `am_fenrir`, selected under the user's delegated non-default voice direction.
- Voiceover: `demo/assets/audio/kokoro_voiceover.wav`.
- Captions: `demo/assets/audio/subtitles.srt`; also embedded as an English subtitle track.
- Verification: `docs/final-video-verification.json`.
- Article: `docs/DEV_SUBMISSION.md`, a pending 1,600+ word draft; not ready to publish without genuine public links and review.

## GitHub checkpoint

Destination is `syncaimain/CareRelay`; the user confirmed public visibility. The local Git repository is initialized on `main`. No external repository has been created or pushed. An authenticated lookup is required to check whether a private destination already exists.

The portable official GitHub CLI is installed at `.tools/gh/bin/gh.exe`. The downloaded v2.103.2 archive passed its upstream SHA-256 checksum. The existing default GitHub account does not match the requested destination and has not been switched.

Use a task-specific configuration when authenticating so another agent's default account stays unchanged:

```powershell
cd G:\Hacktoberfest-2026-Week3\04-CareRelay
$env:GH_CONFIG_DIR = Join-Path (Get-Location) '.cache/github-auth'
.\.tools\gh\bin\gh.exe auth login --hostname github.com --git-protocol https --web
.\.tools\gh\bin\gh.exe api user --jq .login
```

Choose **syncaimain** during browser authentication. The final command must return `syncaimain` before any repository operation. Do not paste tokens into chat. `.cache/`, `.tools/`, local environments, runtime databases and `.env*` files are ignored; `.env.example` remains publishable. Repeat the source scan before pushing.

## YouTube and article checkpoint

The user uploaded the demonstration to https://youtu.be/ylEdw_ICXTU. YouTube's public oEmbed endpoint verified the title “Care Relay” and author “Syncai”; the canonical watch page also returned successfully. Upload the separate SRT as captions if needed; the MP4's embedded subtitle track is not a guarantee that YouTube will import captions automatically.

The verified YouTube embed is in the article. After the authenticated repository push, verify actual screenshot URLs and replace the draft's local asset references with stable links. Display the entire final article for user review. Do not publish the DEV article automatically.
