# Backblaze B2 integration

AI Subtitle Extractor can optionally archive an emitted Markdown or JSON
transcript in Backblaze B2 through its S3-compatible API. Extraction remains
local-first; no upload happens unless `--b2-upload` is passed.

## Configure

Create a bucket and a restricted application key that can write only to that
bucket. Do not commit credentials.

```text
B2_ENDPOINT_URL=https://s3.<region>.backblazeb2.com
B2_REGION=<region>
B2_BUCKET=<bucket-name>
B2_KEY_ID=<application-key-id>
B2_APPLICATION_KEY=<application-key>
```

Install the optional client:

```bash
python -m pip install boto3
```

## Verify safely

Preview the deterministic object key without network access:

```bash
python scripts/extract_subtitles.py <video-url> --json --b2-dry-run
```

Run a real upload:

```bash
python scripts/extract_subtitles.py <video-url> --json -o result.json --b2-upload
```

The command prints a receipt containing the bucket, key, endpoint, and SHA-256
digest. It never prints credentials. The object metadata records platform,
language, adapter, and cue count; the source video URL is deliberately not
stored as object metadata.

## Verification status

- Unit-tested with an injected S3-compatible client.
- Dry-run is available without credentials.
- A real Backblaze upload must be completed with the project owner's bucket
  before the Devpost submission may claim a live integration.

