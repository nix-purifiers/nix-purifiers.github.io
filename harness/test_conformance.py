import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from conformance import run_suite
from runtime import Executable, UnsupportedOperation, run


@unittest.skipUnless(shutil.which('nix'), 'Nix is needed to evaluate the tool model')
class ModelHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent.parent
        def evaluate(output):
            return json.loads(subprocess.run(['nix', 'eval', '--json', f'.#{output}'],
                              cwd=cls.root, check=True, capture_output=True, text=True).stdout)
        cls.catalog = evaluate('catalog')
        cls.plans = evaluate('testPlans')

    def test_sbt_record_drives_invocation_without_a_documentation_record(self):
        model = self.catalog['sbt-purifier']
        calls = []
        def sbt(invocation, **kwargs):
            calls.append(invocation)
            return subprocess.CompletedProcess(invocation.arguments, 0)
        context = {'project_root': '/fixture', 'lockfile': '/external/sbt.json'}
        run(model, 'lock', {'sbt': sbt}, context)
        self.assertEqual(calls[0].arguments, ['-batch', 'nixLock'])
        self.assertEqual(calls[0].environment, {'SBT_PURIFIER_LOCKFILE': '/external/sbt.json'})
        run(model, 'update', {'sbt': sbt}, context)
        self.assertEqual(calls[-1].arguments, ['-batch', 'nixLockUpdate'])
        with self.assertRaises(UnsupportedOperation):
            run(model, 'named-update', {'sbt': sbt}, context, arguments=['library'])
        self.assertNotIn('sections', model)

    def test_missing_fixture_glue_is_blocked_and_cannot_pass(self):
        report = run_suite(self.catalog['ant-purifier'], self.plans['ant-purifier'], {}, {}, {})
        self.assertEqual(report['results']['relock']['status'], 'blocked')
        self.assertFalse(report['complete'])

    def test_shared_test_detects_behavior_that_disagrees_with_the_model(self):
        model = self.catalog['ant-purifier']
        plan = copy.deepcopy(self.plans['ant-purifier'])
        plan['cases'] = {'relock': plan['cases']['relock']}
        selected = {'library': '1.0'}
        def broken_resolver(invocation, **kwargs):
            selected['library'] = upstream['library']
            return subprocess.CompletedProcess(invocation.arguments, 0)
        upstream = {'library': '1.0'}
        fixtures = {'locked-selections': lambda: dict(selected),
                    'advance-upstream': lambda: upstream.update(library='2.0')}
        report = run_suite(model, plan, {'ant-purifier': broken_resolver}, fixtures,
                           {'project_root': '/fixture', 'lockfile': '/fixture/lock.json'})
        self.assertEqual(report['results']['relock']['status'], 'failed')
        self.assertIn('pin-retention', report['results']['relock']['reason'])

    def test_named_update_requires_names_before_calling_glue(self):
        with self.assertRaisesRegex(ValueError, 'at least 1'):
            run(self.catalog['ant-purifier'], 'named-update', {'ant-purifier': lambda x: None}, {})

    def test_cli_uses_the_sbt_recipe_and_preserves_native_exit_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / 'catalog.json'
            catalog.write_text(json.dumps(self.catalog))
            provider = root / 'provider.json'
            provider.write_text(json.dumps({
                'capabilities': {'sbt': {'command': [sys.executable, '-c',
                    'import json,sys; print(json.dumps(sys.argv[1:])); sys.exit(7)']}},
                'context': {'project_root': str(root), 'lockfile': str(root / 'sbt.json')},
            }))
            result = subprocess.run([sys.executable, str(self.root / 'harness/cli.py'),
                '--catalog', str(catalog), '--project', 'sbt-purifier',
                '--provider', str(provider), 'lock'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertEqual(json.loads(result.stdout), ['-batch', 'nixLock'])

    @unittest.skipUnless(os.environ.get('PURIFIER_DOCKER_SOURCE'), 'Supply the Docker integration source to test its real resolver')
    def test_real_docker_resolver_obeys_the_model_with_bespoke_fixture_glue(self):
        source = Path(os.environ['PURIFIER_DOCKER_SOURCE']).resolve()
        with tempfile.TemporaryDirectory(prefix='purifier-conformance-') as directory:
            base = Path(directory)
            project = base / 'project'
            shutil.copytree(source / 'examples/hello', project,
                            ignore=shutil.ignore_patterns('.docker-purifier', 'dependencies'))
            lockfile = project / 'docker-purifier.lock.json'
            original = json.loads(lockfile.read_text())['images']
            upstream = base / 'upstream.json'
            upstream.write_text(json.dumps(original))
            # This is the bespoke fixture capability: exercise the real CLI and
            # locking algorithm against a controllable registry response.
            # It doesn't replace the algorithm's pin-retention behavior.
            shim = ('import json, os, sys\n'
                    'from pathlib import Path\n'
                    'from docker_purifier import cli\n'
                    'cli.resolve = lambda ref, platforms, pin=None: '
                    'json.loads(Path(os.environ["PURIFIER_FIXTURE_UPSTREAM"]).read_text())[ref]\n'
                    'cli.main()\n')
            capability = Executable([sys.executable, '-c', shim], {
                'PYTHONPATH': str(source), 'PURIFIER_FIXTURE_UPSTREAM': str(upstream)})
            def selections():
                return {ref: image['sourceDigest'] for ref, image in json.loads(lockfile.read_text())['images'].items()}
            def advance():
                newer = copy.deepcopy(original)
                for image in newer.values():
                    image['sourceDigest'] = 'sha256:' + 'b' * 64
                upstream.write_text(json.dumps(newer))
            report = run_suite(self.catalog['docker-purifier'], self.plans['docker-purifier'],
                               {'docker-purifier': capability},
                               {'locked-selections': selections, 'advance-upstream': advance},
                               {'project_root': str(project), 'lockfile': str(lockfile)})
            self.assertEqual(report['results']['relock']['status'], 'passed', report)
            self.assertFalse(report['complete'])  # Other facts still need coverage.


if __name__ == '__main__':
    unittest.main()
