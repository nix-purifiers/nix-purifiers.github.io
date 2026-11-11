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
from compatibility_evidence import audit_source, validate_registry, verify_ci, inputs
from compatibility_reconciliation import Reconciliation, MATCH, PAGES, CURRENT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=ROOT/'docs-site/catalog.json')
    parser.add_argument('--registry', type=Path, default=ROOT/'model/compatibility-tests.json')
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument('--checkouts', type=Path, help='Clean native checkouts, named by purifier')
    sources.add_argument('--fetch', action='store_true', help='Read current public default branches in isolated bare clones')
    parser.add_argument('--verify-ci', action='store_true', help='Recheck actual GitHub job conclusions and CI source inputs')
    parser.add_argument('--reconciliation', type=Path, default=ROOT/'model/compatibility-reconciliation.json', help='Explicit reviewed provenance; never suppress unresolved drift')
    parser.add_argument('--output', type=Path, help='Write the JSON report, including errors and source drift')
    args = parser.parse_args()
    if args.verify_ci and not (args.fetch or args.checkouts):
        parser.error('--verify-ci requires --fetch or --checkouts')
    registry = json.loads(args.registry.read_text())
    catalog = json.loads(args.catalog.read_text())['catalog']
    validate_registry(registry, catalog)
    reconciliation = Reconciliation(json.loads(args.reconciliation.read_text()), args.registry.read_bytes(), ROOT, catalog=catalog)
    report = dict(version=2, status='catalog-consistent', nativeTestsExecuted=False, projects={}, currentApplicability='not-evaluated', pointCounts={})
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
                observed_files = inputs(checkout, 'HEAD')
                current_verified = False
                for review in entry['reviews']:
                    row = audit_source(checkout, review, clean=not args.fetch)
                    row['pointIds'] = review['pointIds']
                    if args.verify_ci:
                        verify_ci(repository, review, checkout, fetch=args.fetch)
                        row['ciEvidence'] = 'verified'
                    row['historicalEvidence'] = dict(status='verified' if args.verify_ci else 'not-rechecked', testedRevision=review['sourceRevision'], inputDigest=review['inputDigest'])
                    row['currentApplicability'] = {point_id: reconciliation.classify(name, point_id, row['currentRevision'], observed_files) for point_id in review['pointIds']}
                    if args.verify_ci and not current_verified and any(x['status'] == CURRENT for x in row['currentApplicability'].values()):
                        reconciliation.verify_current_ci(name)
                        current_verified = True
                    rows.append(row)
                # Each point retains its own scope; one matching old review
                # cannot hide drift in another SDK point for this project.
                status = 'review-needed' if any(x['status'] != 'inputs-match' for x in rows) else 'inputs-match'
                states = [value['status'] for row in rows for value in row['currentApplicability'].values()]
                reconciled = all(value in [MATCH, PAGES, CURRENT] for value in states)
                failed |= not reconciled
                for state in states:
                    report['pointCounts'][state] = report['pointCounts'].get(state, 0) + 1
                report['projects'][name] = dict(status=status, currentApplicability='reviewed' if reconciled else 'review-needed', reviews=rows)
            except (ValueError, OSError, subprocess.CalledProcessError) as error:
                failed = True
                report['projects'][name] = dict(status='unverified', error=str(error), reviews=rows)
    if args.fetch or args.checkouts:
        report['currentApplicability'] = 'review-needed' if failed else 'reviewed'
    if failed: report['status'] = 'review-needed'
    payload = json.dumps(report, indent=2)+'\n'
    if args.output: args.output.write_text(payload)
    print(payload, end='')
    return int(failed)


if __name__ == '__main__': sys.exit(main())
