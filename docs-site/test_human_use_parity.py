import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from human_use_evidence import validate_review
from quality_policy import TECHNICAL_CRITERIA, best_tier, require_current_registry
from test_human_use_evidence import REPOSITORY, cases


@unittest.skipUnless(shutil.which('nix') and os.environ.get('NIXPKGS_LIB'), 'NIXPKGS_LIB is required for Nix parity checks')
class HumanUseParity(unittest.TestCase):
    def evaluate(self, value, expression):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)/'fixture.json'; data.write_text(json.dumps(value))
            expr = ('let lib = import (builtins.toPath '+json.dumps(os.environ['NIXPKGS_LIB'])+'); '
                    'human = import '+str(root/'model/human-use-review.nix')+' { inherit lib; }; '
                    'policy = import '+str(root/'model/quality-policy.nix')+' { inherit lib; }; '
                    'value = builtins.fromJSON (builtins.readFile '+json.dumps(str(data))+'); in '+expression)
            result = subprocess.run(['nix', 'eval', '--impure', '--json', '--expr', expr], check=True, capture_output=True, text=True)
            return json.loads(result.stdout)

    def test_human_report_semantics_match(self):
        for name, value, expected in cases():
            with self.subTest(name=name):
                self.assertEqual(self.evaluate(value, '(builtins.tryEval (builtins.deepSeq (human.validate '+json.dumps(REPOSITORY)+' value) true)).success'), expected)

    def test_production_rejects_legacy_downgrade(self):
        for version in (3, 2, 1, True, 3.0):
            expected = type(version) is int and version == 3
            with self.subTest(version=version):
                if expected: self.assertTrue(require_current_registry(version))
                else:
                    with self.assertRaises(ValueError): require_current_registry(version)
                self.assertEqual(self.evaluate(version, '(builtins.tryEval (policy.requireCurrentRegistry value)).success'), expected)

    def test_actual_production_module_rejects_downgrade_and_missing_human_fields(self):
        root = Path(__file__).resolve().parents[1]
        baseline = json.loads((root / 'model/tiers.json').read_text())
        for mode in ('downgrade', 'empty-downgrade', 'missing-human'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                temp = Path(directory); model = temp / 'model'; model.mkdir()
                for source in (root / 'model').iterdir():
                    if source.name not in ('tiers.nix', 'tiers.json', 'default.nix'):
                        (model / source.name).symlink_to(source, target_is_directory=source.is_dir())
                (model / 'tiers.nix').write_bytes((root / 'model/tiers.nix').read_bytes())
                (model / 'default.nix').write_bytes((root / 'model/default.nix').read_bytes())
                (temp / 'docs-site').symlink_to(root / 'docs-site', target_is_directory=True)
                q = json.loads(json.dumps(baseline['projects']['sbt-purifier']))
                q.pop('humanUseReview')
                for key in ('firsthandUse', 'ongoingUse'): q['criteria'].pop(key)
                (model / 'tiers.json').write_text(json.dumps({'version': 2 if mode in ('downgrade', 'empty-downgrade') else 3,
                    'projects': {} if mode == 'empty-downgrade' else {'sbt-purifier': q}}))
                expr = ('let lib = import (builtins.toPath '+json.dumps(os.environ['NIXPKGS_LIB'])+'); '
                        'q = (lib.evalModules { modules = [ '+str(model/'tiers.nix')+
                        ' { options.repository = lib.mkOption { type = lib.types.str; }; '
                        'config.repository = "nix-purifiers/sbt-purifier"; } ]; }).config.quality; '
                        'in (builtins.tryEval (builtins.deepSeq q true)).success')
                if mode == 'empty-downgrade':
                    expr = ('let lib = import (builtins.toPath '+json.dumps(os.environ['NIXPKGS_LIB'])+'); '
                            'q = (import '+str(model)+' { inherit lib; }).qualityTiers; '
                            'in (builtins.tryEval (builtins.deepSeq q true)).success')
                result = subprocess.run(['nix', 'eval', '--impure', '--json', '--expr', expr], check=True, capture_output=True, text=True)
                self.assertFalse(json.loads(result.stdout))

    def test_tier_gates_match(self):
        technical = {key: {'state': 'met'} for key in TECHNICAL_CRITERIA}
        for first, ongoing, samples in [(False, False, True), (True, False, True), (True, True, True), (True, True, False)]:
            value = {'criteria': dict(technical, firsthandUse={'state': 'met' if first else 'not-met'}, ongoingUse={'state': 'met' if ongoing else 'not-met'}), 'hasSample': samples}
            with self.subTest(value=value):
                self.assertEqual(self.evaluate(value, 'policy.bestTier 3 value.criteria value.hasSample'), best_tier(3, value['criteria'], samples))
