"""
Deterministic Grok pattern builder for the Ingest Engine.

Analyzes sample log lines and generates Grok patterns by matching
segments against a comprehensive library of built-in patterns.
Supports preset log formats, custom pattern definitions, and
multi-sample cross-validation.

Usage::

    from elastro.core.ingest.grok_builder import GrokBuilder

    builder = GrokBuilder()
    result = builder.build_pattern([
        '192.168.1.1 - frank [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326',
    ])
    print(result.pattern)   # %{COMBINEDAPACHELOG}
    print(result.fields)    # ['clientip', 'ident', 'auth', ...]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from elastro.core.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Built-in Grok pattern library (mirrors Logstash/ES defaults)
# ---------------------------------------------------------------------------

# Atomic patterns — ordered from most specific to least specific
# Each entry: (grok_name, regex, suggested_field_name, priority)
# Higher priority = tried first during inference
_ATOMIC_PATTERNS: List[Tuple[str, str, str, int]] = [
    # --- Network ---
    (
        "IPV6",
        r"(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}|(?:[0-9A-Fa-f]{1,4}:){1,7}:|::(?:[0-9A-Fa-f]{1,4}:){0,5}[0-9A-Fa-f]{1,4}",
        "ipv6",
        95,
    ),
    (
        "IPV4",
        r"(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)",
        "clientip",
        90,
    ),
    (
        "IP",
        r"(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)",
        "ip",
        89,
    ),
    ("MAC", r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}", "mac", 88),
    ("HOSTPORT", r"[a-zA-Z0-9._-]+:\d+", "hostport", 60),
    (
        "IPORHOST",
        r"(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)|[a-zA-Z0-9._-]+",
        "host",
        55,
    ),
    # --- Timestamps ---
    (
        "TIMESTAMP_ISO8601",
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?",
        "timestamp",
        92,
    ),
    (
        "HTTPDATE",
        r"\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4}",
        "timestamp",
        91,
    ),
    ("DATESTAMP", r"\d{2}[-/.]\d{2}[-/.]\d{4}[- ]\d{2}:\d{2}:\d{2}", "timestamp", 85),
    ("SYSLOGTIMESTAMP", r"[A-Za-z]{3} +\d{1,2} \d{2}:\d{2}:\d{2}", "timestamp", 87),
    ("DATE_US", r"\d{2}[/-]\d{2}[/-]\d{4}", "date", 70),
    ("DATE_EU", r"\d{2}[/.]\d{2}[/.]\d{4}", "date", 69),
    ("DATE", r"\d{4}[/-]\d{2}[/-]\d{2}", "date", 68),
    ("TIME", r"\d{2}:\d{2}:\d{2}(?:\.\d+)?", "time", 65),
    # --- HTTP ---
    ("URIPROTO", r"[a-zA-Z][a-zA-Z0-9+.-]*", "proto", 30),
    ("URIPATH", r"/[^ ?#\"]*", "path", 50),
    ("URIPARAM", r"\?[^ #\"]*", "params", 48),
    ("URI", r"[a-zA-Z][a-zA-Z0-9+.-]*://[^ \"]+", "uri", 75),
    # --- Log levels ---
    (
        "LOGLEVEL",
        r"(?:TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|CRITICAL|NOTICE|SEVERE|EMERG(?:ENCY)?|ALERT)",
        "loglevel",
        86,
    ),
    # --- Numbers ---
    ("NUMBER", r"(?:[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?)", "number", 40),
    ("POSINT", r"\b[1-9]\d*\b", "posint", 42),
    ("NONNEGINT", r"\b\d+\b", "nonnegint", 38),
    ("BASE16NUM", r"0[xX][0-9A-Fa-f]+", "hexnum", 45),
    # --- Identifiers ---
    (
        "UUID",
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        "uuid",
        93,
    ),
    ("EMAILADDRESS", r"[\w.+-]+@[\w.-]+\.\w{2,}", "email", 88),
    (
        "HOSTNAME",
        r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*",
        "hostname",
        35,
    ),
    ("USERNAME", r"[a-zA-Z0-9._-]+", "user", 25),
    ("USER", r"[a-zA-Z0-9._-]+", "user", 24),
    ("WORD", r"\b\w+\b", "word", 10),
    # --- Catch-alls ---
    ("QUOTEDSTRING", r'"(?:[^"\\]|\\.)*"', "quoted", 52),
    ("QS", r'"(?:[^"\\]|\\.)*"', "qs", 51),
    ("GREEDYDATA", r".*", "message", 1),
    ("DATA", r".*?", "data", 2),
    ("NOTSPACE", r"\S+", "field", 5),
    ("SPACE", r"\s+", "_space", 0),
]

# Compiled pattern cache
_COMPILED_PATTERNS: List[Tuple[str, re.Pattern[str], str, int]] = []


def _get_compiled_patterns() -> List[Tuple[str, re.Pattern[str], str, int]]:
    """Lazily compile and cache all atomic patterns."""
    global _COMPILED_PATTERNS
    if not _COMPILED_PATTERNS:
        for name, regex, field_hint, priority in _ATOMIC_PATTERNS:
            try:
                compiled = re.compile(regex)
                _COMPILED_PATTERNS.append((name, compiled, field_hint, priority))
            except re.error:
                logger.warning(f"Failed to compile Grok pattern: {name}")
        _COMPILED_PATTERNS.sort(key=lambda x: -x[3])  # Highest priority first
    return _COMPILED_PATTERNS


# ---------------------------------------------------------------------------
# Preset log format templates
# ---------------------------------------------------------------------------

_PRESETS: Dict[str, Dict[str, Any]] = {
    "apache_combined": {
        "name": "Apache Combined Log",
        "pattern": '%{IPORHOST:clientip} %{USER:ident} %{USER:auth} \\[%{HTTPDATE:timestamp}\\] "%{WORD:verb} %{URIPATH:request}(?:%{URIPARAM:params})?(?: HTTP/%{NUMBER:httpversion})?" %{NUMBER:response} (?:%{NUMBER:bytes}|-)',
        "example": '192.168.1.1 - frank [10/Oct/2000:13:55:36 -0700] "GET /index.html HTTP/1.0" 200 2326',
    },
    "apache_common": {
        "name": "Apache Common Log",
        "pattern": '%{IPORHOST:clientip} %{USER:ident} %{USER:auth} \\[%{HTTPDATE:timestamp}\\] "%{WORD:verb} %{URIPATH:request}(?: HTTP/%{NUMBER:httpversion})?" %{NUMBER:response} (?:%{NUMBER:bytes}|-)',
        "example": '192.168.1.1 - frank [10/Oct/2000:13:55:36 -0700] "GET /index.html HTTP/1.0" 200 2326',
    },
    "syslog": {
        "name": "Syslog (RFC 3164)",
        "pattern": "%{SYSLOGTIMESTAMP:timestamp} %{IPORHOST:hostname} %{DATA:program}(?:\\[%{POSINT:pid}\\])?: %{GREEDYDATA:message}",
        "example": "Oct  5 09:47:23 myhost sshd[1234]: Accepted publickey for user",
    },
    "nginx_combined": {
        "name": "Nginx Combined Log",
        "pattern": '%{IPORHOST:clientip} - %{USER:remote_user} \\[%{HTTPDATE:timestamp}\\] "%{WORD:verb} %{URIPATH:request}(?: HTTP/%{NUMBER:httpversion})?" %{NUMBER:response} %{NUMBER:bytes} "%{DATA:referrer}" "%{DATA:agent}"',
        "example": '10.0.0.1 - admin [10/Oct/2000:13:55:36 -0700] "POST /api/v1/data HTTP/1.1" 201 512 "https://example.com" "curl/7.68"',
    },
    "json_log": {
        "name": "JSON Structured Log (with prefix)",
        "pattern": "%{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:level} %{NOTSPACE:logger} - %{GREEDYDATA:message}",
        "example": "2026-01-15T10:30:00.123Z INFO com.app.Service - Processing request id=abc123",
    },
    "java_log4j": {
        "name": "Java Log4j",
        "pattern": "%{TIMESTAMP_ISO8601:timestamp} \\[%{DATA:thread}\\] %{LOGLEVEL:level} %{NOTSPACE:logger} - %{GREEDYDATA:message}",
        "example": "2026-01-15T10:30:00.123Z [main] INFO com.app.Main - Application started",
    },
}


# ---------------------------------------------------------------------------
# Grok inference result
# ---------------------------------------------------------------------------


@dataclass
class GrokResult:
    """Result of a Grok pattern inference operation."""

    pattern: str
    fields: List[str] = field(default_factory=list)
    preset_name: Optional[str] = None
    confidence: float = 0.0
    matched_samples: int = 0
    total_samples: int = 0
    custom_definitions: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    @property
    def match_rate(self) -> float:
        if self.total_samples == 0:
            return 0.0
        return (self.matched_samples / self.total_samples) * 100

    def to_processor_dict(self, source_field: str = "message") -> Dict[str, Any]:
        """Convert to an ES Grok processor definition."""
        cfg: Dict[str, Any] = {
            "grok": {
                "field": source_field,
                "patterns": [self.pattern],
            }
        }
        if self.custom_definitions:
            cfg["grok"]["pattern_definitions"] = self.custom_definitions
        return cfg


# ---------------------------------------------------------------------------
# Segment — an identified token in a log line
# ---------------------------------------------------------------------------


@dataclass
class _Segment:
    """A matched segment of a log line."""

    start: int
    end: int
    grok_name: str
    field_name: str
    text: str
    priority: int


# ---------------------------------------------------------------------------
# GrokBuilder — the main engine
# ---------------------------------------------------------------------------


class GrokBuilder:
    """Deterministic Grok pattern builder.

    Analyzes sample log lines and generates Grok patterns by:

    1. Attempting to match preset log formats first (highest confidence).
    2. Falling back to segment-by-segment token analysis using the
       built-in pattern library.
    3. Cross-validating the generated pattern against all samples.
    4. Assigning confidence scores based on match rate and pattern
       specificity.

    Args:
        custom_patterns: Additional pattern definitions to include
            in the pattern library (name → regex).
    """

    def __init__(
        self,
        custom_patterns: Optional[Dict[str, str]] = None,
    ) -> None:
        self._custom_patterns = custom_patterns or {}
        self._field_counter: Dict[str, int] = {}

    def build_pattern(
        self,
        samples: List[str],
        *,
        source_field: str = "message",
        prefer_preset: bool = True,
    ) -> GrokResult:
        """Analyze sample log lines and generate a Grok pattern.

        Args:
            samples: One or more sample log lines.
            source_field: The ES document field containing the log text.
            prefer_preset: Try preset patterns before inference.

        Returns:
            A :class:`GrokResult` with the generated pattern, field names,
            and confidence score.
        """
        if not samples:
            return GrokResult(
                pattern="%{GREEDYDATA:message}",
                fields=["message"],
                confidence=0.0,
                total_samples=0,
            )

        clean_samples = [s.strip() for s in samples if s.strip()]
        if not clean_samples:
            return GrokResult(
                pattern="%{GREEDYDATA:message}",
                fields=["message"],
                confidence=0.0,
                total_samples=len(samples),
            )

        # Phase 1: Try presets
        if prefer_preset:
            preset_result = self._try_presets(clean_samples)
            if preset_result is not None:
                return preset_result

        # Phase 2: Segment-based inference from first sample
        self._field_counter.clear()
        primary = clean_samples[0]
        pattern, fields = self._infer_pattern(primary)

        # Phase 3: Cross-validate against all samples
        matched = self._cross_validate(pattern, clean_samples)

        # Phase 4: Calculate confidence
        specificity = self._pattern_specificity(pattern)
        match_rate = matched / len(clean_samples) if clean_samples else 0.0
        confidence = round(match_rate * 0.7 + specificity * 0.3, 2)

        warnings: List[str] = []
        if match_rate < 1.0:
            unmatched = len(clean_samples) - matched
            warnings.append(
                f"{unmatched}/{len(clean_samples)} sample(s) did not match the pattern"
            )
        if "GREEDYDATA" in pattern and pattern.count("GREEDYDATA") > 1:
            warnings.append("Multiple GREEDYDATA captures reduce pattern precision")

        return GrokResult(
            pattern=pattern,
            fields=fields,
            confidence=confidence,
            matched_samples=matched,
            total_samples=len(clean_samples),
            custom_definitions=dict(self._custom_patterns),
            warnings=warnings,
        )

    def list_presets(self) -> Dict[str, Dict[str, Any]]:
        """Return available preset log format templates."""
        return dict(_PRESETS)

    def get_preset(self, name: str) -> Optional[GrokResult]:
        """Get a preset pattern by name."""
        preset = _PRESETS.get(name)
        if preset is None:
            return None
        pattern = preset["pattern"]
        fields = self._extract_field_names(pattern)
        return GrokResult(
            pattern=pattern,
            fields=fields,
            preset_name=name,
            confidence=1.0,
            matched_samples=0,
            total_samples=0,
        )

    # ------------------------------------------------------------------
    # Preset matching
    # ------------------------------------------------------------------

    def _try_presets(self, samples: List[str]) -> Optional[GrokResult]:
        """Try each preset pattern against the samples."""
        patterns = _get_compiled_patterns()

        for preset_key, preset in _PRESETS.items():
            grok_pattern = preset["pattern"]
            regex = self._grok_to_regex(grok_pattern)
            if regex is None:
                continue

            try:
                compiled = re.compile(f"^{regex}$")
            except re.error:
                continue

            matched = sum(1 for s in samples if compiled.match(s))
            if matched == len(samples):
                fields = self._extract_field_names(grok_pattern)
                return GrokResult(
                    pattern=grok_pattern,
                    fields=fields,
                    preset_name=preset_key,
                    confidence=1.0,
                    matched_samples=matched,
                    total_samples=len(samples),
                )

        return None

    # ------------------------------------------------------------------
    # Segment-based inference
    # ------------------------------------------------------------------

    def _infer_pattern(self, line: str) -> Tuple[str, List[str]]:
        """Build a Grok pattern by scanning the line left-to-right."""
        patterns = _get_compiled_patterns()
        pos = 0
        parts: List[str] = []
        fields: List[str] = []
        length = len(line)

        while pos < length:
            best_match: Optional[_Segment] = None

            # Skip delimiters: brackets, quotes, whitespace, common separators
            ch = line[pos]
            if ch in " \t":
                # Consume whitespace
                ws_end = pos
                while ws_end < length and line[ws_end] in " \t":
                    ws_end += 1
                parts.append(" ")
                pos = ws_end
                continue

            # Literal delimiters
            if ch in "[](){}":
                parts.append("\\" + ch)
                pos += 1
                continue

            if ch == '"':
                # Try to match a quoted string
                qs_match = re.match(r'"(?:[^"\\]|\\.)*"', line[pos:])
                if qs_match:
                    field_name = self._unique_field("quoted")
                    parts.append(f'"%{{DATA:{field_name}}}"')
                    fields.append(field_name)
                    pos += qs_match.end()
                    continue
                parts.append('"')
                pos += 1
                continue

            # Try each atomic pattern at current position
            for grok_name, compiled, hint, priority in patterns:
                if grok_name in ("GREEDYDATA", "DATA", "SPACE"):
                    continue  # Skip catch-alls during scanning

                m = compiled.match(line, pos)
                if m and m.start() == pos and m.end() > pos:
                    candidate = _Segment(
                        start=m.start(),
                        end=m.end(),
                        grok_name=grok_name,
                        field_name=hint,
                        text=m.group(),
                        priority=priority,
                    )
                    if best_match is None or (
                        candidate.end > best_match.end
                        or (
                            candidate.end == best_match.end
                            and candidate.priority > best_match.priority
                        )
                    ):
                        best_match = candidate

            if best_match is not None:
                field_name = self._unique_field(best_match.field_name)
                parts.append(f"%{{{best_match.grok_name}:{field_name}}}")
                fields.append(field_name)
                pos = best_match.end
            else:
                # Literal character
                if ch in r"\.^$*+?{}|()[]":
                    parts.append("\\" + ch)
                else:
                    parts.append(ch)
                pos += 1

        # Collapse trailing segments: if the last capture is a low-priority
        # WORD or NOTSPACE and there's remaining text, replace with GREEDYDATA
        pattern = "".join(parts)
        return pattern, fields

    # ------------------------------------------------------------------
    # Cross-validation
    # ------------------------------------------------------------------

    def _cross_validate(self, pattern: str, samples: List[str]) -> int:
        """Validate the pattern against all samples, return match count."""
        regex = self._grok_to_regex(pattern)
        if regex is None:
            return 0
        try:
            compiled = re.compile(f"^{regex}$")
        except re.error:
            return 0

        return sum(1 for s in samples if compiled.match(s))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _unique_field(self, base: str) -> str:
        """Generate a unique field name by appending a counter if needed."""
        count = self._field_counter.get(base, 0)
        self._field_counter[base] = count + 1
        if count == 0:
            return base
        return f"{base}{count + 1}"

    @staticmethod
    def _extract_field_names(pattern: str) -> List[str]:
        """Extract field names from a Grok pattern string."""
        return re.findall(r"%\{[^:}]+:([^}]+)\}", pattern)

    @staticmethod
    def _grok_to_regex(pattern: str) -> Optional[str]:
        """Convert a Grok pattern to a Python regex.

        Replaces ``%{NAME:field}`` and ``%{NAME}`` references with
        their underlying regex from the pattern library.
        """
        lookup = {name: regex for name, regex, _, _ in _ATOMIC_PATTERNS}
        result = pattern

        # Iteratively resolve %{NAME:field} and %{NAME}
        max_iterations = 20
        for _ in range(max_iterations):
            prev = result

            # Named captures: %{PATTERN:field}
            def _replace_named(m: re.Match[str]) -> str:
                name = m.group(1)
                field_name = m.group(2)
                regex = lookup.get(name, r"\S+")
                return f"(?P<{field_name}>{regex})"

            result = re.sub(r"%\{(\w+):(\w+)\}", _replace_named, result)

            # Unnamed references: %{PATTERN}
            def _replace_unnamed(m: re.Match[str]) -> str:
                name = m.group(1)
                regex = lookup.get(name, r"\S+")
                return f"(?:{regex})"

            result = re.sub(r"%\{(\w+)\}", _replace_unnamed, result)

            if result == prev:
                break

        if "%{" in result:
            return None
        return result

    @staticmethod
    def _pattern_specificity(pattern: str) -> float:
        """Score pattern specificity (0.0 to 1.0).

        Patterns with more specific tokens (IP, TIMESTAMP, UUID) score
        higher than those relying heavily on GREEDYDATA/NOTSPACE.
        """
        tokens = re.findall(r"%\{(\w+):", pattern)
        if not tokens:
            return 0.0

        high_value = {
            "IPV4",
            "IPV6",
            "IP",
            "TIMESTAMP_ISO8601",
            "HTTPDATE",
            "SYSLOGTIMESTAMP",
            "UUID",
            "EMAILADDRESS",
            "LOGLEVEL",
            "MAC",
            "URI",
            "DATESTAMP",
        }
        medium_value = {
            "NUMBER",
            "POSINT",
            "NONNEGINT",
            "DATE",
            "TIME",
            "HOSTNAME",
            "IPORHOST",
            "URIPATH",
            "WORD",
            "USERNAME",
            "USER",
            "QUOTEDSTRING",
            "QS",
        }
        low_value = {"GREEDYDATA", "DATA", "NOTSPACE"}

        total = len(tokens)
        score = 0.0
        for t in tokens:
            if t in high_value:
                score += 1.0
            elif t in medium_value:
                score += 0.6
            elif t in low_value:
                score += 0.1
            else:
                score += 0.3

        return round(score / total, 2)
