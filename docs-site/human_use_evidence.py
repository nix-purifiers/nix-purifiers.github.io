"""Reviewed human-use reports. Structure is validated; original attestations need review.

Private originals stay outside the public model. A direct attestation uses a stable
opaque provenance reference; it need not have a public URL or public identity.
"""
import copy
from html import escape
import re

from quality_policy import HUMAN_CRITERIA, POLICY

REPORT_FIELDS = {'repository', 'reportedAt', 'reporter', 'basis', 'scope', 'claims', 'source', 'reviewedAt', 'summary'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def without_whitespace(value):
    return value.translate({ord(char): None for char in POLICY['humanWhitespace']})


def text(value):
    return isinstance(value, str) and bool(without_whitespace(value))


def primary_url(value):
    return isinstance(value, str) and re.fullmatch(r'https://[^<>"|]+', value) is not None and without_whitespace(value) == value


def date(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])', value) is not None


def public_report(envelope):
    """Select the explicitly reviewed public projection, never private originals."""
    require(isinstance(envelope, dict) and set(envelope) <= {'public', 'private'} and 'public' in envelope,
            'attestation envelope needs an explicit public projection')
    report = copy.deepcopy(envelope['public'])
    require(isinstance(report, dict) and isinstance(report.get('repository'), str), 'invalid public report projection')
    validate_report(report['repository'], report)
    return report


def validate_report(repository, report):
    require(isinstance(report, dict) and set(report) == REPORT_FIELDS, 'human report has missing or unknown fields')
    require(isinstance(report['repository'], str) and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', report['repository']) is not None
            and report['repository'] == repository, 'human report belongs to another purifier')
    require(date(report['reportedAt']) and date(report['reviewedAt']), 'human report needs report and review dates')
    require(all(text(report[k]) for k in ('scope', 'summary')), 'human report needs scoped use and a review summary')
    reporter = report['reporter']
    require(isinstance(reporter, dict) and set(reporter) == {'kind', 'relationship', 'publicLabel'}, 'invalid reporter provenance')
    require(reporter['kind'] in ('human', 'bot', 'unknown'), 'invalid reporter kind')
    require(reporter['relationship'] in ('maintainer', 'contributor', 'independent-user', 'other-user', 'unknown'), 'invalid reporter relationship')
    require(reporter['publicLabel'] is None or text(reporter['publicLabel']), 'invalid public reporter label')
    require(report['basis'] in ('firsthand', 'hearsay', 'authorship-only', 'automation'), 'invalid human report basis')
    claims = report['claims']
    require(isinstance(claims, list) and bool(claims)
            and all(isinstance(c, str) and c in ('firsthand-use', 'ongoing-use') for c in claims)
            and len(claims) == len(set(claims)), 'invalid human usage claims')
    require('ongoing-use' not in claims or 'firsthand-use' in claims, 'ongoing report also needs firsthand use')
    source = report['source']
    require(isinstance(source, dict) and set(source) == {'kind', 'url', 'reference'}, 'invalid human report source')
    if source['kind'] == 'public-primary-url':
        require(primary_url(source['url'])
                and source['reference'] is None, 'public report needs a primary URL')
    else:
        require(source['kind'] == 'direct-attestation' and source['url'] is None
                and isinstance(source['reference'], str)
                and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]*', source['reference']) is not None,
                'direct attestation needs an opaque provenance reference, not a private path or URL')
    return report


def validate_context(repository, context):
    require(isinstance(context, dict) and set(context) == {'repository', 'kind', 'source', 'scope', 'attribution', 'reviewedAt'}, 'invalid ongoing-use context')
    require(context['repository'] == repository, 'usage context belongs to another purifier')
    require(context['kind'] in ('maintained-consumer-history', 'supplied-usage-context'), 'invalid usage-context kind')
    require(all(text(context[k]) for k in ('scope', 'attribution')) and date(context['reviewedAt']), 'usage context needs scope, attribution and review date')
    source = context['source']
    require(isinstance(source, dict) and set(source) == {'kind', 'url', 'reference'}, 'invalid usage-context provenance')
    if source['kind'] == 'public-primary-url':
        require(primary_url(source['url'])
                and source['reference'] is None, 'usage context needs a primary URL')
    else:
        require(source['kind'] == 'private-context' and source['url'] is None
                and isinstance(source['reference'], str)
                and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]*', source['reference']) is not None,
                'private usage context needs opaque provenance')
    return context


def validate_review(repository, review):
    require(isinstance(review, dict) and set(review) == {'reviewedAt', 'reports', 'criteria'}, 'invalid human usage review')
    require(date(review['reviewedAt']), 'human usage review needs a date')
    reports, criteria = review['reports'], review['criteria']
    require(isinstance(reports, dict) and all(text(k) for k in reports), 'invalid report identities')
    for report in reports.values():
        validate_report(repository, report)
    require(isinstance(criteria, dict) and set(criteria) == set(HUMAN_CRITERIA), 'both human use criteria need explicit review')
    for key in HUMAN_CRITERIA:
        criterion = criteria[key]
        require(isinstance(criterion, dict) and set(criterion) == {'state', 'summary', 'reports', 'gap', 'confidenceReason', 'usageContexts'}, 'invalid human use criterion')
        require(criterion['state'] in ('met', 'not-met') and text(criterion['summary']), 'invalid human use judgment')
        refs = criterion['reports']
        require(isinstance(refs, list) and all(isinstance(ref, str) for ref in refs)
                and len(refs) == len(set(refs)) and all(ref in reports for ref in refs), 'unknown or duplicate human report reference')
        contexts = criterion['usageContexts']
        require(isinstance(contexts, list), 'usage contexts must be a list')
        for context in contexts:
            validate_context(repository, context)
        require(key == 'ongoingUse' or contexts == [], 'usage contexts belong to the ongoing-use review')
        if criterion['state'] == 'not-met':
            require(text(criterion['gap']) and criterion['confidenceReason'] is None, 'missing use evidence needs an honest gap')
            continue
        require(criterion['gap'] is None, 'met human use criterion cannot assert a gap')
        require(all(reports[ref]['reporter']['kind'] == 'human' and reports[ref]['basis'] == 'firsthand'
                    and 'firsthand-use' in reports[ref]['claims'] for ref in refs), 'human use requires actual firsthand human evidence')
        if key == 'firsthandUse':
            require(bool(refs), 'met firsthand use requires reviewed reports')
        else:
            require(bool(contexts) or (bool(refs) and all('ongoing-use' in reports[ref]['claims'] for ref in refs)),
                    'ongoing use needs continuing-use evidence or attributable usage context')
        if key == 'ongoingUse':
            require(text(criterion['confidenceReason']) and criteria['firsthandUse']['state'] == 'met', 'ongoing use needs reviewed confidence and firsthand use')
        else:
            require(criterion['confidenceReason'] is None, 'firsthand use does not require an ongoing-use threshold')
    return review


def render_reports(repository, review):
    """Only the public reviewed record reaches rendered documentation."""
    validate_review(repository, review)
    lines = []
    for report in review['reports'].values():
        source = report['source']
        label = report['reporter']['publicLabel'] or 'Reporter'
        origin = (f'<a href="{escape(source["url"], quote=True)}">{escape(label)}</a>' if source['kind'] == 'public-primary-url'
                  else f'{escape(label)} (reviewed direct attestation)')
        lines.append(f'- {origin}, {report["reportedAt"]}; {escape(report["reporter"]["relationship"])}. '
                     f'{escape(report["scope"])} {escape(report["summary"])}')
    for context in review['criteria']['ongoingUse']['usageContexts']:
        source = context['source']
        origin = (f'<a href="{escape(source["url"], quote=True)}">Primary use context</a>'
                  if source['kind'] == 'public-primary-url' else 'Reviewed private use context')
        lines.append(f'- {origin}, reviewed {context["reviewedAt"]}. {escape(context["scope"])} {escape(context["attribution"])}')
    for key in HUMAN_CRITERIA:
        criterion = review['criteria'][key]
        if criterion['confidenceReason'] is not None:
            lines.append('Ongoing-use confidence: ' + escape(criterion['confidenceReason']))
        if criterion['gap'] is not None:
            label = 'Firsthand-use evidence gap' if key == 'firsthandUse' else 'Ongoing-use evidence gap'
            lines.append(label + ': ' + escape(criterion['gap']))
    return '\n'.join(lines)
