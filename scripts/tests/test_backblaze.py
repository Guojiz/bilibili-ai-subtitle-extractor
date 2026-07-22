from __future__ import annotations

import unittest

from scripts.lib.backblaze import B2Config, object_key, upload_bytes


class FakeS3Client:
    def __init__(self) -> None:
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)


class BackblazeTests(unittest.TestCase):
    def test_config_requires_all_values(self):
        with self.assertRaisesRegex(ValueError, "B2_BUCKET"):
            B2Config.from_env({})

    def test_object_key_is_stable_and_hides_source_url(self):
        key = object_key("demo", "lesson one.md", b"hello")
        self.assertEqual(key, "demo/2cf24dba5fb0-lesson-one.md")

    def test_upload_sends_bytes_and_returns_receipt(self):
        client = FakeS3Client()
        cfg = B2Config(
            endpoint_url="https://s3.us-west-004.backblazeb2.com",
            bucket="demo-bucket",
            key_id="test-key",
            application_key="test-secret",
        )
        receipt = upload_bytes(
            b"subtitle",
            filename="result.md",
            content_type="text/markdown; charset=utf-8",
            metadata={"platform": "youtube", "language": "en"},
            config=cfg,
            client=client,
        )
        self.assertEqual(receipt["provider"], "Backblaze B2")
        self.assertEqual(receipt["bucket"], "demo-bucket")
        self.assertEqual(len(client.calls), 1)
        call = client.calls[0]
        self.assertEqual(call["Body"], b"subtitle")
        self.assertEqual(call["Metadata"]["platform"], "youtube")


if __name__ == "__main__":
    unittest.main()

