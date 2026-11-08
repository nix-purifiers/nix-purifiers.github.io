import copy
import json
from pathlib import Path
import unittest

from human_use_evidence import canonical_repository, public_report, render_reports, validate_review
from quality_policy import TECHNICAL_CRITERIA, best_tier

REPOSITORY = 'nix-purifiers/sbt-purifier'


def fixture():
    return json.loads((Path(__file__).parent / 'fixtures/human-use/sbt-firsthand.json').read_text())


def ongoing_user(status='maintainer'):
    return {'publicLabel': None, 'maintainerStatus': status,
            'statusBasis': ({'summary': 'Synthetic reviewed role basis for the actual ongoing-use subject.',
                             'source': {'kind': 'public-primary-url', 'url': 'https://example.test/maintainer-role', 'reference': None}}
                            if status != 'unknown' else None),
            'useScope': 'Synthetic fixture: this subject continues using the purifier in actual project work.'}


def consumer_project(slug='project-one', url=None, project_path=None):
    url = url or 'https://code.example/consumers/' + slug
    base = canonical_repository(url)
    identity = base + ('#' + project_path.lower() if project_path else '')
    def proof(path, **extra):
        return {'projectIdentity': identity, 'sourceUrl': base + path,
                'summary': 'Synthetic reviewed primary evidence scoped to this consumer project.', **extra}
    return {'repository': REPOSITORY, 'canonicalIdentity': identity, 'publicRepository': url,
            'projectPath': project_path, 'identityBasis': 'Synthetic distinct real consumer-project identity review, not a fixture, alias or copy.',
            'kind': 'external-open-source-consumer', 'reviewedAt': '2026-11-08',
            'vitalityConfidence': 'Synthetic reviewed confidence from actual consumer maintenance and integration context, without a cadence cutoff.',
            'externalAdoption': {'projectIdentity': identity, 'status': 'reviewed-beyond-maintainer',
                'source': {'kind': 'public-primary-url', 'url': base + '/README', 'reference': None},
                'summary': 'Synthetic reviewed adoption beyond the purifier maintainer.'},
            'openSourceBasis': proof('/LICENSE'),
            'integration': proof('/src/' + (project_path + '/' if project_path else '') + 'flake.nix', kind='actual-purifier-integration'),
            'activityMonitoring': [proof('/commits/' + (project_path or 'main'), kind='maintenance-history')]}


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
    ongoing['reports']['sbt-pr-13']['ongoingUsers'] = [ongoing_user()]
    ongoing['reports']['sbt-pr-13']['scope'] = 'Synthetic fixture: the maintainer reports continuing real use.'
    ongoing['reports']['sbt-pr-13']['source']['url'] = 'https://example.test/maintainer-use'
    ongoing['criteria']['ongoingUse'].update(state='met', reports=['sbt-pr-13'], gap=None,
        confidenceReason='Synthetic reviewed maintainer use and two real external OSS consumers with actual integration and signs of life.',
        consumerProjects=[consumer_project(), consumer_project('project-two')])
    yield 'maintainer use plus two qualified live OSS projects', ongoing, True
    for label, edit in [
        ('maintainer ongoing use alone is insufficient', lambda r: r['criteria']['ongoingUse'].update(consumerProjects=[])),
        ('one consumer project is insufficient', lambda r: r['criteria']['ongoingUse'].update(consumerProjects=[consumer_project()])),
        ('two consumer projects without ongoing maintainer use', lambda r: r['reports']['sbt-pr-13'].update(ongoingUsers=[ongoing_user('non-maintainer')])),
        ('contributor or MEMBER does not prove ongoing maintainer status', lambda r: r['reports']['sbt-pr-13'].update(ongoingUsers=[ongoing_user('unknown')])),
        ('maintainer role needs a reviewed basis', lambda r: r['reports']['sbt-pr-13']['ongoingUsers'][0].update(statusBasis=None)),
        ('fixture is not a real consumer', lambda r: r['criteria']['ongoingUse']['consumerProjects'][0].update(kind='fixture')),
        ('demo is not a real consumer', lambda r: r['criteria']['ongoingUse']['consumerProjects'][0].update(kind='demo')),
        ('copy is not a real consumer', lambda r: r['criteria']['ongoingUse']['consumerProjects'][0].update(kind='copy')),
        ('name catalogue is not purifier integration', lambda r: r['criteria']['ongoingUse']['consumerProjects'][0]['integration'].update(kind='name-only')),
        ('CI alone does not establish signs of life', lambda r: r['criteria']['ongoingUse']['consumerProjects'][0]['activityMonitoring'][0].update(kind='ci-only')),
        ('stars alone do not establish signs of life', lambda r: r['criteria']['ongoingUse']['consumerProjects'][0]['activityMonitoring'][0].update(kind='stars-only')),
        ('downloads alone do not establish signs of life', lambda r: r['criteria']['ongoingUse']['consumerProjects'][0]['activityMonitoring'][0].update(kind='downloads-only')),
        ('consumer repository URL cannot hide whitespace in query', lambda r: r['criteria']['ongoingUse']['consumerProjects'][0].update(publicRepository='https://code.example/consumers/project-one?ignored=\u00a0')),
        ('consumer license needs primary basis', lambda r: r['criteria']['ongoingUse']['consumerProjects'][0]['openSourceBasis'].update(sourceUrl='')),
        ('consumer integration cannot borrow another project', lambda r: r['criteria']['ongoingUse']['consumerProjects'][0]['integration'].update(sourceUrl='https://code.example/other/project/flake.nix')),
        ('activity monitoring cannot borrow another project', lambda r: r['criteria']['ongoingUse']['consumerProjects'][0]['activityMonitoring'][0].update(projectIdentity='https://code.example/other/project')),
        ('vitality confidence needs a reviewed reason', lambda r: r['criteria']['ongoingUse']['consumerProjects'][0].update(vitalityConfidence='')),
        ('ongoing review needs a confidence reason', lambda r: r['criteria']['ongoingUse'].update(confidenceReason=None)),
    ]:
        bad = copy.deepcopy(ongoing); edit(bad); yield label, bad, False
    duplicate = copy.deepcopy(ongoing)
    duplicate['criteria']['ongoingUse']['consumerProjects'] = [consumer_project(url='https://github.com/Example/Consumer'), consumer_project(url='https://www.github.com/example/consumer.git/')]
    yield 'case clone-suffix and host aliases cannot count twice', duplicate, False
    repeated = copy.deepcopy(ongoing); repeated['criteria']['ongoingUse']['consumerProjects'] = [consumer_project(), consumer_project()]
    yield 'repeated identical project cannot count twice', repeated, False
    private_use = copy.deepcopy(ongoing)
    private_use['reports']['sbt-pr-13']['source'] = {'kind': 'direct-attestation', 'url': None, 'reference': 'supplied-ongoing-maintainer-use'}
    private_use['reports']['sbt-pr-13']['ongoingUsers'][0]['statusBasis']['source'] = {'kind': 'private-context', 'url': None, 'reference': 'supplied-role-context'}
    yield 'private maintainer use plus two public OSS consumers can qualify', private_use, True
    context = copy.deepcopy(original)
    context['criteria']['ongoingUse'].update(state='met', reports=[], gap=None,
        confidenceReason='Synthetic credible maintainer ongoing context with two monitored OSS consumers.',
        consumerProjects=[consumer_project(), consumer_project('project-two')],
        usageContexts=[{'repository': REPOSITORY, 'kind': 'supplied-usage-context',
            'source': {'kind': 'private-context', 'url': None, 'reference': 'maintainer-use-context'},
            'scope': 'Synthetic context establishes continuing actual maintainer use.',
            'attribution': 'Synthetic reviewed context, not author membership inferred as use.',
            'reviewedAt': '2026-11-08', 'ongoingUsers': [ongoing_user()]}])
    yield 'maintainer ongoing context and two consumers needs no extra report quote', context, True
    oneoff = copy.deepcopy(original)
    oneoff['reports']['sbt-pr-13']['reporter']['relationship'] = 'other-user'
    oneoff['reports']['sbt-pr-13']['scope'] = 'Synthetic one-off non-maintainer use.'
    oneoff['reports']['sbt-pr-15']['claims'].append('ongoing-use')
    oneoff['reports']['sbt-pr-15']['ongoingUsers'] = [ongoing_user()]
    oneoff['criteria']['ongoingUse'].update(state='met', reports=['sbt-pr-13', 'sbt-pr-15'], gap=None,
        confidenceReason='Synthetic one-off external report plus maintainer ongoing use, but no two consumers.')
    yield 'one-off outside report does not replace two consumer projects', oneoff, False
    borrowed_context = copy.deepcopy(context); borrowed_context['criteria']['ongoingUse']['usageContexts'][0]['repository'] = 'nix-purifiers/cargo-purifier'
    yield 'ongoing context belongs to another purifier', borrowed_context, False
    invalid_ci = copy.deepcopy(context); invalid_ci['criteria']['ongoingUse']['usageContexts'][0]['kind'] = 'ci-success'
    yield 'CI status is not a maintainer-use context', invalid_ci, False
    monorepo = copy.deepcopy(ongoing)
    monorepo['criteria']['ongoingUse']['consumerProjects'] = [consumer_project(url='https://code.example/consumers/monorepo', project_path='projects/one'), consumer_project(url='https://code.example/consumers/monorepo', project_path='projects/two')]
    yield 'reviewed distinct monorepo projects can have distinct scoped identities', monorepo, True


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
        context = [value for name, value, ok in cases() if name == 'maintainer ongoing context and two consumers needs no extra report quote'][0]
        rendered = render_reports(REPOSITORY, context)
        self.assertIn(context['criteria']['ongoingUse']['confidenceReason'], rendered)
        self.assertIn('Reviewed private use context', rendered)

    def test_tier_one_requires_maintainer_use_and_two_distinct_real_oss_projects(self):
        values = {name: (value, expected) for name, value, expected in cases()}
        positive = values['maintainer use plus two qualified live OSS projects'][0]
        validate_review(REPOSITORY, positive)
        technical = {key: {'state': 'met'} for key in TECHNICAL_CRITERIA}
        self.assertEqual(best_tier(3, dict(technical, **positive['criteria']), True), 1)
        negative = values['one consumer project is insufficient'][0]
        with self.assertRaisesRegex(ValueError, 'two distinct'): validate_review(REPOSITORY, negative)
        duplicate = values['case clone-suffix and host aliases cannot count twice'][0]
        with self.assertRaisesRegex(ValueError, 'duplicate canonical'): validate_review(REPOSITORY, duplicate)
        self.assertEqual(set(positive['criteria']), {'firsthandUse', 'ongoingUse'})

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
