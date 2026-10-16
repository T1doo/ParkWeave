"""Equivalent known-token replacement with a checked fast path.

The caller's ordered values remain the reference fallback. Every-position
lookahead is intentional: tokens may be embedded in a larger URL-safe word.
No token values are logged or exposed by the returned statistics.
"""
import re
from collections import Counter

TOKEN = re.compile(r'(?=([A-Za-z0-9_-]{43}))')
FULL_TOKEN = re.compile(r'[A-Za-z0-9_-]{43}\Z')
PLACEHOLDER = '[REDACTED_SYNTHETIC_SESSION]'


def reference_replace(text, values):
    count = 0
    for value in values:
        matches = text.count(value)
        if matches:
            count += matches
            text = text.replace(value, PLACEHOLDER)
    return text, count


class KnownTokenRedactor:
    def __init__(self, values):
        self.ordered_values = tuple(values)
        self.values = frozenset(values)
        self.fast_pool = all(isinstance(value, str) and FULL_TOKEN.fullmatch(value) is not None for value in values)
        self.fast_values = frozenset(value for value in values if isinstance(value, str) and FULL_TOKEN.fullmatch(value) is not None)
        self.short_values = tuple(value for value in values if isinstance(value, str) and 0 < len(value) < 43)
        self.mixed_short_pool = bool(self.fast_values) and not self.fast_pool and all(isinstance(value, str) and (FULL_TOKEN.fullmatch(value) is not None or 0 < len(value) < 43) for value in values) and self.ordered_values == tuple(sorted(values, key=lambda value: (-len(value), value)))
        # The placeholder cannot create a new 43-character URL-safe token: its
        # surrounding brackets break both splice boundaries, and its interior
        # has fewer than 43 characters.
        assert len(PLACEHOLDER) < 43 and PLACEHOLDER.startswith('[') and PLACEHOLDER.endswith(']')
        self.stats = Counter()

    def replace(self, text):
        self.stats['replace_calls'] += 1
        if not (self.fast_pool or self.mixed_short_pool):
            self.stats['fallback_pool_calls'] += 1
            result, count = reference_replace(text, self.ordered_values)
            self.stats['exact_replacements'] += count
            return result, count
        spans = []
        prior_end = -1
        for match in TOKEN.finditer(text):
            self.stats['candidate_positions'] += 1
            if match.group(1) not in self.fast_values:
                continue
            start, end = match.start(), match.start() + 43
            if start < prior_end:
                self.stats['fallback_overlap_calls'] += 1
                result, count = reference_replace(text, self.ordered_values)
                self.stats['exact_replacements'] += count
                return result, count
            spans.append((start, end))
            prior_end = end
        self.stats['fast_calls'] += 1
        self.stats['matched_nonoverlapping_spans'] += len(spans)
        self.stats['exact_replacements'] += len(spans)
        if not spans:
            result, count = reference_replace(text, self.short_values)
            self.stats['exact_replacements'] += count
            return result, count
        pieces = []
        end = 0
        for start, stop in spans:
            pieces.extend((text[end:start], PLACEHOLDER))
            end = stop
        pieces.append(text[end:])
        result, short_count = reference_replace(''.join(pieces), self.short_values)
        self.stats['exact_replacements'] += short_count
        return result, len(spans) + short_count

    def has_residual(self, text):
        self.stats['residual_calls'] += 1
        if not (self.fast_pool or self.mixed_short_pool):
            self.stats['residual_fallback_pool_calls'] += 1
            return any(value in text for value in self.ordered_values)
        self.stats['residual_fast_calls'] += 1
        return any(match.group(1) in self.fast_values for match in TOKEN.finditer(text)) or any(value in text for value in self.short_values)

    def public_statistics(self):
        return {'pool_count': len(self.ordered_values), 'unique_pool_count': len(self.values),
                'all_values_43_urlsafe': self.fast_pool, 'mixed_short_pool': self.mixed_short_pool, 'placeholder_characters': len(PLACEHOLDER),
                **dict(self.stats)}
