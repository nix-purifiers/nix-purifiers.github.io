"""Audit observation-level evidence in independently selected execution contexts.

Support facts and coverage obligations remain separate. This auditor never
promotes a native runner's overall success into unobserved assertions.
"""
import argparse
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def audit(plan, evidence, expected):
    projects = {}
    for name, project in plan['projects'].items():
        contexts = []
        review = [case['id'] for case in project['obligations']
                  if case['applicability'] == 'needs-review']
        required = {case['id']: case for case in project['obligations']
                    if case['applicability'] == 'required'}
        targets = expected.get(name, [])
        for target in targets:
            matches = [entry for entry in evidence.get(name, [])
                       if all(entry.get('provenance', {}).get(key) == target.get(key)
                              for key in ('system', 'nativeSDK', 'cacheProfile'))]
            problems = []
            entry = matches[0] if len(matches) == 1 else {}
            if len(matches) != 1:
                problems.append('expected exactly one evidence entry for context')
            provenance = entry.get('provenance', {})
            for key in ('system', 'nativeSDK', 'cacheProfile', 'sourceNarHash',
                        'sourceRevision', 'inputsDigest', 'driverDigest', 'graphHelperDigest'):
                if not isinstance(target.get(key), str) or not target[key]:
                    problems.append('missing expected ' + key)
                elif provenance.get(key) != target[key]:
                    problems.append('stale or missing ' + key)
            if target.get('system') not in project['systems']:
                problems.append('system is not declared by the model')
            if target.get('cacheProfile') not in project['cacheProfiles']:
                problems.append('cache profile is not declared by the plan')
            if provenance.get('planDigest') != digest(project):
                problems.append('stale or missing planDigest')
            observations = entry.get('observations', {})
            unknown = sorted(set(observations) - {case['id'] for case in project['obligations']})
            if unknown:
                problems.append('unknown obligations: ' + ', '.join(unknown))
            results = {}
            for case_id, case in required.items():
                recorded = observations.get(case_id, {})
                extra = set(recorded) - set(case['observations'])
                if extra:
                    problems.append('unknown observations for ' + case_id)
                result = {}
                for observation in case['observations']:
                    status = recorded.get(observation, {}).get('status', 'not-run')
                    if status not in {'passed', 'failed', 'blocked', 'skipped', 'not-run'}:
                        problems.append('invalid observation status')
                        status = 'invalid'
                    result[observation] = status
                results[case_id] = result
            if problems:
                results = {case: {key: 'stale' if status == 'passed' else status
                                  for key, status in observations.items()}
                           for case, observations in results.items()}
            contexts.append({'context': target, 'problems': problems, 'obligations': results,
                             'complete': bool(results) and not problems and all(
                                 status == 'passed' for observations in results.values()
                                 for status in observations.values())})
        selected = {(target.get('system'), target.get('nativeSDK'), target.get('cacheProfile')) for target in targets}
        matrix = {(system, sdk, cache) for system in project['systems']
                  for sdk in project['sdkMatrix'].get('profiles', []) for cache in project['cacheProfiles']}
        missing_matrix = sorted(matrix - selected)
        extra_contexts = [entry.get('provenance', {}) for entry in evidence.get(name, [])
                          if tuple(entry.get('provenance', {}).get(key) for key in
                                   ('system', 'nativeSDK', 'cacheProfile')) not in selected]
        projects[name] = {'contexts': contexts, 'applicabilityReviewPending': review,
                          'sdkMatrix': project['sdkMatrix'],
                          'missingMatrixContexts': missing_matrix, 'unexpectedContexts': extra_contexts,
                          'complete': bool(contexts) and bool(matrix) and not missing_matrix
                          and not extra_contexts and not review
                          and project['sdkMatrix']['state'] == 'reviewed'
                          and all(context['complete'] for context in contexts)}
    extras = sorted(set(evidence) - set(plan['projects']))
    return {'version': 1, 'scope': 'selected-execution-contexts', 'planDigest': digest(plan), 'projects': projects,
            'unknownEvidenceProjects': extras,
            'candidateCompatibilityReviewPending': len(plan['projectionCandidates']),
            'complete': bool(projects) and not extras and not plan['projectionCandidates']
                        and all(project['complete'] for project in projects.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('plan', 'evidence', 'expected'):
        parser.add_argument('--' + argument, type=Path, required=True)
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    result = audit(*(json.loads(path.read_text()) for path in (args.plan, args.evidence, args.expected)))
    print(json.dumps(result, indent=2, sort_keys=True))
    return int(args.require_complete and not result['complete'])


if __name__ == '__main__':
    raise SystemExit(main())
