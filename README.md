# AI Subtitle Extractor

[中文](./README.zh-CN.md)

**Turn any online video link into a clean transcript — read the subtitles the platform already has. Human tracks first, auto tracks as fallback. No video download, no ASR.**

The core of this repo is the recipe in [`SKILL.md`](./SKILL.md): one shared pipeline, with YouTube and Bilibili as verified adapters. Any other site falls back to generic discovery — no support claimed.

```text
video link
  → identify site (or generic discovery)
  → ask the target language first — translate into the language the user wants
  → find captions (API / timedtext / VTT·SRT / transcript panel / <track>)
  → human track first → full timed cues → readable text
  → return: text + platform + language + source + method
  → site unreachable: fall back to the user's local browser
  → truly no captions: say so (only then consider ASR)
```

## Verification status

Only what actually ran is claimed.

| Component | Status |
|---|---|
| YouTube adapter | ✅ Verified on a real watch page (via WebBridge) |
| Bilibili adapter | ✅ Verified on real videos (full SRT/text export) |
| Generic sniffing (fetch/XHR hook, `textTracks`, `<track>`) | ✅ Verified in test suite + real YouTube page |
| Injection via WebBridge `evaluate` (main path) | ✅ Verified |
| Injection via Playwright `add_init_script` | ✅ Verified (whole test suite) |
| MV3 extension form | ✅ Verified on Bilibili |
| Tampermonkey install form | ⚠️ Not independently tested |
| agent-browser backend in `scripts/` | ⚠️ Not yet tested |
| Any other site | Generic discovery only |

## Quick start (verified main path)

Drive the user's real browser (their login session) through a bridge like Kimi WebBridge — nothing to install:

```text
1. node universal/build.js   → dist/universal-subtitle-extractor.user.js
2. navigate → the video page
3. evaluate → inject the .user.js file (re-injection guarded)
4. evaluate → extract in one round trip:
```

```javascript
(async () => {
  await window.__USE__.waitFor(1, 20000);
  return JSON.stringify({
    meta: window.__USE__.meta(),
    tracks: window.__USE__.list(),
    text: window.__USE__.text()
  });
})()
```

## Repository layout

| Path | What it is |
|---|---|
| [`SKILL.md`](./SKILL.md) | **The recipe (core asset)**: pipeline → adapters → fallback → output contract |
| [`universal/`](./universal/) | Runnable universal extractor (`window.__USE__` API), tests included |
| [`scripts/`](./scripts/) | Reference CLI + page-inject core (`__ovsExportSubtitle`) |
| [`examples/`](./examples/) | Adapter walkthroughs: YouTube + browser fallback, Bilibili curl |

## Contributing

Site adapters welcome: follow the shared pipeline and the `Cue` model, use public examples, label "verified" or "experimental" honestly. See [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

MIT — see [LICENSE](./LICENSE).
