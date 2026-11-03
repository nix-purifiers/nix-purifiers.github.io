"""Run a modeled operation using a capability provider's executable bindings."""
import argparse
import json
from pathlib import Path

if __package__:
    from .runtime import Executable, run
else:
    from runtime import Executable, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', required=True, type=Path)
    parser.add_argument('--project', required=True)
    parser.add_argument('--provider', required=True, type=Path,
                        help='JSON containing capabilities and context from the bespoke integration')
    parser.add_argument('operation')
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    models = json.loads(args.catalog.read_text())
    provider = json.loads(args.provider.read_text())
    capabilities = {name: Executable(binding['command'], binding.get('environment'))
                    for name, binding in provider['capabilities'].items()}
    arguments = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
    try:
        result = run(models[args.project], args.operation, capabilities,
                     provider['context'], arguments=arguments)
    except ValueError as error:
        parser.exit(2, f'purifier harness: {error}\n')
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
