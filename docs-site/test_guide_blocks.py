import unittest
from guide_blocks import markdown_blocks, validate_assignments
from inventory import validate_coverage


class GuideBlockTests(unittest.TestCase):
    def test_combined_native_sections_can_be_partitioned_without_duplication(self):
        source = [('Development', 'Mutable project.\n\nLanguage server.\n\nPlatform limits.')]
        plan = {'introduction': {'omitSummary': False, 'section': None}}
        selected = [{'heading':'Development','blocks':[0,2]}, {'heading':'Development','blocks':[1]}]
        validate_assignments('', source, plan, selected)
        for bad in (selected[:1], selected + selected[:1], ['Development', *selected]):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, 'exactly once'):
                validate_assignments('', source, plan, bad)
        with self.assertRaisesRegex(ValueError, 'exactly once'):
            validate_assignments('', [('Development', source[0][1]+'\n\nNew behavior.')], plan, selected)

    def test_intro_commands_and_fenced_examples_remain_intact(self):
        text = 'Setup.\n\n```sh\nfirst\n\nsecond\n```\n\nDetails.'
        blocks = markdown_blocks(text)
        self.assertEqual(len(blocks), 3)
        self.assertIn('first\n\nsecond', blocks[1])
        plan = {'introduction': {'omitSummary': False, 'section': None}}
        validate_assignments(text, [], plan, [{'heading':'@introduction','blocks':[0,1,2]}])
        plan['introduction']['section'] = 'setup'
        with self.assertRaisesRegex(ValueError, 'both wholly'):
            validate_assignments(text, [], plan, [{'heading':'@introduction','blocks':[0,1,2]}])

    def test_homepage_cannot_silently_add_an_unmodeled_purifier(self):
        html = '<a href="/first-purifier/">First</a><a href="https://nix-purifiers.github.io/next-purifier/">Next</a>'
        with self.assertRaisesRegex(ValueError, 'next-purifier'):
            validate_coverage({'first-purifier': {}}, html)
        self.assertEqual(validate_coverage({'first-purifier': {}, 'next-purifier': {}}, html),
                         {'first-purifier', 'next-purifier'})
        self.assertEqual(validate_coverage({}, '<a href="https://example.com/other-purifier/">External</a>'), set())
