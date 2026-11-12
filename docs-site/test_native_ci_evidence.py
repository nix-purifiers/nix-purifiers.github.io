import copy
import json
import os
import subprocess
from pathlib import Path
import tempfile
import unittest
from native_ci_evidence import retain_native_artifact, validate_native_ci
from receipt_artifacts import retain


class NativeCITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = 'https://example.test/receipts/'
        self.repo, self.rev = 'owner/project', 'a' * 40
        self.drv = '/nix/store/' + 'a' * 32 + '-example.drv'
        self.job = {'id': 123, 'head_sha': self.rev, 'html_url': 'https://github.com/owner/project/actions/runs/1/job/123',
                    'status': 'completed', 'conclusion': 'success', 'steps': [{'number': 5, 'name': 'Run nix flake check -L', 'status': 'completed', 'conclusion': 'success', 'started_at': '2026-11-06T00:00:01Z', 'completed_at': '2026-11-06T00:00:03Z'}]}
        self.log = ('2026-11-06T00:00:00Z Image: ubuntu-24.04-arm\n'
                    '2026-11-06T00:00:00Z repository: owner/project\n'
                    '2026-11-06T00:00:00Z ' + self.rev + '\n'
                    '2026-11-06T00:00:01Z nix flake check -L\n'
                    '2026-11-06T00:00:02Z checking derivation checks.aarch64-linux.sample...\n'
                    '2026-11-06T00:00:02Z derivation evaluated to ' + self.drv + '\n')

    def record(self, job=None, log=None):
        api = 'repos/owner/project/actions/jobs/123'
        refs = []
        for name, capture in [('job', {'command': ['gh', 'api', api], 'exitCode': 0, 'stdout': json.dumps(job or self.job)}),
                              ('log', {'command': ['gh', 'api', api + '/logs'], 'exitCode': 0, 'stdout': self.log if log is None else log})]:
            source = self.root / (name + '.json')
            source.write_text(json.dumps(capture))
            refs.append(retain(source, self.root / 'public', self.base))
        return {'kind': 'native-ci-execution', 'repository': self.repo, 'revision': self.rev,
                'system': 'aarch64-linux', 'check': 'checks.aarch64-linux.sample', 'drvPath': self.drv,
                'predictedOutputs': {}, 'observedOutputs': {}, 'outputNarHashes': None,
                'jobUrl': self.job['html_url'], 'jobArtifact': refs[0], 'logArtifact': refs[1],
                'stepNumber': 5, 'command': 'nix flake check -L', 'runnerImage': 'ubuntu-24.04-arm'}

    def check(self, record):
        try:
            result = validate_native_ci(record, self.root / 'public', self.base)
            error = None
        except ValueError as exc:
            result, error = None, exc
        if os.environ.get('NIXPKGS_LIB'):
            path = self.root / 'variant.json'
            path.write_text(json.dumps(record))
            model = Path(__file__).resolve().parents[1] / 'model/native-ci-evidence.nix'
            expr = ('let lib = import ' + os.environ['NIXPKGS_LIB'] + '; v = import ' + str(model) + ' { inherit lib; }; '
                    'in v.validate ' + json.dumps(str(self.root / 'public')) + ' ' + json.dumps(self.base) +
                    ' (builtins.fromJSON (builtins.readFile ' + str(path) + '))')
            proc = subprocess.run(['nix-instantiate', '--eval', '--strict', '--json', '--expr', expr], capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode == 0, error is None, proc.stderr)
        if error:
            raise error
        return result

    def test_native_success_without_observed_output_nars(self):
        self.check(self.record())
        self.check(self.record(log=self.log.replace('2026-11-06T00:00:02Z derivation evaluated', '2026-11-06T00:00:02Z unpacking pinned source...\n2026-11-06T00:00:02Z derivation evaluated')))

    def test_explicit_sandbox_check_requires_exact_successful_step(self):
        command = 'nix flake check --print-build-logs --keep-going --option sandbox true'
        job = copy.deepcopy(self.job)
        job['steps'][0]['name'] = 'Check the flake'
        log = self.log.replace('nix flake check -L', command)
        record = self.record(job=job, log=log)
        record.update(command=command, stepName='Check the flake')
        self.check(record)
        for bad_log in (log.replace('sandbox true', 'sandbox false'),
                        log.replace(command, command + ' --no-build')):
            with self.subTest(log=bad_log), self.assertRaises(ValueError):
                changed = self.record(job=job, log=bad_log)
                changed.update(command=command, stepName='Check the flake')
                self.check(changed)
        job['steps'][0]['conclusion'] = 'failure'
        changed = self.record(job=job, log=log)
        changed.update(command=command, stepName='Check the flake')
        with self.assertRaises(ValueError):
            self.check(changed)

    def test_exact_bounded_parallel_check_preserves_execution_bindings(self):
        command = 'nix flake check --max-jobs 2 --print-build-logs'
        job = copy.deepcopy(self.job)
        job['steps'][0]['name'] = 'Run ' + command
        log = self.log.replace('nix flake check -L', command)
        record = self.record(job=job, log=log)
        record['command'] = command
        self.check(record)
        changed = copy.deepcopy(record)
        changed['command'] = command.replace('--max-jobs 2', '--max-jobs 3')
        with self.assertRaises(ValueError):
            self.check(changed)
        failed = copy.deepcopy(job)
        failed['steps'][0]['conclusion'] = 'failure'
        changed = self.record(job=failed, log=log)
        changed['command'] = command
        with self.assertRaises(ValueError):
            self.check(changed)
        changed = self.record(job=job, log=log.replace(self.drv, self.drv.replace('example', 'foreign')))
        changed['command'] = command
        with self.assertRaises(ValueError):
            self.check(changed)

    def test_large_log_preserves_literal_source_and_runner_matching(self):
        log = self.log + '2026-11-06T00:00:04Z ' + 'x' * (512 * 1024) + '\n'
        self.check(self.record(log=log))
        for changed in (log.replace(self.rev, 'b' * 40),
                        log.replace('Image: ubuntu-24.04-arm', 'Image: ubuntu-24x04-arm')):
            with self.subTest(changed=changed[:80]):
                with self.assertRaises(ValueError):
                    self.check(self.record(log=changed))

    def test_many_line_step_preserves_late_command_and_rejects_nonmatch(self):
        command = 'nix flake check -L'
        base = self.log.replace('2026-11-06T00:00:01Z ' + command + '\n', '')
        noise = '2026-11-06T00:00:02Z unrelated build output\n' * 120000
        late = base + noise + '2026-11-06T00:00:02Z ' + command + '\n'
        self.check(self.record(log=late))
        with self.assertRaises(ValueError):
            self.check(self.record(log=late.replace(command, 'nix flake check -X')))

    def test_logical_command_continuations_and_separator_boundaries(self):
        command = 'nix flake check -L'
        base = self.log.replace('2026-11-06T00:00:01Z ' + command + '\n', '')
        cases = [
            (['nix flake \\', 'check -L'], True),
            (['nix flake check \\', '-L'], True),
            ([command + '; echo unrelated'], False),
            ([command + ' && echo unrelated'], False),
            (['echo before', command, 'echo after'], True),
            ([''], False),
            (['nix flake \\', '', 'check -L'], False),
        ]
        for lines, accepted in cases:
            log = base + ''.join('2026-11-06T00:00:02Z ' + line + '\n' for line in lines)
            with self.subTest(lines=lines, accepted=accepted):
                if accepted:
                    self.check(self.record(log=log))
                else:
                    with self.assertRaises(ValueError):
                        self.check(self.record(log=log))

    def test_url_only_foreign_source_platform_and_drv_rejected(self):
        for field, value in [('jobArtifact', {}), ('revision', 'b' * 40),
                             ('system', 'aarch64-darwin'), ('drvPath', self.drv.replace('example', 'invented')),
                             ('observedOutputs', {'out': self.drv[:-4]}), ('outputNarHashes', {})]:
            with self.subTest(field=field):
                record = self.record()
                record[field] = value
                with self.assertRaises(ValueError):
                    self.check(record)

    def test_optional_reviewed_sdk_and_sample_annotation_shape(self):
        record = self.record()
        record['sdkVersions'] = {'example': '1.2.3'}
        record['sampleSources'] = [{'repository': 'https://example.test/sample', 'revision': 'b' * 40, 'sourceNarHash': 'sha256-' + 'B' * 43 + '='}]
        self.check(record)
        for field, value in [('sdkVersions', {'example': 12}), ('sdkVersions', {'': '1.2.3'}),
                             ('sampleSources', [{'repository': 'https://example.test/sample', 'revision': 'main', 'sourceNarHash': 'sha256-' + 'B' * 43 + '='}])]:
            invalid = copy.deepcopy(record)
            invalid[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.check(invalid)

    def test_raw_job_metadata_grouped_log_and_custom_step(self):
        self.job.update(name='flake-check (macos-latest)', url='https://api.github.com/repos/owner/project/actions/jobs/123')
        self.job['steps'][0]['name'] = 'Build the checks'
        raw = self.log.replace('ubuntu-24.04-arm', 'macos-26-arm64').replace('aarch64-linux', 'aarch64-darwin').replace('nix flake check -L', '^[[36;1mnix flake check --print-build-logs^[[0m')
        log_path = self.root / 'actual.log'
        log_path.write_text('\n'.join(self.job['name'] + '\tUNKNOWN STEP\t' + line for line in raw.splitlines()) + '\n')
        record = self.record()
        record.update(system='aarch64-darwin', check='checks.aarch64-darwin.sample', runnerImage='macos-26-arm64',
                      command='nix flake check --print-build-logs', stepName='Build the checks', logJobName=self.job['name'],
                      sourceNarHash='sha256-' + 'A' * 43 + '=')
        record['logArtifact'] = retain_native_artifact(log_path, self.root / 'public', self.base, 'text')
        for format, value in [('job-json', self.job), ('jobs-json', {'jobs': [self.job]})]:
            path = self.root / 'actual-job.json'
            path.write_text(json.dumps(value))
            record['jobArtifact'] = retain_native_artifact(path, self.root / 'public', self.base, format)
            self.check(record)
        record['logJobName'] = 'unrelated-job'
        with self.assertRaises(ValueError):
            self.check(record)

    def test_successful_step_survives_later_job_failure(self):
        job = copy.deepcopy(self.job)
        job['conclusion'] = 'failure'
        job['steps'].append({'number': 6, 'name': 'Later lifecycle test', 'status': 'completed', 'conclusion': 'failure', 'started_at': '2026-11-06T00:00:04Z', 'completed_at': '2026-11-06T00:00:05Z'})
        record = self.record(job)
        record['jobConclusion'] = 'failure'
        self.check(record)
        for missing in ('omit', 'null'):
            changed = copy.deepcopy(record)
            if missing == 'omit':
                del changed['jobConclusion']
            else:
                changed['jobConclusion'] = None
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                self.check(changed)
        record['jobConclusion'] = 'success'
        with self.assertRaises(ValueError):
            self.check(record)

    def script_record(self):
        source = self.root / 'generator.py'
        source.write_text("# Synthetic structural fixture; not real execution evidence\nsubprocess.run(['nix', 'build', '--expr', expression], check=True)\n")
        lock = self.root / 'flake.lock'
        lock.write_text(json.dumps({'nodes': {}, 'version': 7}))
        script_ref = retain_native_artifact(source, self.root / 'public', self.base, 'text')
        lock_ref = retain_native_artifact(lock, self.root / 'public', self.base, 'json')
        command = "python3 tests/sdk-native.py '5.5'"
        job = copy.deepcopy(self.job)
        job['run_id'] = 321
        job['steps'][0]['name'] = 'Native SDK test'
        log = self.log.replace('nix flake check -L', command)
        log = log[:log.index('2026-11-06T00:00:02Z checking derivation')] + "2026-11-06T00:00:02Z building '" + self.drv + "'...\n2026-11-06T00:00:02Z PASS native SDK 5.5.1\n"
        record = self.record(job, log)
        record.update(command=command, stepName='Native SDK test', sourceNarHash='sha256-' + 'A' * 43 + '=', sdkVersions={'Lua': '5.5.1'}, runtimeAssertions=['PASS native SDK 5.5.1'])
        record['check'] = {'kind': 'script-generated-derivation', 'scriptPath': 'tests/sdk-native.py',
                           'sourceUrl': 'https://github.com/owner/project/blob/' + self.rev + '/tests/sdk-native.py',
                           'scriptArtifact': script_ref, 'lockArtifact': lock_ref, 'invoker': 'python3', 'arguments': "'5.5'",
                           'inputSourceHashes': {'tests/sdk-native.py': script_ref['artifactSha256'], 'flake.lock': lock_ref['artifactSha256']},
                           'assertionSnippet': "subprocess.run(['nix', 'build', '--expr', expression], check=True)", 'replayNotes': 'Exact generator and locked source inputs reconstruct this fixture check; no original temporary path is invented.'}
        return record

    def test_script_generated_derivation_requires_executable_replay_and_actual_build(self):
        record = self.script_record()
        self.check(record)
        for change in ('foreign-script', 'foreign-lock', 'wrong-drv', 'missing-assertion', 'wrong-arguments', 'foreign-assertion'):
            changed = copy.deepcopy(record)
            if change == 'foreign-script':
                changed['check']['sourceUrl'] = changed['check']['sourceUrl'].replace(self.rev, 'b' * 40)
            elif change == 'foreign-lock':
                changed['check']['inputSourceHashes']['flake.lock'] = 'c' * 64
            elif change == 'wrong-drv':
                changed['drvPath'] = self.drv.replace('example', 'unbuilt')
            elif change == 'missing-assertion':
                changed['runtimeAssertions'] = ['unobserved PASS SDK 5.5.1']
            elif change == 'wrong-arguments':
                changed['check']['arguments'] = "'5.4'"
            else:
                changed['check']['assertionSnippet'] = 'unobserved source assertion'
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.check(changed)

    def archived_record(self):
        record = self.script_record()
        log_path = self.root / 'public' / (record['logArtifact']['artifactSha256'] + '.json')
        log_capture = json.loads(log_path.read_text())
        log_capture['stdout'] = log_capture['stdout'][:log_capture['stdout'].index('2026-11-06T00:00:02Z building')] + '2026-11-06T00:00:04Z Uploaded native-captured\n'
        path = self.root / 'parent-log.json'
        path.write_text(json.dumps(log_capture))
        record['logArtifact'] = retain_native_artifact(path, self.root / 'public', self.base, 'command-json')
        output = self.drv[:-4]
        transcript = self.root / 'commands.log'
        transcript.write_text("building '" + self.drv + "'...\n" + output + '\nPASS native SDK 5.5.1\n')
        report = self.root / 'report.json'
        report.write_text(json.dumps({'selectedCasesPassed': True}))
        metadata = self.root / 'artifacts.json'
        value = {'artifacts': [{'name': 'native-captured', 'created_at': '2026-11-06T00:00:04Z', 'workflow_run': {'id': 321, 'head_sha': self.rev}}]}
        metadata.write_text(json.dumps(value))
        record['check'].update(executionArtifact=retain_native_artifact(transcript, self.root / 'public', self.base, 'text'),
                               reportArtifact=retain_native_artifact(report, self.root / 'public', self.base, 'json'),
                               artifactMetadata=retain_native_artifact(metadata, self.root / 'public', self.base, 'json'), artifactName='native-captured')
        record['observedOutputs'] = {'out': output}
        return record, output, transcript, report, metadata, value

    def test_archived_script_transcript_binds_run_source_report_and_observed_outputs(self):
        record, output, transcript, report, metadata, value = self.archived_record()
        self.check(record)
        for change in ('foreign-run', 'foreign-source', 'false-report', 'unobserved-output', 'no-built-drv', 'bare-before-marker'):
            changed = copy.deepcopy(record)
            if change in ('foreign-run', 'foreign-source'):
                modified = copy.deepcopy(value)
                modified['artifacts'][0]['workflow_run']['id' if change == 'foreign-run' else 'head_sha'] = 322 if change == 'foreign-run' else 'b' * 40
                metadata.write_text(json.dumps(modified))
                changed['check']['artifactMetadata'] = retain_native_artifact(metadata, self.root / 'public', self.base, 'json')
            elif change == 'false-report':
                report.write_text(json.dumps({'selectedCasesPassed': False}))
                changed['check']['reportArtifact'] = retain_native_artifact(report, self.root / 'public', self.base, 'json')
            elif change == 'unobserved-output':
                changed['observedOutputs']['out'] += '-invented'
            elif change == 'bare-before-marker':
                transcript.write_text(output + "\nbuilding '" + self.drv + "'...\nPASS native SDK 5.5.1\n")
                changed['check']['executionArtifact'] = retain_native_artifact(transcript, self.root / 'public', self.base, 'text')
            else:
                transcript.write_text(output + '\nPASS native SDK 5.5.1\n')
                changed['check']['executionArtifact'] = retain_native_artifact(transcript, self.root / 'public', self.base, 'text')
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.check(changed)

    def test_serialized_stdout_stderr_must_bind_same_actual_command_block(self):
        record, output, transcript, report, metadata, value = self.archived_record()
        generator = self.root / 'generator.py'
        original_source = generator.read_text() + '\nlog.write(result.stdout + result.stderr)\n'
        generator.write_text(original_source)
        record['check']['scriptArtifact'] = retain_native_artifact(generator, self.root / 'public', self.base, 'text')
        record['check']['inputSourceHashes']['tests/sdk-native.py'] = record['check']['scriptArtifact']['artifactSha256']
        argv = ['nix', 'build', 'path:/actual-generated-fixture#default', '--print-out-paths']
        record['check'].update(buildArgv=argv, transcriptLayout='argv-stdout-stderr')
        body = json.dumps(argv) + '\n' + output + "\nbuilding '" + self.drv + "'...\nPASS native SDK 5.5.1\n"
        transcript.write_text(body)
        record['check']['executionArtifact'] = retain_native_artifact(transcript, self.root / 'public', self.base, 'text')
        self.check(record)
        for change in ('cross-command-output', 'foreign-argv', 'wrong-layout-source', 'missing-drv', 'missing-output'):
            changed = copy.deepcopy(record)
            if change == 'cross-command-output':
                changed_body = json.dumps(['nix', 'build', 'path:/unrelated#default']) + '\n' + output + '\n' + json.dumps(argv) + "\nbuilding '" + self.drv + "'...\nPASS native SDK 5.5.1\n"
                transcript.write_text(changed_body)
                changed['check']['executionArtifact'] = retain_native_artifact(transcript, self.root / 'public', self.base, 'text')
            elif change == 'foreign-argv':
                changed['check']['buildArgv'] = ['nix', 'build', 'path:/never-executed#default']
            elif change == 'wrong-layout-source':
                generator.write_text(original_source.replace('result.stdout + result.stderr', 'result.stderr + result.stdout'))
                changed['check']['scriptArtifact'] = retain_native_artifact(generator, self.root / 'public', self.base, 'text')
                changed['check']['inputSourceHashes']['tests/sdk-native.py'] = changed['check']['scriptArtifact']['artifactSha256']
            else:
                transcript.write_text(body.replace("building '" + self.drv + "'...", 'derivation merely evaluated') if change == 'missing-drv' else body.replace(output + '\n', ''))
                changed['check']['executionArtifact'] = retain_native_artifact(transcript, self.root / 'public', self.base, 'text')
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.check(changed)

    def test_eval_only_skipped_or_foreign_step_does_not_prove_runtime(self):
        for change in ('eval-only', 'skipped', 'outside-step', 'next-step-same-second'):
            job, log = copy.deepcopy(self.job), self.log
            if change == 'eval-only':
                job['steps'][0]['name'] = 'Run nix flake check --no-build'
                log = log.replace('nix flake check -L', 'nix flake check --no-build')
            elif change == 'skipped':
                job['steps'][0]['conclusion'] = 'skipped'
            elif change == 'outside-step':
                log = log.replace('00:00:02Z', '00:00:10Z')
            else:
                job['steps'].append({'number': 6, 'name': 'Run nix flake check --no-build', 'status': 'completed', 'conclusion': 'success', 'started_at': '2026-11-06T00:00:03Z', 'completed_at': '2026-11-06T00:00:05Z'})
                log = log.replace('00:00:02Z', '00:00:03.500Z')
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.check(self.record(job, log))
