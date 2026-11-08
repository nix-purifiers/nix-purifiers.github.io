"""Reviewed human-use reports. Structure is validated; original attestations need review.

Private originals stay outside the public model. A direct attestation uses a stable
opaque provenance reference; it need not have a public URL or public identity.
"""
import copy
from html import escape
import re

from quality_policy import HUMAN_CRITERIA, POLICY

REPORT_FIELDS = {'repository', 'reportedAt', 'reporter', 'basis', 'scope', 'claims', 'source', 'reviewedAt', 'summary', 'ongoingUsers'}


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


def validate_role_basis(basis):
    require(isinstance(basis, dict) and set(basis) == {'summary', 'source'} and text(basis['summary']), 'invalid ongoing-user role basis')
    source = basis['source']
    require(isinstance(source, dict) and set(source) == {'kind', 'url', 'reference'}, 'invalid ongoing-user role provenance')
    if source['kind'] == 'public-primary-url':
        require(primary_url(source['url']) and source['reference'] is None, 'role basis needs a primary URL')
    else:
        require(source['kind'] in ('direct-attestation', 'private-context') and source['url'] is None
                and isinstance(source['reference'], str)
                and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]*', source['reference']) is not None,
                'private role basis needs opaque provenance')


def validate_ongoing_users(users):
    require(isinstance(users, list), 'ongoing-use subjects must be a list')
    for user in users:
        require(isinstance(user, dict) and set(user) == {'publicLabel', 'maintainerStatus', 'statusBasis', 'useScope'}, 'invalid ongoing-use subject')
        require(user['publicLabel'] is None or text(user['publicLabel']), 'invalid ongoing-user label')
        require(text(user['useScope']), 'ongoing-use subject needs actual use scope')
        require(user['maintainerStatus'] in ('maintainer', 'non-maintainer', 'unknown'), 'invalid ongoing-user maintainer status')
        if user['statusBasis'] is not None:
            validate_role_basis(user['statusBasis'])
        require(user['maintainerStatus'] == 'unknown' or user['statusBasis'] is not None,
                'known ongoing-user maintainer status requires a reviewed basis')
    return users


def has_maintainer_ongoing_user(users):
    return any(user['maintainerStatus'] == POLICY['ongoingUse']['requiredMaintainerStatus'] for user in users)


def canonical_repository(value, repository_root=True):
    if not isinstance(value, str):
        return None
    value = value.split('#', 1)[0].split('?', 1)[0]
    match = re.fullmatch(r'https://([A-Za-z0-9.-]+)/([A-Za-z0-9._~/-]+)', value)
    if match is None:
        return None
    host, path = match.group(1).lower(), match.group(2).lower()
    if host == 'www.github.com': host = 'github.com'
    if host == 'api.github.com' and path.startswith('repos/'):
        host, path = 'github.com', path[6:]
    if path.endswith('/'): path = path[:-1]
    if path.endswith('.git'): path = path[:-4]
    parts = path.split('/')
    if any(part in ('', '.', '..') for part in parts):
        return None
    if repository_root and host == 'github.com' and len(parts) != 2:
        return None
    return 'https://' + host + '/' + path


def project_identity(project):
    base = canonical_repository(project['publicRepository'])
    if base is None: return None
    path = project['projectPath']
    if path is None: return base
    if not isinstance(path, str) or re.fullmatch(r'[A-Za-z0-9._~/-]+', path) is None:
        return None
    if any(part in ('', '.', '..') for part in path.split('/')): return None
    return base + '#' + path.lower()


def project_source_belongs(url, project):
    source = canonical_repository(url, repository_root=False)
    base = canonical_repository(project['publicRepository'])
    return source is not None and base is not None and (source == base or source.startswith(base + '/'))


def validate_consumer_project(repository, project):
    fields = {'repository', 'canonicalIdentity', 'publicRepository', 'projectPath', 'identityBasis', 'kind',
              'externalAdoption', 'openSourceBasis', 'integration', 'activityMonitoring', 'reviewedAt', 'vitalityConfidence'}
    require(isinstance(project, dict) and set(project) == fields, 'invalid consumer-project record')
    require(project['repository'] == repository, 'consumer project is bound to another purifier')
    identity = project_identity(project)
    require(identity is not None and project['canonicalIdentity'] == identity, 'consumer project needs a canonical identity')
    require(canonical_repository(project['publicRepository']) != 'https://github.com/' + repository.lower(), 'purifier itself is not an external consumer')
    require(project['kind'] == 'external-open-source-consumer' and text(project['identityBasis']), 'fixtures, demos, copies and name catalogues are not qualified consumers')
    require(date(project['reviewedAt']) and text(project['vitalityConfidence']), 'consumer project needs a reviewed vitality judgment')
    adoption = project['externalAdoption']
    require(isinstance(adoption, dict) and set(adoption) == {'projectIdentity', 'status', 'source', 'summary'}
            and adoption['projectIdentity'] == identity and adoption['status'] == 'reviewed-beyond-maintainer'
            and text(adoption['summary']), 'consumer adoption needs subject-bound beyond-maintainer evidence')
    validate_role_basis({'source': adoption['source'], 'summary': adoption['summary']})
    if adoption['source']['kind'] == 'public-primary-url':
        require(project_source_belongs(adoption['source']['url'], project), 'adoption reference belongs to another consumer project')
    for key in ('openSourceBasis', 'integration'):
        basis = project[key]
        fields = {'projectIdentity', 'sourceUrl', 'summary'} | ({'kind'} if key == 'integration' else set())
        require(isinstance(basis, dict) and set(basis) == fields and basis['projectIdentity'] == identity
                and text(basis['summary']) and primary_url(basis['sourceUrl']) and project_source_belongs(basis['sourceUrl'], project),
                'license and integration evidence must belong to the consumer project')
        if key == 'integration': require(basis['kind'] == 'actual-purifier-integration', 'a name listing is not purifier integration')
    activity = project['activityMonitoring']
    require(isinstance(activity, list) and bool(activity), 'consumer project needs activity-monitoring references')
    kinds = POLICY['ongoingUse']['substantiveActivityKinds'] + POLICY['ongoingUse']['supplementalActivityKinds']
    for item in activity:
        require(isinstance(item, dict) and set(item) == {'projectIdentity', 'sourceUrl', 'summary', 'kind'}
                and item['projectIdentity'] == identity and item['kind'] in kinds and text(item['summary'])
                and primary_url(item['sourceUrl']) and project_source_belongs(item['sourceUrl'], project), 'activity evidence must belong to the consumer project')
    require(any(item['kind'] in POLICY['ongoingUse']['substantiveActivityKinds'] for item in activity),
            'CI, stars or downloads alone do not establish consumer vitality')
    return project


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
    validate_ongoing_users(report['ongoingUsers'])
    require(not report['ongoingUsers'] or 'ongoing-use' in claims, 'a one-off report cannot supply ongoing-use subjects')
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
    require(isinstance(context, dict) and set(context) == {'repository', 'kind', 'source', 'scope', 'attribution', 'reviewedAt', 'ongoingUsers'}, 'invalid ongoing-use context')
    require(context['repository'] == repository, 'usage context belongs to another purifier')
    validate_ongoing_users(context['ongoingUsers'])
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
        require(isinstance(criterion, dict) and set(criterion) == {'state', 'summary', 'reports', 'gap', 'confidenceReason', 'usageContexts', 'consumerProjects'}, 'invalid human use criterion')
        require(criterion['state'] in ('met', 'not-met') and text(criterion['summary']), 'invalid human use judgment')
        refs = criterion['reports']
        require(isinstance(refs, list) and all(isinstance(ref, str) for ref in refs)
                and len(refs) == len(set(refs)) and all(ref in reports for ref in refs), 'unknown or duplicate human report reference')
        contexts = criterion['usageContexts']
        require(isinstance(contexts, list), 'usage contexts must be a list')
        for context in contexts:
            validate_context(repository, context)
        projects = criterion['consumerProjects']
        require(isinstance(projects, list), 'consumer projects must be a list')
        for project in projects: validate_consumer_project(repository, project)
        identities = [project['canonicalIdentity'] for project in projects]
        require(len(identities) == len(set(identities)), 'duplicate canonical consumer project')
        require(key == 'ongoingUse' or (contexts == [] and projects == []), 'ongoing contexts and consumer projects do not gate firsthand use')
        if criterion['state'] == 'not-met':
            require(text(criterion['gap']) and criterion['confidenceReason'] is None, 'missing use evidence needs an honest gap')
            continue
        require(criterion['gap'] is None, 'met human use criterion cannot assert a gap')
        require(all(reports[ref]['reporter']['kind'] == 'human' and reports[ref]['basis'] == 'firsthand'
                    and 'firsthand-use' in reports[ref]['claims'] for ref in refs), 'human use requires actual firsthand human evidence')
        if key == 'firsthandUse':
            require(bool(refs), 'met firsthand use requires reviewed reports')
        else:
            continuing_report = any('ongoing-use' in reports[ref]['claims']
                                    and has_maintainer_ongoing_user(reports[ref]['ongoingUsers']) for ref in refs)
            continuing_context = any(has_maintainer_ongoing_user(context['ongoingUsers']) for context in contexts)
            require(continuing_report or continuing_context,
                    'ongoing confidence needs reviewed maintainer ongoing use')
            require(len(projects) >= POLICY['ongoingUse']['minimumConsumerProjects'], 'ongoing confidence needs two distinct qualified open-source consumer projects')
        if key == 'ongoingUse':
            require(text(criterion['confidenceReason']) and criteria['firsthandUse']['state'] == 'met', 'ongoing use needs reviewed confidence and firsthand use')
        else:
            require(criterion['confidenceReason'] is None, 'firsthand use does not require an ongoing-use threshold')
    return review


def render_reports(repository, review):
    """Only the public reviewed record reaches rendered documentation."""
    validate_review(repository, review)
    lines = []
    def subjects(users):
        for user in users:
            label = user['publicLabel'] or 'Ongoing-use participant'
            lines.append('Ongoing-use subject: ' + escape(label) + '; maintainer status: '
                         + escape(user['maintainerStatus']) + '. ' + escape(user['useScope']))
            basis = user['statusBasis']
            if basis is not None:
                source = basis['source']
                origin = (f'<a href="{escape(source["url"], quote=True)}">Reviewed role basis</a>'
                          if source['kind'] == 'public-primary-url' else 'Reviewed private role basis')
                lines.append(origin + ': ' + escape(basis['summary']))
    for report in review['reports'].values():
        source = report['source']
        label = report['reporter']['publicLabel'] or 'Reporter'
        origin = (f'<a href="{escape(source["url"], quote=True)}">{escape(label)}</a>' if source['kind'] == 'public-primary-url'
                  else f'{escape(label)} (reviewed direct attestation)')
        lines.append(f'- {origin}, {report["reportedAt"]}; {escape(report["reporter"]["relationship"])}. '
                     f'{escape(report["scope"])} {escape(report["summary"])}')
        subjects(report['ongoingUsers'])
    for context in review['criteria']['ongoingUse']['usageContexts']:
        source = context['source']
        origin = (f'<a href="{escape(source["url"], quote=True)}">Primary use context</a>'
                  if source['kind'] == 'public-primary-url' else 'Reviewed private use context')
        lines.append(f'- {origin}, reviewed {context["reviewedAt"]}. {escape(context["scope"])} {escape(context["attribution"])}')
        subjects(context['ongoingUsers'])
    for project in review['criteria']['ongoingUse']['consumerProjects']:
        lines.append(f'- Open-source consumer: <a href="{escape(project["publicRepository"], quote=True)}">{escape(project["canonicalIdentity"])}</a>. '
                     + escape(project['identityBasis']) + ' ' + escape(project['vitalityConfidence']))
        for key, label in [('openSourceBasis', 'Open-source basis'), ('integration', 'Purifier integration')]:
            basis = project[key]
            lines.append(f'<a href="{escape(basis["sourceUrl"], quote=True)}">{label}</a>: ' + escape(basis['summary']))
        for activity in project['activityMonitoring']:
            lines.append(f'<a href="{escape(activity["sourceUrl"], quote=True)}">Activity monitoring</a>: ' + escape(activity['summary']))
        source = project['externalAdoption']['source']
        origin = (f'<a href="{escape(source["url"], quote=True)}">Beyond-maintainer adoption</a>'
                  if source['kind'] == 'public-primary-url' else 'Reviewed beyond-maintainer adoption')
        lines.append(origin + ': ' + escape(project['externalAdoption']['summary']))
    for key in HUMAN_CRITERIA:
        criterion = review['criteria'][key]
        if criterion['confidenceReason'] is not None:
            lines.append('Ongoing-use confidence: ' + escape(criterion['confidenceReason']))
        if criterion['gap'] is not None:
            label = 'Firsthand-use evidence gap' if key == 'firsthandUse' else 'Ongoing-use evidence gap'
            lines.append(label + ': ' + escape(criterion['gap']))
    return '\n'.join(lines)
