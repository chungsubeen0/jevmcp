import logging

from jev_mcp.engine import Engine
from jev_mcp.errors import ErrorCode, JevError
from jev_mcp.providers.mock import MockJudgmentProvider
from jev_mcp.telemetry.privacy import redact_text
from jev_mcp.tools.judge import run_judge

def _fixture(*parts: str) -> str:
    """Assemble fake leak strings at runtime so scanners do not treat fixtures as live secrets."""
    return "".join(parts)


SECRETS = [
    _fixture("apikey_", "27640ad988025db4016987967cc024ecc95_deadbeef"),
    _fixture("ghp_", "abcdefghijklmnopqrstuvwxyz0123456789"),
    _fixture("glpat-", "abcdefghijklmnopqrstuvwx"),
    _fixture("xoxb-", "1234567890-abcdefghij"),
    _fixture("npm_", "abcdefghijklmnopqrstuvwx"),
    _fixture("AKIA", "IOSFODNN7EXAMPLE"),
    _fixture("sk_live_", "51FakeStripeSecretKeyValue"),
    _fixture("Bearer ", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.", "eyJzdWIiOiIxMjM0In0.", "abcdeghijk"),
    _fixture("postgres://", "user:hunter2@localhost:5432/app"),
]


async def test_secrets_redacted_from_errors_logs_telemetry_cache(app_config, caplog):
    blob = "leak " + " ".join(SECRETS)
    engine = Engine.create(app_config, provider=MockJudgmentProvider(answers={"Q1": 0.5}))
    with caplog.at_level(logging.INFO):
        result = await run_judge(
            engine,
            state={"dump": blob},
            questions=[{"id": "Q1", "question": "Does the supplied evidence suggest a leak string?"}],
        )
    dumped = str(result) + str(engine.telemetry.export_rows())
    cache_bytes = engine.config.cache_path().read_bytes() if engine.config.cache_path().exists() else b""
    error = JevError(ErrorCode.PROVIDER_UNAVAILABLE, f"failed with {blob}").to_dict()
    surfaces = dumped + str(error) + caplog.text + cache_bytes.decode("utf-8", errors="ignore")
    for secret in SECRETS:
        assert secret not in surfaces
        assert secret not in redact_text(blob)
    assert "[REDACTED]" in redact_text(blob)
