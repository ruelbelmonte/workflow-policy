from helpers import FIXTURES, findings


def test_message_suggests_sha_pin():
    first = findings("WP004", FIXTURES / "wp004" / "bad" / "unpinned.yml")[0]
    assert "`actions/checkout@v4`" in first.message and "40-character" in first.message


def test_docker_message_suggests_digest():
    docker = [f for f in findings("WP004", FIXTURES / "wp004" / "bad" / "unpinned.yml") if "docker://" in f.message]
    assert len(docker) == 2 and all("@sha256:" in f.message for f in docker)
