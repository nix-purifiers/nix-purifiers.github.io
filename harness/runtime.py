"""Execute modeled tool invocations through capabilities supplied by bespoke glue.

The model contains recipes, never plugin implementation or executable locations.
A provider may be a Python callable or an Executable bound to an existing tool.
"""
from dataclasses import dataclass
import os
import subprocess


class UnsupportedOperation(ValueError):
    """The model does not offer this operation."""


class CapabilityUnavailable(ValueError):
    """The model offers it, but the integration did not supply its capability."""


class OperationUnknown(UnsupportedOperation):
    """This operation has not been modeled, rather than being known unsupported."""


@dataclass(frozen=True)
class Invocation:
    arguments: list[str]
    environment: dict[str, str]
    directory: str


class Executable:
    """Bind a modeled capability to a separately implemented executable."""

    def __init__(self, command, environment=None):
        if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
            raise ValueError('capability command must be a nonempty argument list')
        self.command = command
        self.environment = environment or {}

    def __call__(self, invocation, **kwargs):
        if set(kwargs) - {'capture_output', 'stdout', 'stderr', 'stdin', 'timeout', 'input'}:
            raise ValueError('unsupported execution options')
        return subprocess.run(
            [*self.command, *invocation.arguments], cwd=invocation.directory,
            env={**os.environ, **self.environment, **invocation.environment},
            text=True, check=False, **kwargs)


def value(expression, context):
    if isinstance(expression, str):
        return expression
    if isinstance(expression, dict) and set(expression) == {'binding'}:
        key = expression['binding']
        result = context.get(key)
        if not isinstance(result, str) or not result:
            raise ValueError(f'missing or invalid context binding: {key}')
        return result
    raise ValueError(f'invalid invocation expression: {expression!r}')


def run(model, operation, capabilities, context, arguments=(), **kwargs):
    """Resolve a recipe and call its supplied capability, preserving exit status.

    Additional arguments are accepted only at an explicit splice. Context
    bindings remain individual argv or environment values, never shell code.
    No fallback executable is chosen if the bespoke integration is incomplete.
    """
    recipe = model['operations'].get(operation)
    if recipe is None or recipe.get('state') == 'unknown':
        reason = recipe.get('reason') if recipe else 'No invocation recipe is declared.'
        raise OperationUnknown(f'{operation}: {reason}')
    if recipe.get('state', 'available') != 'available':
        reason = recipe.get('reason') if recipe else 'No invocation recipe is declared.'
        raise UnsupportedOperation(f'{operation}: {reason}')
    capability = capabilities.get(recipe['capability'])
    if capability is None:
        raise CapabilityUnavailable(f'{operation}: glue must supply {recipe["capability"]}')
    if not isinstance(arguments, (tuple, list)) or not all(isinstance(arg, str) for arg in arguments):
        raise ValueError('arguments must be strings')
    if len(arguments) < recipe.get('minimumArguments', 0):
        raise ValueError(f'{operation}: requires at least {recipe["minimumArguments"]} arguments')
    argv = []
    splices = 0
    for expression in recipe['arguments']:
        if expression == {'splice': 'arguments'}:
            argv.extend(arguments)
            splices += 1
        else:
            argv.append(value(expression, context))
    if splices > 1 or (arguments and splices == 0):
        raise ValueError(f'{operation}: additional arguments are not accepted here')
    invocation = Invocation(
        argv, {key: value(expr, context) for key, expr in recipe['environment'].items()},
        value(recipe['directory'], context))
    return capability(invocation, **kwargs)
