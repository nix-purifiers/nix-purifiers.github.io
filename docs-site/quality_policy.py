"""Shared tier gates; version 2 remains explicitly legacy until audited migration."""
import json
from pathlib import Path

POLICY = json.loads((Path(__file__).resolve().parents[1] / 'model/tier-policy.json').read_text())
TECHNICAL_CRITERIA = tuple(POLICY['technicalCriteria'])
HUMAN_CRITERIA = tuple(POLICY['humanCriteria'])
LABELS = POLICY['labels']


def criterion_keys(version):
    if type(version) is not int or version not in (2, 3):
        raise ValueError('unsupported quality registry version')
    return TECHNICAL_CRITERIA + (HUMAN_CRITERIA if version == 3 else ())


def best_tier(version, criteria, has_sample):
    criterion_keys(version)
    def requirements(tier):
        rule = POLICY['tiers'][str(tier)]
        return (requirements(rule['base']) if 'base' in rule else []) + rule['requires']
    def sample_required(tier):
        rule = POLICY['tiers'][str(tier)]
        return rule.get('sampleBuild', False) or ('base' in rule and sample_required(rule['base']))
    for tier in (1, 2, 3, 4):
        keys = [key for key in requirements(tier) if version == 3 or key not in HUMAN_CRITERIA]
        if (has_sample or not sample_required(tier)) and all(criteria.get(key, {}).get('state') == 'met' for key in keys):
            return tier
    return None


def require_current_registry(version):
    if type(version) is not int or version != 3:
        raise ValueError('production quality requires registry version 3')
    return True
