# Maintaining

Use this checklist when updating the extraction recipe.

## Review priorities

- Keep the workflow reproducible with public examples.
- Prefer existing caption APIs over video download or ASR.
- Keep account, cookie, token, and browser-profile data out of the repo.
- Document assumptions when Bilibili behavior changes.
- Keep AI-agent instructions explicit enough to audit.

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