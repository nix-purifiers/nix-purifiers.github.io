"""Catalog/source drift must never become a successful runtime test."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from compatibility_evidence import inputs, input_digest, validate_registry, audit_source, verify_ci


class Evidence(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        for name, content in {'main.py': 'print(42)\n', 'tests/native.py': 'assert True\n',
                              '.github/workflows/check.yml': 'name: native\n', 'README.md': 'docs\n'}.items():
            p = self.root/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content)
        self.commit()
        self.revision = self.git('rev-parse', 'HEAD').strip()
        files = inputs(self.root, self.revision)
        self.point = dict(id='native-point', components=[dict(role='project-runtime', name='Runtime', version='1.0')],
            system='x86_64-linux', operations=['native-install-offline'], sourceRevision=self.revision,
            evidence=[f'https://github.com/nix-purifiers/example/blob/{self.revision}/tests/native.py',
                      'https://github.com/nix-purifiers/example/actions/runs/123/job/456'], notes=[])
        self.review = dict(sourceRevision=self.revision, files=files, inputDigest=input_digest(files),
            pointIds=['native-point'], ci=[dict(runId=123, attempt=1, headRevision=self.revision,
                inputDigest=input_digest(files), jobs=[dict(id=456, name='native', system='x86_64-linux', conclusion='success')])])
        self.registry = dict(version=1, projects={'example': dict(testedPoints=[self.point], reviews=[self.review])})
        self.catalog = {'example': {'repository': 'nix-purifiers/example', 'compatibility': {
            'defaults': [], 'projectSelections': [], 'testedPoints': [self.point], 'supportedRanges': [], 'limitations': []}}}

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True)

    def commit(self):
        self.git('add', '.'); self.git('commit', '-qm', 'fixture')

    def test_export_cannot_drop_or_change_reviewed_points(self):
        validate_registry(self.registry, self.catalog)
        for mutation in ['drop', 'change']:
            catalog = copy.deepcopy(self.catalog)
            if mutation == 'drop': catalog['example']['compatibility']['testedPoints'] = []
            else: catalog['example']['compatibility']['testedPoints'][0]['operations'] += ['native-publish']
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_registry(self.registry, catalog)

    def test_canceled_ci_missing_platform_and_unbound_tests_fail(self):
        for mutation in ['canceled', 'platform', 'test', 'digest']:
            registry = copy.deepcopy(self.registry); review = registry['projects']['example']['reviews'][0]
            if mutation == 'canceled': review['ci'][0]['jobs'][0]['conclusion'] = 'cancelled'
            elif mutation == 'platform': review['ci'][0]['jobs'][0]['system'] = 'aarch64-linux'
            elif mutation == 'test': del review['files']['tests/native.py']
            else: review['ci'][0]['inputDigest'] = '0'*64
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_registry(registry, self.catalog)

    def test_source_fixture_workflow_and_new_implementation_drift(self):
        for name in ['main.py', 'tests/native.py', '.github/workflows/check.yml', 'new.py']:
            with self.subTest(name=name):
                self.git('reset', '--hard', self.revision)
                (self.root/name).write_text('changed\n'); self.commit()
                result = audit_source(self.root, self.review)
                self.assertEqual(result['status'], 'review-needed')
                self.assertIn(name, result['changedFiles'])
        self.git('reset', '--hard', self.revision)

    def test_documentation_change_is_not_a_new_runtime_pass(self):
        (self.root/'README.md').write_text('new docs\n'); self.commit()
        result = audit_source(self.root, self.review)
        self.assertEqual(result['status'], 'inputs-match')
        self.assertNotIn('passed', result.values())
        self.assertNotEqual(result['currentRevision'], self.revision)

    def test_executable_mode_changes_require_review(self):
        self.git('update-index', '--chmod=+x', 'main.py')
        self.git('commit', '-qm', 'change executable mode')
        result = audit_source(self.root, self.review, clean=False)
        self.assertEqual(result['status'], 'review-needed')
        self.assertIn('main.py', result['changedFiles'])

    def test_dirty_checkout_is_not_silently_audited_as_clean(self):
        (self.root/'main.py').write_text('uncommitted\n')
        with self.assertRaisesRegex(ValueError, 'uncommitted'):
            audit_source(self.root, self.review)

    def test_remote_ci_must_match_the_recorded_attempt_source_and_successful_job(self):
        run = dict(head_sha=self.revision, run_attempt=1)
        job = dict(run_id=123, head_sha=self.revision, name='native',
                   status='completed', conclusion='success')
        original = subprocess.check_output
        for mutation in ['none', 'cancelled', 'attempt', 'head', 'job-name', 'ci-inputs']:
            observed_run, observed_job = copy.deepcopy(run), copy.deepcopy(job)
            review = copy.deepcopy(self.review)
            if mutation == 'cancelled': observed_job['conclusion'] = 'cancelled'
            elif mutation == 'attempt': observed_run['run_attempt'] = 2
            elif mutation == 'head': observed_run['head_sha'] = '0'*40
            elif mutation == 'job-name': observed_job['name'] = 'unrelated'
            elif mutation == 'ci-inputs': review['inputDigest'] = '0'*64
            def response(args, **kwargs):
                if args[0] == 'gh':
                    return json.dumps(observed_job if '/actions/jobs/' in args[-1] else observed_run)
                return original(args, **kwargs)
            with self.subTest(mutation=mutation), patch('compatibility_evidence.subprocess.check_output', side_effect=response):
                if mutation == 'none': verify_ci('nix-purifiers/example', review, self.root)
                else:
                    with self.assertRaises(ValueError):
                        verify_ci('nix-purifiers/example', review, self.root)


if __name__ == '__main__': unittest.main()
