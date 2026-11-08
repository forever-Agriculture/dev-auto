# MODULE: test_away_precedence.py - W1-W3 rule precedence and presence-specific dispatch bounds
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'skills/dev-auto'
LINE = "While the owner is away, BMN's Away notice takes precedence over skill instructions for messages, consultant retries and provider changes, clarification cards, planning questions and report opinions; it grants no authority."

def words(path):
    return ' '.join((ROOT / path).read_text().split())

class AwayPrecedence(unittest.TestCase):
    def test_skill_and_routes_name_the_same_away_precedence(self):
        for path in ['SKILL.md', 'references/models.md']:
            self.assertIn(LINE, words(path))

    def test_go_named_messages_need_exact_answered_text_while_away(self):
        text = words('SKILL.md')
        self.assertIn("While the owner is present, a message the go's Run needs name", text)
        self.assertIn('While he is away, a named purpose alone does not authorize sending', text)
        self.assertIn('exact message text must be on his answered card', text)
        self.assertIn('draft on one non-blocking `bmn ask` card', text)
        self.assertIn('spend_ledger.py message reserve', text)

    def test_away_consultant_does_not_inherit_present_retry_rules(self):
        text = words('references/models.md')
        self.assertIn('When an ask does not answer, while the owner is present', text)
        self.assertIn('one stable key, a bounded time limit, no recursion and no other provider', text)
        self.assertIn('On refusal, timeout or uncertain completion, read the existing ask record instead of asking again', text)
        self.assertIn('do not use a new retry key or change providers', text)
        self.assertIn('creates no dispatch or spending authority', text)

if __name__ == '__main__':
    unittest.main()
