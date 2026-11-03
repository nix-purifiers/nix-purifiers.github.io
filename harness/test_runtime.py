import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from runtime import CapabilityUnavailable, Executable, UnsupportedOperation, run


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.model = {'repository': 'example/sbt-purifier', 'operations': {
            'lock': {'capability': 'sbt', 'arguments': ['-batch', {'splice': 'arguments'}, 'nixLock'],
                     'environment': {'SBT_PURIFIER_LOCKFILE': {'binding': 'lockfile'}},
                     'directory': {'binding': 'project_root'}},
            'update': {'capability': 'sbt', 'arguments': ['-batch', 'nixLockUpdate'],
                       'environment': {}, 'directory': {'binding': 'project_root'}},
        }}

    def test_recipe_drives_real_process_arguments_environment_and_directory(self):
        with tempfile.TemporaryDirectory(prefix='purifier harness ') as directory:
            root = Path(directory)
            probe = root / 'observe.py'
            probe.write_text('import json, os, sys\nprint(json.dumps({"arguments": sys.argv[1:], '
                             '"lockfile": os.environ["SBT_PURIFIER_LOCKFILE"], "cwd": os.getcwd()}))\n')
            context = {'project_root': str(root), 'lockfile': str(root / 'external lock.json')}
            result = run(self.model, 'lock', {'sbt': Executable([sys.executable, str(probe)])},
                         context, arguments=['set version := "$(touch SHOULD_NOT_EXIST)"'], capture_output=True)
            observed = json.loads(result.stdout)
            self.assertEqual(observed['arguments'], ['-batch', 'set version := "$(touch SHOULD_NOT_EXIST)"', 'nixLock'])
            self.assertEqual(observed['lockfile'], context['lockfile'])
            self.assertEqual(observed['cwd'], str(root))
            self.assertFalse((root / 'SHOULD_NOT_EXIST').exists())

    def test_missing_capability_is_not_unsupported_behavior(self):
        with self.assertRaises(CapabilityUnavailable):
            run(self.model, 'lock', {}, {})
        with self.assertRaises(UnsupportedOperation):
            run(self.model, 'named-update', {}, {})

    def test_extra_arguments_and_missing_context_fail_before_invocation(self):
        calls = []
        def capability(invocation, **kwargs):
            calls.append(invocation)
        with self.assertRaises(ValueError):
            run(self.model, 'update', {'sbt': capability}, {}, arguments=['package-name'])
        with self.assertRaises(ValueError):
            run(self.model, 'lock', {'sbt': capability}, {'project_root': '.'})
        self.assertEqual(calls, [])

    def test_glue_receives_prepared_invocation_and_exit_status_survives(self):
        calls = []
        def bespoke_glue(invocation, **kwargs):
            calls.append(invocation)
            return subprocess.CompletedProcess(invocation.arguments, 7)
        result = run(self.model, 'update', {'sbt': bespoke_glue}, {'project_root': '/project'})
        self.assertEqual(result.returncode, 7)
        self.assertEqual(calls[0].arguments, ['-batch', 'nixLockUpdate'])


if __name__ == '__main__':
    unittest.main()
