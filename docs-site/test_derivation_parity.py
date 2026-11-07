"""Run shared receipt fixtures through Python and Nix semantic validators.

Set NIXPKGS_LIB to the lib directory of the site's locked nixpkgs-lib input.
"""
import copy
import json
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from derivation_evidence import validate_review
from test_derivation_evidence import fixture


@unittest.skipUnless(os.environ.get('NIXPKGS_LIB'), 'NIXPKGS_LIB is required for Nix parity checks')
class ParityTests(unittest.TestCase):
    def test_shared_semantic_fixtures(self):
        fixtures = [('native-success', fixture(), True)]
        for key, value in [('revision', 'b' * 40), ('repository', 'foreign/repo'),
                           ('outputNarHashes', {}), ('drvPath', '/nix/store/bad')]:
            q = fixture()
            q['derivations']['sample'][key] = value
            fixtures.append((key, q, False))
        for key, value in [('sourceRevision', 'b' * 40), ('outputs', {}),
                           ('sdkVersions', {'example': '9'}), ('executedSystem', 'aarch64-darwin'),
                           ('receipt', 'https://example.test/\ninvalid')]:
            q = fixture()
            q['derivations']['sample']['build'][key] = value
            fixtures.append(('build-' + key, q, False))
        for build in (None, 'failed'):
            q = fixture()
            e = q['derivations']['sample']
            e['outputNarHashes'] = {}
            if build is None:
                e['build'] = None
            else:
                e['build'].update(status='failed', outputs={}, outputNarHashes={})
            for key in ('linux', 'oneVersion'):
                q['criteria'][key].update(state='not-met', gap='No native output realized.')
            fixtures.append(('honest-' + str(build), copy.deepcopy(q), True))
            if build is None:
                e['evaluation'] = None
                fixtures.append(('bare-declared-drv', copy.deepcopy(q), False))
        for key, value in [('state', 'unreviewed'), ('derivations', ['missing']), ('gap', None)]:
            q = fixture()
            q['criteria']['goodTests'][key] = value
            fixtures.append(('criterion-' + key, q, False))
        sample = {'name': 'sample', 'upstream': {'repository': 'https://example.test/upstream', 'revision': 'd' * 40, 'sourceNarHash': 'sha256-' + 'D' * 43 + '='}, 'derivations': ['sample']}
        q = fixture()
        q['sampleBuilds'] = [sample]
        q['derivations']['sample']['sampleSources'] = [copy.deepcopy(sample['upstream'])]
        q['derivations']['sample']['build']['sampleSources'] = [copy.deepcopy(sample['upstream'])]
        fixtures.append(('bound-sample', copy.deepcopy(q), True))
        local = copy.deepcopy(q)
        local_source = {'repository': 'https://github.com/nix-purifiers/example-purifier', 'revision': 'a' * 40, 'sourceNarHash': local['derivations']['sample']['sourceNarHash']}
        local['sampleBuilds'][0]['upstream'] = copy.deepcopy(local_source)
        local['derivations']['sample']['sampleSources'] = [copy.deepcopy(local_source)]
        local['derivations']['sample']['build']['sampleSources'] = [copy.deepcopy(local_source)]
        fixtures.append(('local-fixture-sample', local, True))
        changed = copy.deepcopy(q)
        changed['sampleBuilds'][0]['upstream']['revision'] = 'e' * 40
        fixtures.append(('foreign-sample-source', changed, False))
        q['sampleBuilds'][0]['derivations'] = ['missing']
        fixtures.append(('unbound-sample', q, False))
        q = fixture()
        e = q['derivations']['sample']
        expression = '{ pkgs }: pkgs.test'
        e['check'] = {'kind': 'expression', 'value': expression, 'replay': {'artifactUrl': 'https://example.test/replay.tar', 'artifactSha256': 'e' * 64, 'expressionSha256': hashlib.sha256(expression.encode()).hexdigest(), 'arguments': {'pkgs': 'locked-nixpkgs'}}}
        e['evaluation']['check'] = copy.deepcopy(e['check'])
        fixtures.append(('replay-expression', copy.deepcopy(q), True))
        e['check']['replay']['expressionSha256'] = 'f' * 64
        e['evaluation']['check'] = copy.deepcopy(e['check'])
        fixtures.append(('bad-expression-hash', q, False))
        model = Path(__file__).resolve().parents[1] / 'model/derivation-review.nix'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.json'
            for name, q, expected in fixtures:
                with self.subTest(name=name):
                    try:
                        validate_review('nix-purifiers/example-purifier', 'a' * 40, q)
                        python_valid = True
                    except ValueError:
                        python_valid = False
                    path.write_text(json.dumps(q))
                    expr = ('let lib = import ' + os.environ['NIXPKGS_LIB'] + '; '
                            'validator = import ' + str(model) + ' { inherit lib; }; '
                            'in validator.validate "nix-purifiers/example-purifier" "' + 'a' * 40 + '" '
                            '(builtins.fromJSON (builtins.readFile ' + str(path) + '))')
                    result = subprocess.run(['nix-instantiate', '--eval', '--strict', '--json', '--expr', expr], capture_output=True, text=True, timeout=60)
                    self.assertEqual(python_valid, expected, name)
                    self.assertEqual(result.returncode == 0, expected, result.stderr)
