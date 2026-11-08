import copy
import json
from pathlib import Path
import unittest

from human_use_evidence import public_report, render_reports, validate_review
from quality_policy import TECHNICAL_CRITERIA, best_tier

REPOSITORY = 'nix-purifiers/sbt-purifier'


def fixture():
    return json.loads((Path(__file__).parent / 'fixtures/human-use/sbt-firsthand.json').read_text())


def cases():
    original = fixture()
    yield 'attributed contributor sample report', original, True
    private = copy.deepcopy(original)
    report = private['reports']['sbt-pr-13']
    report['source'] = {'kind': 'direct-attestation', 'url': None, 'reference': 'supplied-report-1'}
    report['reporter']['publicLabel'] = None
    report['reporter']['relationship'] = 'maintainer'
    yield 'private maintainer attestation has no public URL', private, True
    missing = copy.deepcopy(original)
    missing['reports'] = {}
    missing['criteria']['firsthandUse'].update(state='not-met', reports=[], gap='No reviewed firsthand report is recorded.')
    yield 'missing report stays an honest gap', missing, True
    for name, edit in [
        ('carriage-return-only scope', lambda r: r['reports']['sbt-pr-13'].update(scope='\r')),
        ('Unicode-whitespace-only summary', lambda r: r['reports']['sbt-pr-13'].update(summary='\u00a0')),
        ('Unicode whitespace in primary URL', lambda r: r['reports']['sbt-pr-13']['source'].update(url='https://example.test/\u00a0report')),
        ('whitespace report identity', lambda r: r['reports'].update({'\r': copy.deepcopy(r['reports']['sbt-pr-13'])})),
        ('bot output', lambda r: r['reports']['sbt-pr-13']['reporter'].update(kind='bot')),
        ('CI is not human use', lambda r: r['reports']['sbt-pr-13'].update(basis='automation')),
        ('authorship is not use', lambda r: r['reports']['sbt-pr-13'].update(basis='authorship-only')),
        ('hearsay', lambda r: r['reports']['sbt-pr-13'].update(basis='hearsay')),
        ('different purifier', lambda r: r['reports']['sbt-pr-13'].update(repository='nix-purifiers/cargo-purifier')),
        ('native CI source cannot replace a human report', lambda r: r['reports']['sbt-pr-13']['source'].update(kind='native-ci-execution')),
        ('missing primary URL', lambda r: r['reports']['sbt-pr-13']['source'].update(url=None)),
        ('unknown report', lambda r: r['criteria']['firsthandUse'].update(reports=['absent'])),
        ('duplicate report', lambda r: r['criteria']['firsthandUse'].update(reports=['sbt-pr-13', 'sbt-pr-13'])),
        ('private original in public record', lambda r: r['reports']['sbt-pr-13'].update(privateOriginal='PRIVATE_ORIGINAL')),
        ('ongoing inferred from two dated reports', lambda r: r['criteria']['ongoingUse'].update(state='met', reports=['sbt-pr-13', 'sbt-pr-15'], gap=None, confidenceReason='Two sample checks alone.')),
    ]:
        bad = copy.deepcopy(original); edit(bad); yield name, bad, False
    for value in ['ongoing-use-fixture', '/home/private/report', 'https://private.example/transcript']:
        candidate = copy.deepcopy(private); candidate['reports']['sbt-pr-13']['source']['reference'] = value
        yield 'direct provenance '+value, candidate, '/' not in value
    ongoing = copy.deepcopy(original)
    ongoing['reports']['sbt-pr-13']['claims'].append('ongoing-use')
    ongoing['reports']['sbt-pr-13']['scope'] = 'Synthetic fixture: the person explicitly reports continuing real use.'
    ongoing['criteria']['ongoingUse'].update(state='met', reports=['sbt-pr-13'], gap=None, confidenceReason='Synthetic explicit continuing-use context; no user-count or duration cutoff.')
    yield 'qualitative ongoing-use fixture', ongoing, True
    consumer = copy.deepcopy(original)
    consumer['criteria']['ongoingUse'].update(state='met', reports=[], gap=None,
        confidenceReason='Synthetic attributable consumer history supports continuing actual usage.',
        usageContexts=[{'repository': REPOSITORY, 'kind': 'maintained-consumer-history', 'source': {'kind': 'public-primary-url', 'url': 'https://example.test/consumer/history', 'reference': None},
                        'scope': 'Synthetic fixture: maintained consumer uses this purifier in continuing project work.',
                        'attribution': 'Synthetic attributable consumer maintenance history.', 'reviewedAt': '2026-11-07'}])
    yield 'ongoing use from attributable maintained consumer history', consumer, True
    private_context = copy.deepcopy(consumer)
    private_context['criteria']['ongoingUse']['usageContexts'][0]['source'] = {'kind': 'private-context', 'url': None, 'reference': 'private-consumer-context-1'}
    yield 'private consumer context has no public URL', private_context, True
    bad_context = copy.deepcopy(consumer); bad_context['criteria']['ongoingUse']['usageContexts'][0]['kind'] = 'ci-success'
    yield 'CI status is not consumer use context', bad_context, False
    borrowed = copy.deepcopy(consumer); borrowed['criteria']['ongoingUse']['usageContexts'][0]['repository'] = 'nix-purifiers/cargo-purifier'
    yield 'consumer context belongs to another purifier', borrowed, False
    no_reason = copy.deepcopy(ongoing); no_reason['criteria']['ongoingUse']['confidenceReason'] = None
    yield 'ongoing review needs a reason', no_reason, False


class HumanUseTests(unittest.TestCase):
    def test_review_cases(self):
        for name, value, expected in cases():
            with self.subTest(name=name):
                if expected: validate_review(REPOSITORY, value)
                else:
                    with self.assertRaises(ValueError): validate_review(REPOSITORY, value)

    def test_private_original_is_not_exported_or_rendered(self):
        private = [value for name, value, ok in cases() if name.startswith('private maintainer')][0]
        record = private['reports']['sbt-pr-13']
        exported = public_report({'public': record, 'private': {'statement': 'PRIVATE_STATEMENT', 'identity': 'PRIVATE_IDENTITY', 'path': '/private/transcript'}})
        self.assertEqual(exported, record)
        rendered = render_reports(REPOSITORY, private)
        for secret in ('PRIVATE_STATEMENT', 'PRIVATE_IDENTITY', '/private/transcript', 'supplied-report-1'):
            self.assertNotIn(secret, json.dumps(exported) if secret != 'supplied-report-1' else rendered)
        self.assertIn('reviewed direct attestation', rendered)

    def test_not_met_automation_record_is_not_labelled_human(self):
        value = fixture()
        value['reports']['sbt-pr-13']['reporter'].update(kind='bot', publicLabel=None)
        value['criteria']['firsthandUse'].update(state='not-met', gap='The available report does not establish human use.')
        self.assertNotIn('Human reporter', render_reports(REPOSITORY, value))

    def test_review_justification_and_evidence_gaps_are_rendered(self):
        value = fixture()
        self.assertIn(value['criteria']['ongoingUse']['gap'], render_reports(REPOSITORY, value))
        context = [value for name, value, ok in cases() if name == 'ongoing use from attributable maintained consumer history'][0]
        rendered = render_reports(REPOSITORY, context)
        self.assertIn(context['criteria']['ongoingUse']['confidenceReason'], rendered)
        self.assertIn('Primary use context', rendered)

    def test_tier_three_requires_human_use_and_tier_one_needs_ongoing_use(self):
        technical = {key: {'state': 'met'} for key in TECHNICAL_CRITERIA}
        missing = dict(technical, firsthandUse={'state': 'not-met'}, ongoingUse={'state': 'not-met'})
        self.assertEqual(best_tier(3, missing, True), 4)
        first = dict(missing, firsthandUse={'state': 'met'})
        self.assertEqual(best_tier(3, first, True), 2)
        third = dict(first, goodTests={'state': 'not-met'})
        self.assertEqual(best_tier(3, third, True), 3)
        self.assertEqual(best_tier(3, dict(first, ongoingUse={'state': 'met'}), True), 1)
        self.assertEqual(best_tier(3, first, False), 4)
        self.assertIsNone(best_tier(3, dict(first, evaluation={'state': 'not-met'}), True))

    def test_legacy_tiers_are_explicitly_version_two(self):
        technical = {key: {'state': 'met'} for key in TECHNICAL_CRITERIA}
        self.assertEqual(best_tier(2, technical, True), 1)
        self.assertEqual(best_tier(3, technical, True), 4)
        with self.assertRaises(ValueError): best_tier(True, technical, True)


if __name__ == '__main__':
    unittest.main()
