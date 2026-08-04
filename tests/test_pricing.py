import unittest

from goldenclaw import pricing


class LookupTest(unittest.TestCase):
    def test_specific_prefix_wins_over_general(self):
        # claude-opus-4-1 ($15/$75) must match before claude-opus-4 ($5/$25).
        self.assertEqual(pricing.lookup("claude-opus-4-1"), (15.0, 75.0))
        self.assertEqual(pricing.lookup("claude-opus-4-8"), (5.0, 25.0))

    def test_unknown_model_returns_none(self):
        self.assertIsNone(pricing.lookup("<synthetic>"))
        self.assertIsNone(pricing.lookup("gpt-5"))


class EstimateTest(unittest.TestCase):
    def test_cache_weights_applied(self):
        # 1M of each category on a $10/$50 model:
        # input 10 + output 50 + cache write 12.5 + cache read 1.0 = 73.5
        total, per_model, unpriced = pricing.estimate_cost({
            "claude-fable-5": {
                "input_tokens": 1_000_000, "output_tokens": 1_000_000,
                "cache_creation_input_tokens": 1_000_000,
                "cache_read_input_tokens": 1_000_000,
            }
        })
        self.assertAlmostEqual(total, 73.5)
        self.assertEqual(unpriced, [])

    def test_unpriced_models_reported_not_guessed(self):
        total, per_model, unpriced = pricing.estimate_cost({
            "<synthetic>": {"input_tokens": 5_000_000},
        })
        self.assertEqual(total, 0)
        self.assertEqual(unpriced, ["<synthetic>"])


class ParseTokensTest(unittest.TestCase):
    def test_ritual_budget_shorthand(self):
        from goldenclaw.ritual import _parse_tokens
        self.assertEqual(_parse_tokens("25M"), 25_000_000)
        self.assertEqual(_parse_tokens("500k"), 500_000)
        self.assertEqual(_parse_tokens("1,000,000"), 1_000_000)
        self.assertIsNone(_parse_tokens("a lot"))
        self.assertIsNone(_parse_tokens(""))


if __name__ == "__main__":
    unittest.main()
