import unittest

from midflight.claims import Claim, ClaimBoard


class ClaimBoardTests(unittest.TestCase):
    def setUp(self):
        self.board = ClaimBoard()
        self.board.submit(Claim("api", "Somesh", "Build API", ("api.py",), ("user-api",)))

    def test_shared_interface_across_different_files_asks_question(self):
        result = self.board.submit(Claim("ui", "Frederik", "Build screen", ("ui.tsx",), ("user-api",)))
        self.assertEqual(result.status, "needs_clarification")
        self.assertIn("Shared interfaces: user-api", result.questions[0].reason)
        self.assertIn("Overlap alone is not a conflict", result.questions[0].question)

    def test_same_file_is_a_question_not_proof_of_conflict(self):
        result = self.board.submit(Claim("edit", "Mithilesh", "Add helper", ("api.py",), ()))
        self.assertEqual(result.status, "needs_clarification")
        self.assertEqual(result.questions[0].claim_ids, ("edit", "api"))

    def test_independent_declarations_do_not_grant_approval(self):
        result = self.board.submit(Claim("docs", "Mithilesh", "Write guide", ("guide.md",), ()))
        self.assertEqual(result.status, "no_declared_overlap")
        self.assertEqual(result.questions, ())
        self.assertIn("not approval", result.limitations)

    def test_broad_goal_is_valid_but_unknown(self):
        result = self.board.submit(Claim("explore", "Frederik", "Explore history"))
        self.assertEqual(result.status, "unknown")
        self.assertIn("Unknown declarations", result.questions[0].reason)

    def test_incomplete_peer_keeps_result_unknown(self):
        self.board.submit(Claim("explore", "Frederik", "Explore history"))
        result = self.board.submit(Claim("docs", "Mithilesh", "Write guide", ("guide.md",), ()))
        self.assertEqual(result.status, "unknown")
        self.assertTrue(any("explore" in question.claim_ids for question in result.questions))

    def test_revision_replaces_previous_claim_without_self_comparison(self):
        self.board.submit(Claim("ui", "Frederik", "Build screen", ("ui.tsx",), ("user-api",)))
        result = self.board.submit(Claim("ui", "Frederik", "Build standalone mock", ("mock.tsx",), ()))
        self.assertEqual(result.status, "no_declared_overlap")
        self.assertEqual(result.compared_with, ("api",))
        following = self.board.submit(Claim("other", "Mithilesh", "Build report", ("ui.tsx",), ()))
        self.assertEqual(following.status, "no_declared_overlap")

    def test_revision_cannot_change_owner(self):
        with self.assertRaises(ValueError):
            self.board.submit(Claim("api", "Frederik", "Replace owner"))

    def test_overlap_still_surfaces_when_other_details_unknown(self):
        result = self.board.submit(Claim("ui", "Frederik", "Build screen", None, ("user-api",)))
        self.assertEqual(result.status, "needs_clarification")
        self.assertTrue(any("Unknown" in q.reason for q in result.questions))

    def test_json_validation_and_empty_lists(self):
        claim = Claim.from_dict({"id": "doc", "owner": "Mithilesh", "goal": "Write", "files": [], "interfaces": []})
        self.assertEqual(claim.files, ())
        for invalid in (
            {"id": "x", "owner": "F", "goal": "Build", "files": "api.py"},
            {"id": "x", "owner": "F", "goal": "Build", "interfaces": [3]},
            {"id": "x", "owner": "F", "goal": " "},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                Claim.from_dict(invalid)


if __name__ == "__main__":
    unittest.main()
