import copy
import unittest

from content import render


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.contract = {'sections': [
            {'id': 'workflow', 'title': 'Development loop', 'shared': {
                'standard': 'Run `{project} lock` to retain existing pins.'}},
            {'id': 'editor', 'title': 'Editor', 'shared': {}},
        ]}
        self.page = {'version': 1, 'repository': 'nix-purifiers/example-purifier',
                     'summary': 'Example.', 'facts': {}, 'sections': {
                         'workflow': {'use': 'standard', 'details': 'Commit the lock.'},
                         'editor': {'omit': 'No editor integration is provided.'}}}

    def test_shared_copy_updates_every_consumer(self):
        self.assertIn('`example-purifier lock`', render(self.page, self.contract)[0])
        self.contract['sections'][0]['shared']['standard'] = 'Updated shared copy.'
        self.assertIn('Updated shared copy.', render(self.page, self.contract)[0])

    def test_differences_are_recorded(self):
        self.page['sections']['workflow'] = {
            'replace': 'Different workflow.', 'reason': 'No native lock command.'}
        markdown, differences = render(self.page, self.contract)
        self.assertIn('Different workflow.', markdown)
        self.assertNotIn('retain existing pins', markdown)
        self.assertEqual(differences[0]['reason'], 'No native lock command.')
        self.assertEqual(differences[1]['kind'], 'omitted')

    def test_rejects_missing_unknown_and_unexplained_sections(self):
        for edit in (
            lambda p: p['sections'].pop('editor'),
            lambda p: p['sections'].update(typo={'replace': 'Oops', 'reason': 'Oops'}),
            lambda p: p['sections'].update(editor={'replace': 'Custom'}),
            lambda p: p['sections'].update(workflow={'use': 'typo'}),
            lambda p: p['sections'].update(workflow={'use': 'standard', 'replace': 'Both'}),
            lambda p: p['sections'].update(workflow={'use': 'standard', 'detials': 'Typo'}),
        ):
            page = copy.deepcopy(self.page)
            edit(page)
            with self.subTest(page=page), self.assertRaises(ValueError):
                render(page, self.contract)

    def test_sections_follow_contract_order(self):
        self.page['sections']['editor'] = {'replace': 'Editor details.', 'reason': 'Custom editor.'}
        markdown, _ = render(self.page, self.contract)
        self.assertLess(markdown.index('## Development loop'), markdown.index('## Editor'))

    def test_facts_drive_copy_and_require_evidence(self):
        self.contract['facts'] = {'lockfiles': {'type': 'strings'}}
        self.contract['sections'][0]['shared']['standard'] = 'Commit {facts.lockfiles}.'
        self.page['facts'] = {'lockfiles': {
            'state': 'known', 'value': ['native.lock', 'companion.json'],
            'sources': ['README.md#quickstart']}}
        self.assertIn('Commit native.lock, companion.json.', render(self.page, self.contract)[0])
        self.page['facts']['lockfiles']['sources'] = []
        with self.assertRaises(ValueError):
            render(self.page, self.contract)

    def test_unknown_facts_cannot_be_silently_used_as_claims(self):
        self.contract['facts'] = {'lockfiles': {'type': 'strings'}}
        self.page['facts'] = {'lockfiles': {'state': 'unknown', 'reason': 'Needs review.'}}
        render(self.page, self.contract)
        self.contract['sections'][0]['shared']['standard'] = 'Commit {facts.lockfiles}.'
        with self.assertRaises(ValueError):
            render(self.page, self.contract)

    def test_repository_cannot_escape_output_directory(self):
        self.page['repository'] = 'owner/..'
        with self.assertRaises(ValueError):
            render(self.page, self.contract)


if __name__ == '__main__':
    unittest.main()
