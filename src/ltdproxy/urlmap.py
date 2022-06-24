"""Domain model for mapping a request URL to a resource in the S3 bucket."""

from __future__ import annotations

from typing import List

__all__ = ["map_s3_path"]


def map_s3_path(bucket_prefix: str, request_path: str) -> str:
    """Map a request URL to an S3 bucket key."""
    # decompose the path into the project and whether it is a /v/ edition or
    # not
    path_parts = create_bucket_path(request_path)
    if bucket_prefix:
        print("inserting bucket prefix")
        path_parts.insert(0, bucket_prefix)
    else:
        print(f"No bucket prefix: {bucket_prefix}.")

    bucket_path = "/".join(path_parts)
    bucket_path = bucket_path.rstrip("/")  # happens if edition_path is ""

    return bucket_path


def create_bucket_path(request_path: str) -> List[str]:
    parts = request_path.split("/")
    parts_count = len(parts)
    project_name = parts[0].lower()

    if parts_count == 1:
        return [project_name, "v", "__main"]
    elif parts[1].lower() == "v":
        if parts_count == 2:
            return [project_name, "v"]
        elif parts_count == 3:
            if parts[2] == "":
                return [project_name, "v", "index.html"]
            else:
                return [project_name, "v", parts[2]]
        else:
            return create_edition_path(
                project=project_name, edition=parts[2], path=parts[3:]
            )
    elif parts[1].lower() == "builds":
        if parts_count == 2:
            return [project_name, "builds"]
        elif parts_count == 3:
            if parts[2] == "":
                return [project_name, "builds", "index.html"]
            else:
                return [project_name, "builds", parts[2]]
        else:
            return create_build_path(
                project=project_name, build=parts[2], path=parts[3:]
            )
    elif parts[1] == "_dashboard-assets":
        return parts
    else:
        edition_name = "__main"
        return create_edition_path(
            project=project_name, edition=edition_name, path=parts[1:]
        )


def create_edition_path(
    *, project: str, edition: str, path: List[str]
) -> List[str]:
    if path[-1] == "":
        path_str = f'{"/".join(path)}index.html'
    else:
        path_str = "/".join(path)

    return [
        project,
        "v",
        edition,
        path_str,
    ]


def create_build_path(
    *, project: str, build: str, path: List[str]
) -> List[str]:
    if path[-1] == "":
        path_str = f'{"/".join(path)}index.html'
    else:
        path_str = "/".join(path)

    return [
        project,
        "builds",
        build,
        path_str,
    ]
