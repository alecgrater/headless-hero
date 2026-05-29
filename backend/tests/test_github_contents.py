import base64

import httpx
import pytest

from integrations.github_contents import GitHubContentsError, upload_json_file


class MockTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, payload = self.responses.pop(0)
        return httpx.Response(status, json=payload, request=request)


def test_upload_json_file_updates_existing_file():
    transport = MockTransport(
        [
            (200, {"sha": "old-sha"}),
            (200, {"content": {"sha": "new-sha"}, "commit": {"sha": "commit-sha"}}),
        ]
    )

    result = upload_json_file(
        "ghp_test",
        "discovery/content-profile-seed.json",
        {"version": 1},
        "Update discovery content profile seed",
        client=httpx.Client(transport=httpx.MockTransport(transport)),
    )

    assert result == {
        "content_sha": "new-sha",
        "commit_sha": "commit-sha",
        "created": False,
    }
    assert transport.requests[0].method == "GET"
    assert transport.requests[1].method == "PUT"
    body = transport.requests[1].read().decode()
    assert '"sha":"old-sha"' in body
    encoded = body.split('"content":"', 1)[1].split('"', 1)[0]
    assert base64.b64decode(encoded).decode().endswith("\n")


def test_upload_json_file_creates_missing_file():
    transport = MockTransport(
        [
            (404, {"message": "Not Found"}),
            (201, {"content": {"sha": "created-sha"}, "commit": {"sha": "commit-sha"}}),
        ]
    )

    result = upload_json_file(
        token="ghp_test",
        path="discovery/content-profile-seed.json",
        content={"version": 1},
        message="Update discovery content profile seed",
        client=httpx.Client(transport=httpx.MockTransport(transport)),
    )

    assert result["created"] is True
    assert '"sha"' not in transport.requests[1].read().decode()


def test_upload_json_file_retries_once_on_conflict():
    transport = MockTransport(
        [
            (200, {"sha": "old-sha"}),
            (409, {"message": "conflict"}),
            (200, {"sha": "fresh-sha"}),
            (200, {"content": {"sha": "new-sha"}, "commit": {"sha": "commit-sha"}}),
        ]
    )

    result = upload_json_file(
        token="ghp_test",
        path="discovery/content-profile-seed.json",
        content={"version": 1},
        message="Update discovery content profile seed",
        client=httpx.Client(transport=httpx.MockTransport(transport)),
    )

    assert result["content_sha"] == "new-sha"
    assert len(transport.requests) == 4


def test_upload_json_file_raises_clear_error_on_auth_failure():
    transport = MockTransport(
        [(403, {"message": "Resource not accessible by personal access token"})]
    )

    with pytest.raises(GitHubContentsError, match="GitHub contents API failed"):
        upload_json_file(
            token="bad",
            path="discovery/content-profile-seed.json",
            content={"version": 1},
            message="Update discovery content profile seed",
            client=httpx.Client(transport=httpx.MockTransport(transport)),
        )
