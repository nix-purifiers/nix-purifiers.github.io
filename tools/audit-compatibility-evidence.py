#!/usr/bin/env python3
"""Audit catalog bindings and report changed native inputs without inventing passes."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'docs-site'))
from compatibility_evidence import audit_source, validate_registry, verify_ci


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=ROOT/'docs-site/catalog.json')
    parser.add_argument('--registry', type=Path, default=ROOT/'model/compatibility-tests.json')
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument('--checkouts', type=Path, help='Clean native checkouts, named by purifier')
    sources.add_argument('--fetch', action='store_true', help='Read current public default branches in isolated bare clones')
    parser.add_argument('--verify-ci', action='store_true', help='Recheck actual GitHub job conclusions and CI source inputs')
    parser.add_argument('--output', type=Path, help='Write the JSON report, including errors and source drift')
    args = parser.parse_args()
    if args.verify_ci and not (args.fetch or args.checkouts):
        parser.error('--verify-ci requires --fetch or --checkouts')
    registry = json.loads(args.registry.read_text())
    catalog = json.loads(args.catalog.read_text())['catalog']
    validate_registry(registry, catalog)
    report = dict(status='catalog-consistent', nativeTestsExecuted=False, projects={})
    failed = False
    with tempfile.TemporaryDirectory(prefix='purifier-compatibility-audit-') as temporary:
        for name, entry in registry['projects'].items():
            repository = catalog[name]['repository']
            rows = []
            try:
                if args.fetch:
                    checkout = Path(temporary)/name
                    subprocess.run(['git', 'clone', '-q', '--bare', f'https://github.com/{repository}.git', str(checkout)], check=True)
                elif args.checkouts:
                    checkout = args.checkouts/name
                else:
                    report['projects'][name] = dict(status='source-not-checked', testedPoints=len(entry['testedPoints']))
                    continue
                for review in entry['reviews']:
                    row = audit_source(checkout, review, clean=not args.fetch)
                    row['pointIds'] = review['pointIds']
                    if args.verify_ci:
                        verify_ci(repository, review, checkout, fetch=args.fetch)
                        row['ciEvidence'] = 'verified'
                    rows.append(row)
                # Each point retains its own scope; one matching old review
                # cannot hide drift in another SDK point for this project.
                status = 'review-needed' if any(x['status'] != 'inputs-match' for x in rows) else 'inputs-match'
                failed |= status == 'review-needed'
                report['projects'][name] = dict(status=status, reviews=rows)
            except (ValueError, OSError, subprocess.CalledProcessError) as error:
                failed = True
                report['projects'][name] = dict(status='unverified', error=str(error), reviews=rows)
    if failed: report['status'] = 'review-needed'
    payload = json.dumps(report, indent=2)+'\n'
    if args.output: args.output.write_text(payload)
    print(payload, end='')
    return int(failed)


if __name__ == '__main__': sys.exit(main())
