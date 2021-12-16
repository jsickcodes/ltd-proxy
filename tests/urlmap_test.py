"""Tests for the urlmap module."""

from __future__ import annotations

import pytest

from ltdproxy.urlmap import map_s3_path


@pytest.mark.parametrize(
    "bucket_prefix,request_path,expected_bucket_path",
    [
        (
            "",
            "myproject/",
            "myproject/v/__main/index.html",
        ),
        (
            "",
            "myproject/test.css",
            "myproject/v/__main/test.css",
        ),
        (
            "",
            "myproject/index.html",
            "myproject/v/__main/index.html",
        ),
        (
            "",
            "myproject/v/dev",
            "myproject/v/dev/index.html",
        ),
        (
            "",
            "myproject/v/dev/index.html",
            "myproject/v/dev/index.html",
        ),
        (
            "",
            "myproject/v/dev/a/b/index.html",
            "myproject/v/dev/a/b/index.html",
        ),
        (
            "",
            "myproject/v/dev/a/b/",
            "myproject/v/dev/a/b/index.html",
        ),
        (
            "prefix",
            "myproject/",
            "prefix/myproject/v/__main/index.html",
        ),
        (
            "prefix",
            "myproject/index.html",
            "prefix/myproject/v/__main/index.html",
        ),
        (
            "prefix",
            "myproject/v/dev",
            "prefix/myproject/v/dev/index.html",
        ),
        (
            "prefix",
            "myproject/v/dev/index.html",
            "prefix/myproject/v/dev/index.html",
        ),
    ],
)
def test_map_s3_path(
    bucket_prefix: str, request_path: str, expected_bucket_path: str
) -> None:
    result = map_s3_path(bucket_prefix, request_path)
    assert result == expected_bucket_path
