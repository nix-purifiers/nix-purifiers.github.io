"""Shared behavioral tests using invocation recipes and fixture capabilities."""
import copy

if __package__:
    from .runtime import run
else:
    from runtime import run


def run_suite(model, plan, capabilities, fixtures, context):
    """Run modeled tests; missing glue is reported as blocked, never passed.

    `locked-selections` returns normalized native pins; `advance-upstream`
    makes a newer eligible dependency available in the fixture repository.
    Those tool-specific mechanisms belong to the bespoke fixture provider.
    """
    results = {}
    for name, case in plan['cases'].items():
        missing = ([f'capability:{key}' for key in case['capabilities'] if key not in capabilities]
                   + [f'fixture:{key}' for key in case['fixtures'] if key not in fixtures])
        if missing:
            results[name] = {'status': 'blocked', 'missing': missing}
            continue
        try:
            def invoke(operation):
                result = run(model, operation, capabilities, context, capture_output=True)
                if result.returncode != 0:
                    raise AssertionError(f'{operation} exited {result.returncode}: {result.stderr}')
            if case['kind'] == 'operation':
                invoke(case['operation'])
            elif case['kind'] == 'relock':
                invoke('lock')
                before = copy.deepcopy(fixtures['locked-selections']())
                if not before:
                    raise AssertionError('relock fixture must select at least one dependency')
                fixtures['advance-upstream']()
                invoke('lock')
                after = fixtures['locked-selections']()
                if (before == after) != case['expectUnchanged']:
                    raise AssertionError('relocking disagrees with the declared pin-retention behavior')
            else:
                raise ValueError(f'unknown test kind: {case["kind"]}')
            results[name] = {'status': 'passed'}
        except Exception as error:
            results[name] = {'status': 'failed', 'reason': str(error)}
    return {
        'repository': model['repository'], 'results': results,
        'uncoveredFacts': plan['uncoveredFacts'],
        'complete': bool(results) and not plan['uncoveredFacts']
                    and all(result['status'] == 'passed' for result in results.values()),
    }
