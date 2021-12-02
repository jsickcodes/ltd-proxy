"""Domain model for mapping a request URL to a resource in the S3 bucket."""

from __future__ import annotations

__all__ = ["map_s3_path"]


def map_s3_path(bucket_prefix: str, request_path: str) -> str:
    """Map a request URL to an S3 bucket key."""
    # decompose the path into the project and whether it is a /v/ edition or
    # not
    parts = request_path.split("/")
    project_name = parts[0].lower()

    if parts[1].lower() == "v":
        edition_name = parts[2]
        edition_path = "/".join(parts[3:])
    else:
        edition_name = "__main"  # default edition
        edition_path = "/".join(parts[2:])

    if edition_path == "" or edition_path.endswith("/"):
        edition_path = f"{edition_path}index.html"

    if bucket_prefix == "":
        path_parts = [project_name, "v", edition_name, edition_path]
    else:
        path_parts = [
            bucket_prefix,
            project_name,
            "v",
            edition_name,
            edition_path,
        ]

    bucket_path = "/".join(path_parts)

    return bucket_path
