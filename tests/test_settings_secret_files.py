from __future__ import annotations

import pytest

from app.core.config import Settings


def test_settings_read_otp_and_redis_from_private_files(tmp_path):
    otp_file = tmp_path / "otp.secret"
    redis_file = tmp_path / "redis.url"
    otp_file.write_text("unit-test-otp-hmac-value-at-least-32-bytes\n", encoding="utf-8")
    redis_file.write_text("redis://:unit-test-password@redis:6379/0\n", encoding="utf-8")
    otp_file.chmod(0o600)
    redis_file.chmod(0o600)

    settings = Settings(
        _env_file=None,
        otp_hmac_secret_file=str(otp_file),
        redis_url_file=str(redis_file),
    )

    assert settings.otp_hmac_secret == "unit-test-otp-hmac-value-at-least-32-bytes"
    assert settings.redis_url == "redis://:unit-test-password@redis:6379/0"


def test_settings_reject_group_or_world_readable_secret_file(tmp_path):
    secret_file = tmp_path / "redis.url"
    secret_file.write_text("redis://:unit-test-password@redis:6379/0", encoding="utf-8")
    secret_file.chmod(0o640)

    with pytest.raises(ValueError, match="configured secret file is unavailable"):
        Settings(_env_file=None, redis_url_file=str(secret_file))
