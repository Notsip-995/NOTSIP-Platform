from __future__ import annotations
from collections import Counter


_SEVERITY = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2, 'CRITICAL': 3}


class ThreatAssessor:
    """Evidence-first threat scoring; never performs containment or claims proof of compromise."""

    def assess(self, indicators=None):
        indicators = indicators or []
        if not isinstance(indicators, list):
            raise ValueError('indicators must be an array')
        evidence = []
        scores = []
        for raw in indicators[:100]:
            if not isinstance(raw, dict):
                continue
            kind = str(raw.get('type') or raw.get('kind') or 'unknown').strip().lower()
            severity = str(raw.get('severity') or 'LOW').upper()
            if severity not in _SEVERITY:
                severity = 'LOW'
            confidence = max(0.0, min(1.0, float(raw.get('confidence', 0.5))))
            observed = bool(raw.get('observed', True))
            evidence.append({
                'type': kind,
                'severity': severity,
                'confidence': round(confidence, 4),
                'observed': observed,
                'description': str(raw.get('description') or ''),
                'source': str(raw.get('source') or 'runtime'),
            })
            if observed:
                scores.append(_SEVERITY[severity] * confidence)
        max_score = max(scores) if scores else 0.0
        corroborated = len({e['type'] for e in evidence if e['observed']}) >= 2
        if max_score >= 2.5 and corroborated:
            severity = 'CRITICAL'
        elif max_score >= 1.5 or corroborated:
            severity = 'HIGH'
        elif max_score >= 0.7:
            severity = 'MEDIUM'
        else:
            severity = 'LOW'
        recommendation = {
            'LOW': 'continue monitoring; no containment action inferred',
            'MEDIUM': 'increase observation and validate the highest-confidence indicators',
            'HIGH': 'review affected credentials/devices and consider containment after verification',
            'CRITICAL': 'prioritize verified containment and credential/device isolation',
        }[severity]
        return {
            'status': 'SUCCESS',
            'severity': severity,
            'score': round(max_score, 4),
            'evidence': evidence,
            'indicator_types': dict(Counter(e['type'] for e in evidence)),
            'corroborated': corroborated,
            'assessment': 'HYPOTHESIS' if evidence and not (severity == 'CRITICAL' and corroborated) else 'HIGH_CONFIDENCE_ASSESSMENT',
            'recommendation': recommendation,
            'containment_executed': False,
        }
