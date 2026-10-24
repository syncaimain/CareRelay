# Publishing checklist

The user selected the GitHub destination `syncaimain`, confirmed public visibility, and delegated selection of a non-default Kokoro voice. Authenticated access as `syncaimain` is pending. No repository has been created or pushed.

- [x] Inspect environment and available local models.
- [x] Select Ministral 3 14B with the user.
- [x] Implement backend and frontend source.
- [x] Pass deterministic backend tests and TypeScript checking.
- [x] Complete model download and genuine inference verification (`docs/model-verification.json`).
- [x] Run the labeled real-model evaluation and report measured values. Baseline and revised development results are preserved; this is not a held-out evaluation.
- [x] Pass full production build and real-browser end-to-end test.
- [x] Inspect responsive UI and capture actual screenshots.
- [x] Record and verify the actual 90–150-second Playwright demonstration: 1920×1080 H.264, 118.8 seconds; full FFmpeg decode passed.
- [x] Inspect source files for credential patterns; runtime data, environments, caches and private `.env` files are ignored. Repeat before the eventual push.
- [x] Confirm GitHub destination and visibility: `syncaimain/CareRelay`, public. Authentication is still required before the destination can be verified and published.
- [ ] Verify the chosen destination and permission before repository creation, remote changes or push. Do not choose an account silently.
- [ ] Verify the returned real repository URL, branch and stable hosted screenshot URLs.
- [x] Obtain voice direction from the user. They requested a non-common voice and delegated the choice; `am_fenrir` was selected from the verified Kokoro English voices. Kokoro 0.9.4 runs locally on CPU. This is a non-default selection, not a claim based on measured voice popularity.
- [x] Generate real Kokoro `am_fenrir` voiceover, phrase-aligned subtitles and `final_demo.mp4`; verify full decoding, stream formats, audio levels and subtitle timing. Final duration: 108.08 seconds.
- [x] Give the precise final video path and request upload to the user's chosen YouTube account as Public or Unlisted. The actual URL has now been supplied and verified.
- [x] Validate the supplied YouTube URL (`https://youtu.be/ylEdw_ICXTU`, “Care Relay” by Syncai) through public oEmbed and a successful canonical watch-page response; add the real video ID to the DEV embed.
- [x] Verify the official Week 3 prompt and required tags (`devchallenge`, `hf26challenge`); overall submission only, with no unsupported partner category claims and no Gemma.
- [ ] Finalize and display the entire DEV Markdown with actual links, measurements and screenshots.
- [ ] Obtain article review. Do not publish DEV automatically.

Current status: local development only. No fabricated screenshots, video, model measurements, repository URL or YouTube link should be substituted for unfinished work.
