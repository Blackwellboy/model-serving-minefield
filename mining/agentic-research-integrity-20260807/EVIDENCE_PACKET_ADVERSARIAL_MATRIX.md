# Evidence Packet adversarial matrix (publication readiness)

| CASE | EXPECTED | ACTUAL | RESULT |
|------|----------|--------|--------|
| clean non-empty | PASS | PASS | PASS |
| moving main | FAIL | FAIL | PASS |
| CLAIMED_UNVERIFIED identity | HOLD | HOLD | PASS |
| HTTP200 zero obs model claim | FAIL | FAIL | PASS |
| malformed hash | FAIL | FAIL | PASS |
| missing artifact bytes flag | UNKNOWN | UNKNOWN | PASS |
| zero obs reproduced | FAIL | FAIL | PASS |
| infra as target negative | FAIL | FAIL | PASS |
| UNKNOWN as negative | FAIL | FAIL | PASS |
| self-review marked independent | FAIL | FAIL | PASS |
| waiver no reason | FAIL | FAIL | PASS |
| shared harness independent | FAIL | FAIL | PASS |
| missing claim boundary | FAIL | FAIL | PASS |
| summary only promotion | FAIL | FAIL | PASS |
| sanitization conflict | FAIL | FAIL | PASS |

INVALID_PACKET_SILENT_PASS_COUNT=0
Silent PASS when expected non-PASS: 0

