"""Versioned decision inputs for offline inspection, never an authorization gate."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def engine_fingerprint() -> str:
    """Identify actual source bytes, including uncommitted local changes."""
    root = Path(__file__).parent
    digest = sha256()
    for path in sorted(root.rglob('*.py')):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b'\0')
        digest.update(path.read_bytes())
        digest.update(b'\0')
    return digest.hexdigest()


def quote_capture(keys: list[str], response: dict[str, Any]) -> dict[str, Any]:
    return deepcopy({'requested_keys': keys, 'response': response,
                     'received_at': datetime.now(timezone.utc).isoformat(),
                     'timestamp_semantics': 'local receipt; provider timestamps retained in response'})


def replay_capture(*, options: dict[str, Any], structures: dict[str, Any] | None = None,
                   quotes: dict[str, Any] | None = None, families: dict[str, Any] | None = None,
                   lifecycle: dict[str, Any] | None = None, kind: str = 'decision',
                   captured_at: datetime | None = None) -> dict[str, Any]:
    return deepcopy({
        'schema_version': 'dantex-replay-inputs-v1',
        'kind': kind,
        'captured_at': (captured_at or datetime.now(timezone.utc)).isoformat(),
        'engine_source_sha256': engine_fingerprint(),
        'options': options,
        'structures': structures or {},
        'quote_inputs': quotes or {},
        'evidence_families': families or {},
        'lifecycle_result': lifecycle,
        'calibration_eligible': False,
        'limitations': [
            'REST sources are sequential observations, not an atomic exchange snapshot.',
            'Option-chain receipt time is not proof of exchange freshness.',
            'Selected strikes do not guarantee continued coverage of a locked contract.',
            'Sampled premiums cannot establish unobserved intrainterval stop/target order.',
        ],
    })
