# SPDX-License-Identifier: MIT
"""Real client/engine workflows; retain exact host, SDK and sample receipts.

The Docker client runs on the host (including Darwin); the daemon runs Linux.
--network=none denies RUN networking, not the daemon's registry transport.
Linux's separate pure builder runs in its networkless software VM.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import ssl
import subprocess
import sys
import tempfile

SOURCE = Path(os.environ.get('DOCKER_PURIFIER_TEST_SOURCE', Path(__file__).resolve().parents[1]))
SAMPLE = '522bcd2faf422c60b9d20e64d7cd6d56600aec97'


def run(args, **kwargs):
    print('+', ' '.join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), check=True, text=True, **kwargs)


def main():
    receipt = Path(sys.argv[1]).resolve()
    receipt.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='docker-tier2-') as directory:
        temp = Path(directory)
        cli_root = Path(os.environ['DOCKER_PURIFIER_TEST_CLI'])
        cli = cli_root / 'bin/docker-purifier'
        docker = cli_root / 'bin/docker'
        native = Path(os.environ['DOCKER_PURIFIER_TEST_DOCKER']) / 'bin/docker'
        skopeo = Path(os.environ['DOCKER_PURIFIER_TEST_SKOPEO']) / 'bin/skopeo'
        # A fresh HOME prevents accidental use of a developer's native cache.
        # Preserve Docker's selected socket/context in its explicit config path.
        home = temp / 'home'
        home.mkdir()
        env = {**os.environ, 'HOME': str(home),
               'DOCKER_CONFIG': os.environ.get('DOCKER_CONFIG', str(Path.home() / '.docker'))}
        version = json.loads(run([native, 'version', '--format', '{{json .}}'], env=env, capture_output=True).stdout)
        assert version['Server']['Os'] == 'linux', version
        if os.environ.get('EXPECTED_ENGINE_VERSION'):
            assert version['Server']['Version'] == os.environ['EXPECTED_ENGINE_VERSION'], version
            if os.environ['EXPECTED_ENGINE_VERSION'] == '25.0.18':
                assert version['Server']['GitCommit'] == 'eaa0057b5d603fbd1eb1867246c05ef2a0cf1ed9', version
        info = json.loads(run([native, 'info', '--format', '{{json .}}'], env=env, capture_output=True).stdout)
        expected = os.environ.get('EXPECTED_NIX_SYSTEM')
        system = run(['nix', 'eval', '--impure', '--raw', '--expr', 'builtins.currentSystem'], capture_output=True).stdout
        if expected:
            assert system == expected, (system, expected)
        nix_config = json.loads(run(['nix', 'config', 'show', '--json'], capture_output=True).stdout)
        sandbox = nix_config['sandbox']['value']
        assert sandbox is True or sandbox == 'true', sandbox
        nested_store = json.loads(run(['nix', 'store', 'info', '--json'], capture_output=True).stdout)
        if sys.platform == 'darwin':
            assert nested_store['url'] == 'daemon' and nested_store['trusted'] is True, nested_store
        result = {'revision': os.environ['DOCKER_PURIFIER_TEST_REVISION'],
                  'kind': 'impure-external-daemon-host-integration',
                  'runtimeId': os.environ['DOCKER_PURIFIER_TEST_RUNTIME_ID'],
                  'nestedNixRemote': os.environ.get('NIX_REMOTE', 'auto'),
                  'nestedNixSandboxRequested': sandbox,
                  'nestedNixStore': nested_store,
                  'dockerHost': env['DOCKER_HOST'],
                  'daemon': {key: info[key] for key in ('ID', 'ServerVersion', 'OSType', 'Architecture', 'KernelVersion', 'OperatingSystem', 'Driver', 'Name')},
                  'nixSystem': system, 'host': platform.platform(), 'docker': version,
                  'buildx': run([docker, 'buildx', 'version'], env=env, capture_output=True).stdout.strip(),
                  'sample': {'repository': 'docker-library/hello-world', 'revision': SAMPLE}, 'sourceNarHash': run(['nix', 'hash', 'path', SOURCE], capture_output=True).stdout.strip(),
                  'cases': []}
        (receipt / 'runtime.json').write_text(json.dumps(result, indent=2) + '\n')
        projects = [('busybox', SOURCE / 'examples/hello', 'hello from locked Docker dependencies\n')]
        sample = Path(os.environ['DOCKER_PURIFIER_TEST_SAMPLE'])
        arch = 'arm64v8' if platform.machine() in ('arm64', 'aarch64') else 'amd64'
        expected_hashes = json.loads((SOURCE / 'tests/fixtures/hello-world/source.json').read_text())['sha256']
        hashes = {}
        for name in ('Dockerfile', 'hello'):
            hashes[name] = hashlib.sha256((sample / name).read_bytes()).hexdigest()
            assert hashes[name] == expected_hashes[f'{arch}/{name}']
        result['sample'].update(architecture=arch, sha256=hashes)
        projects.append(('independent', sample, None))
        # Capture a real TLS registry dependency, then remove the registry
        # before the native build. Inspect config origin as well as runtime.
        sys.path.insert(0, str(SOURCE / 'tests'))
        from registry import Registry
        registry = Registry().start()
        registry_root = temp / 'registry-project'
        registry_root.mkdir()
        shutil.copyfile(sample / 'hello', registry_root / 'hello')
        (registry_root / 'hello').chmod(0o755)
        reference = registry.host + '/first:latest'
        (registry_root / 'Dockerfile').write_text(f'FROM {reference}\nCOPY hello /hello\nCMD ["/hello"]\n')
        bundle = temp / 'registry-ca.pem'
        bundle.write_text(''.join(ssl.DER_cert_to_PEM_cert(cert) for cert in ssl.create_default_context().get_ca_certs(binary_form=True))
                          + registry.tls.ca.read_text())
        shutil.copyfile(registry.tls.ca, receipt / 'fixture-ca.crt')
        shutil.copyfile(registry.tls.certificate, receipt / 'fixture-localhost.crt')
        result['fixtureOpenSsl'] = registry.tls.version
        registry.tls.trust_skopeo(home, registry.host)
        registry_env = {**env, 'SSL_CERT_FILE': str(bundle), 'NIX_SSL_CERT_FILE': str(bundle)}
        try:
            run([cli, '--project', registry_root, 'lock'], env=registry_env)
            run([cli, '--project', registry_root, 'prefetch'], env=registry_env)
            known_lock = (registry_root / 'docker-purifier.lock.json').read_bytes()
            good_dockerfile = (registry_root / 'Dockerfile').read_bytes()
            (registry_root / 'Dockerfile').write_text(f'FROM {registry.host}/missing:latest\n')
            unknown = subprocess.run([str(cli), '--project', str(registry_root), 'lock'],
                                     env=registry_env, text=True, capture_output=True)
            assert unknown.returncode != 0, unknown
            assert (registry_root / 'docker-purifier.lock.json').read_bytes() == known_lock
            (registry_root / 'Dockerfile').write_bytes(good_dockerfile)
        finally:
            registry.stop()
        tag = f'purifier-tier2-registry:{os.getpid()}'
        try:
            run([docker, 'build', '--no-cache', '--network=none', '--load', '-t', tag, '.'], cwd=registry_root, env=registry_env)
            configuration = json.loads(run([native, 'image', 'inspect', tag], env=env, capture_output=True).stdout)[0]['Config']
            assert 'FIXTURE_VERSION=1' in configuration['Env'], configuration
            output = run([native, 'run', '--rm', '--pull=never', '--network=none', tag], env=env, capture_output=True).stdout
            assert 'Hello from Docker!' in output, output
            result['cases'].append('removed-registry:prefetch-native-build-origin-run-unknown-negative')
        finally:
            subprocess.run([str(native), 'image', 'rm', '-f', tag], env=env, check=False)

        for name, source, expected_output in projects:
            root = temp / name
            shutil.copytree(source, root, ignore=shutil.ignore_patterns('.docker-purifier'))
            original = (root / 'Dockerfile').read_bytes()
            command = [cli, '--project', root]
            run([*command, 'lock'], env=env)
            lock = root / 'docker-purifier.lock.json'
            locked = lock.read_bytes()
            run([*command, 'lock'], env=env)
            assert lock.read_bytes() == locked
            run([*command, 'prefetch'], env=env)
            tag = f'purifier-tier2-{name}:{os.getpid()}'
            try:
                # Use a new tag, no layer cache, no RUN network, and no pull.
                run([docker, 'build', '--no-cache', '--network=none', '--load', '-t', tag, '.'], cwd=root, env=env)
                output = run([native, 'run', '--rm', '--pull=never', '--network=none', tag], env=env, capture_output=True).stdout
                if expected_output:
                    assert output == expected_output, output
                else:
                    assert 'Hello from Docker!' in output, output
                # Altering Dockerfile inputs must fail before invoking the engine.
                (root / 'Dockerfile').write_bytes(original + b'\n')
                failed = subprocess.run([str(docker), 'build', '.'], cwd=root, env=env, text=True, capture_output=True)
                assert failed.returncode != 0 and 'ignore rules changed' in failed.stderr, failed
                (root / 'Dockerfile').write_bytes(original)
                assert lock.read_bytes() == locked
                mutated = json.loads(locked)
                mutated['contentHash'] = '0' * 64
                lock.write_text(json.dumps(mutated))
                failed = subprocess.run([str(docker), 'build', '.'], cwd=root, env=env, text=True, capture_output=True)
                assert failed.returncode != 0 and 'contentHash mismatch' in failed.stderr, failed
                lock.write_bytes(locked)
                if sys.platform == 'linux':
                    image = run(['nix', 'build', '--option', 'sandbox', 'true', '--impure', '--file', cli_root / 'lib/docker-purifier/nix/realize.nix',
                                 '--argstr', 'project', root, '--argstr', 'dockerfile', root / 'Dockerfile',
                                 '--argstr', 'lockFile', lock, '--argstr', 'target', 'release',
                                 '--no-link', '--print-out-paths'], capture_output=True).stdout.strip()
                    archive = Path(image) / 'image.oci.tar.gz'
                    assert archive.is_file()
                    native_archive = temp / (name + '-pure.tar')
                    run([skopeo, 'copy', 'oci-archive:' + str(archive),
                         'docker-archive:' + str(native_archive) + ':' + tag], env=env)
                    run([native, 'load', '--input', native_archive], env=env)
                    pure_output = run([native, 'run', '--rm', '--pull=never', '--network=none', tag],
                                      env=env, capture_output=True).stdout
                    assert pure_output == output, (pure_output, output)
                    result.setdefault('pureReleases', {})[name] = {
                        'output': image,
                        'derivation': run(['nix-store', '--query', '--deriver', image], capture_output=True).stdout.strip(),
                        'narHash': run(['nix', 'hash', 'path', image], capture_output=True).stdout.strip(),
                    }
                    result['cases'].append(name + ':linux-networkless-pure-release')
                result['cases'].append(name + ':lock-prefetch-native-run-stale-tampered-negatives')
            finally:
                subprocess.run([str(native), 'image', 'rm', '-f', tag], env=env, check=False)
            assert (root / 'Dockerfile').read_bytes() == original
            (receipt / 'runtime.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
