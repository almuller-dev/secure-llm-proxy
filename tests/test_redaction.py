from proxy.redaction import redact_text


def test_redacts_openai_key() -> None:
    s = "please use sk-1234567890abcdefghijklmnop for auth"
    r = redact_text(s, redact_emails_phones=False)
    assert "[REDACTED:openai_key]" in r.text
    assert r.counts.get("openai_key", 0) == 1


def test_password_kv() -> None:
    s = "password=supersecret123"
    r = redact_text(s, redact_emails_phones=False)
    assert "[REDACTED:password_kv]" in r.text
