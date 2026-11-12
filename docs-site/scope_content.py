"""Shared formatting for scope facts and detailed source explanations."""


def fact_list(values):
    return '\n'.join('- ' + value.replace('\n', '\n  ') for value in values)


def scope_block(body):
    return '<div class="supported-scope" markdown="1">\n\n' + body + '\n\n</div>'
