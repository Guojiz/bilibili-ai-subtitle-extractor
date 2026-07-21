# Maintaining

Use this checklist when updating the extraction recipe.

## Review priorities

- Keep the **shared pipeline** platform-agnostic; site pages are adapters, not the product core.
- Keep the workflow reproducible with public examples.
- Prefer existing captions / transcripts over video download or ASR.
- Keep human captions preferred over platform AI / auto captions.
- Keep account, cookie, token, and browser-profile data out of the repo.
- Document assumptions when a site adapter or access-fallback behavior changes.
- Do not claim full support for platforms that were not verified.
- Keep AI-agent instructions explicit enough to audit.
- Keep GitLearnOS (or other callers) out of this repo except thin integration notes.
- Reject changes that make the recipe Bilibili-only or YouTube-only in positioning.

## Before accepting a pull request

- Check that no cookies, tokens, account IDs, private profiles, or watch history are included.
- Check that no downloaded video files are included.
- Confirm examples are public and appropriate to share.
- Confirm the change does not bypass access controls.
- Ask for a smaller pull request if extraction, cleanup, and documentation changes are mixed without need.

## Release notes

For notable changes, document:

- affected extraction step;
- tested public example;
- browser or environment assumptions;
- transcript cleanup changes;
- privacy or safety implications.