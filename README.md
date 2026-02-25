# Secure LLM Proxy

A production-minded LLM proxy demonstrating:
- API-key auth (proxy keys)
- secret redaction
- per-key rate limiting (token bucket)
- per-key budgets (requests/day, tokens/day, optional USD/day/month)
- audit logging (JSONL; stores redacted content by default)
- CI + Docker build

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]

# Set upstream OpenAI key
export OPENAI_API_KEY="..."

# Optional: enable email/phone redaction
export REDACT_EMAILS_PHONES=1

# Configure proxy keys (JSON list)
export PROXY_KEYS_JSON='[
  {
    "key":"demo-dev-key-change-me",
    "tenant":"demo",
    "rpm":30,
    "burst":10,
    "max_requests_per_day":500,
    "max_tokens_per_day":200000,
    "max_usd_per_day":0.0,
    "max_usd_per_month":0.0
  }
]'

uvicorn proxy.main:app --host 0.0.0.0 --port 8080
```

## Call it

```bash
curl -s http://localhost:8080/v1/chat.completions \
  -H "Content-Type: application/json" \
  -H "X-Proxy-Key: demo-dev-key-change-me" \
  -d '{
    "model":"gpt-4o-mini",
    "messages":[{"role":"user","content":"Explain token bucket rate limiting in 2 sentences."}],
    "temperature":0.2,
    "max_tokens":120
  }' | jq
```

## Notes on cost enforcement

By default, USD spend caps are disabled unless you set:
- `PRICE_PER_1K_INPUT_USD`
- `PRICE_PER_1K_OUTPUT_USD`

Budgets still enforce requests/day and tokens/day.

## Audit logs

Audit logs are appended to `data/audit.jsonl`. By default they store redacted request content only.
Set `STORE_RAW_IN_AUDIT=1` to include raw prompt content (not recommended outside controlled environments).
