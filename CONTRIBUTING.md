# Contributing

Thank you for considering a contribution.

This project is a **platform-agnostic** agent recipe: a shared pipeline for reading existing online-video captions/transcripts, plus optional site adapters (Bilibili, YouTube, generic web discovery). Do not prioritize video download or ASR. Contributions should improve the common pipeline or add honest, reproducible adapters.

## Good contributions

Useful contributions include:

- improvements to the **shared pipeline** (track selection, cue model, cleanup, output metadata);
- new or clearer **site adapters** that map a platform into the shared cue model;
- access-fallback notes (e.g. local browser when the agent runtime cannot reach a site);
- examples using public, non-sensitive videos;
- error handling and honest scope notes (do not claim untested platforms are fully supported);
- documentation fixes.

Prefer extending adapters over hard-coding a single platform as the product center.

## Do not contribute

Please do not include:

- Bilibili cookies, tokens, account IDs, or session data;
- private browser profiles;
- downloaded videos;
- copyrighted subtitle dumps that cannot be shared;
- personal watch history;
- screenshots exposing account information;
- instructions that bypass access controls.

## Before opening a pull request

1. Open an issue first for large changes to the extraction flow.
2. Keep the change focused.
3. Use public, non-sensitive examples.
4. Redact all account and session data.
5. Explain whether the change affects API extraction, browser automation, or transcript cleanup.

## AI-assisted contributions

AI-generated drafts are welcome, but please review them before submission and say when a change was drafted with AI assistance.
