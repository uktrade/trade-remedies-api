from django.test import SimpleTestCase

from workflow.models import Workflow
from workflow.outcomes import BaseOutcome


class MyOutcome(BaseOutcome):
    key = "MY_OUTCOME"

    def __init__(self, action, workflow, spec=None, **kwargs):
        super().__init__(action, workflow, spec, **kwargs)
        self.call_count = 0

    def execute(self):
        self.call_count += 1


class BaseOutcomeTests(SimpleTestCase):
    def setup_outcome(self, spec, key_values=None):
        key_values = key_values or {}
        full_spec = {
            "spec": spec,
            "type": "my_outcome",
        }
        workflow = Workflow(
            {
                "root": [
                    {
                        "key": "KEY_1",
                        "value": key_values.get("KEY_1", "na"),
                        "children": [
                            {"key": "KEY_1.1", "value": key_values.get("KEY_1.1", "na"),},
                            {"key": "KEY_1.2", "value": key_values.get("KEY_1.2", "na"),},
                            {"key": "KEY_1.3", "value": key_values.get("KEY_1.3", "na"),},
                        ],
                        "outcome_spec": full_spec,
                    }
                ]
            }
        )
        action = workflow["root"][0].copy()
        return MyOutcome(action, workflow, full_spec)

    def get_all_eq_na_spec(self):
        return [
            {
                "all": {
                    "key": ["KEY_1", "KEY_1.1", "KEY_1.2", "KEY_1.3"],
                    "value": "VAL_1",
                    "operator": {"name": "eq", "value": "na"},
                }
            }
        ]

    def test_all_eq_rule_when_true(self):
        outcome = self.setup_outcome(self.get_all_eq_na_spec())
        result = outcome.evaluate_rules()

        self.assertEqual(result, "VAL_1")

    def test_all_eq_rule_when_false(self):
        outcome = self.setup_outcome(self.get_all_eq_na_spec(), key_values={"KEY_1.2": "yes"})
        result = outcome.evaluate_rules()

        self.assertIsNone(result)

    def get_all_in_list_yes_na_spec(self):
        return [
            {
                "all": {
                    "key": ["KEY_1", "KEY_1.1", "KEY_1.2", "KEY_1.3"],
                    "value": "VAL_1",
                    "operator": {"name": "in_list", "value": ["yes", "na"],},
                }
            }
        ]

    def test_all_in_list_rule_when_true(self):
        outcome = self.setup_outcome(
            self.get_all_in_list_yes_na_spec(), key_values={"KEY_1": "yes", "KEY_1.3": "yes"}
        )
        result = outcome.evaluate_rules()

        self.assertEqual(result, "VAL_1")

    def test_all_in_list_rule_when_false(self):
        outcome = self.setup_outcome(
            self.get_all_in_list_yes_na_spec(), key_values={"KEY_1": "yes", "KEY_1.3": "no"}
        )
        result = outcome.evaluate_rules()

        self.assertIsNone(result)

    def get_any_eq_na_spec(self):
        return [
            {
                "any": {
                    "key": ["KEY_1", "KEY_1.1", "KEY_1.2", "KEY_1.3"],
                    "value": "VAL_1",
                    "operator": {"name": "eq", "value": "na",},
                }
            }
        ]

    def test_any_eq_rule_when_true(self):
        outcome = self.setup_outcome(
            self.get_any_eq_na_spec(), key_values={"KEY_1": "yes", "KEY_1.3": "yes"}
        )
        result = outcome.evaluate_rules()

        self.assertEqual(result, "VAL_1")

    def test_any_eq_rule_when_false(self):
        outcome = self.setup_outcome(
            self.get_all_in_list_yes_na_spec(),
            key_values={"KEY_1": "yes", "KEY_1.1": "yes", "KEY_1.2": "yes", "KEY_1.3": "no"},
        )
        result = outcome.evaluate_rules()

        self.assertIsNone(result)

    def get_if_eq_na_spec(self):
        return [
            {"if": {"key": "KEY_1", "value": "VAL_1", "operator": {"name": "eq", "value": "na",}}}
        ]

    def test_if_rule_when_true(self):
        outcome = self.setup_outcome(self.get_if_eq_na_spec())
        result = outcome.evaluate_rules()

        self.assertEqual(result, "VAL_1")

    def test_if_rule_when_false(self):
        outcome = self.setup_outcome(self.get_if_eq_na_spec(), key_values={"KEY_1": "yes"})
        result = outcome.evaluate_rules()

        self.assertIsNone(result)

    def get_all_variate_in_list_yes_na_spec(self):
        return [
            {
                "all_variate": {
                    "key": ["KEY_1", "KEY_1.1", "KEY_1.2", "KEY_1.3"],
                    "value": "VAL_1",
                    "operator": {"name": "in_list", "value": ["yes", "na"],},
                }
            }
        ]

    def test_all_variate_in_list_rule_when_true(self):
        outcome = self.setup_outcome(
            self.get_all_variate_in_list_yes_na_spec(),
            key_values={"KEY_1": "yes", "KEY_1.3": "yes"},
        )
        result = outcome.evaluate_rules()

        self.assertEqual(result, "VAL_1")

    def test_all_variate_in_list_rule_when_false(self):
        outcome = self.setup_outcome(
            self.get_all_variate_in_list_yes_na_spec(), key_values={"KEY_1": "yes", "KEY_1.3": "no"}
        )
        result = outcome.evaluate_rules()
        self.assertIsNone(result)

    def test_all_variate_in_list_rule_when_false_without_yes(self):
        outcome = self.setup_outcome(self.get_all_variate_in_list_yes_na_spec())
        result = outcome.evaluate_rules()

        self.assertIsNone(result)

    def test_all_variate_in_list_rule_when_false_without_na(self):
        outcome = self.setup_outcome(
            self.get_all_variate_in_list_yes_na_spec(),
            key_values={"KEY_1": "yes", "KEY_1.1": "yes", "KEY_1.2": "yes", "KEY_1.3": "yes",},
        )
        result = outcome.evaluate_rules()

        self.assertIsNone(result)

    def get_chained_if_spec(self):
        return [
            {"if": {"key": "KEY_1", "value": "YES!", "operator": {"name": "eq", "value": "yes"}}},
            {"if": {"key": "KEY_1", "value": "NA!", "operator": {"name": "eq", "value": "na"}}},
        ]

    def test_chained_if_rule_when_na(self):
        outcome = self.setup_outcome(self.get_chained_if_spec())
        result = outcome.evaluate_rules()

        self.assertEqual(result, "NA!")

    def test_chained_if_rule_when_yes(self):
        outcome = self.setup_outcome(self.get_chained_if_spec(), key_values={"KEY_1": "yes"})
        result = outcome.evaluate_rules()

        self.assertEqual(result, "YES!")

    def get_composed_and_all_any_yes_na_spec(self):
        """
        The intention of this spec would be to have all keys have a value of
        `yes` or `na`, but at least one must be `yes`.
        """
        return [
            {
                "and": {
                    "conditions": [
                        {
                            "rule": "all",
                            "key": ["KEY_1", "KEY_1.1", "KEY_1.2", "KEY_1.3"],
                            "operator": {"name": "in_list", "value": ["yes", "na"],},
                        },
                        {
                            "rule": "any",
                            "key": ["KEY_1", "KEY_1.1", "KEY_1.2", "KEY_1.3"],
                            "operator": {"name": "eq", "value": "yes",},
                        },
                    ],
                    "value": "VAL_1",
                }
            }
        ]

    def test_composed_and_all_any_rule_when_true(self):
        outcome = self.setup_outcome(
            self.get_composed_and_all_any_yes_na_spec(),
            key_values={"KEY_1": "yes", "KEY_1.3": "yes"},
        )
        result = outcome.evaluate_rules()

        self.assertEqual(result, "VAL_1")

    def test_commposed_and_all_any_rule_when_any_fails(self):
        outcome = self.setup_outcome(self.get_composed_and_all_any_yes_na_spec())
        result = outcome.evaluate_rules()

        self.assertIsNone(result)

    def test_composed_and_all_any_rule_when_all_fails(self):
        outcome = self.setup_outcome(
            self.get_composed_and_all_any_yes_na_spec(),
            key_values={"KEY_1": "yes", "KEY_1.3": "no"},
        )
        result = outcome.evaluate_rules()

        self.assertIsNone(result)

    def get_composed_or_if_eq_spec(self):
        return [
            {
                "or": {
                    "conditions": [
                        {"rule": "if", "key": "KEY_1", "operator": {"name": "eq", "value": "yes",}},
                        {
                            "rule": "if",
                            "key": "KEY_1.1",
                            "operator": {"name": "in_list", "value": ["yes", "na"],},
                        },
                    ],
                    "value": "VAL_1",
                }
            }
        ]

    def test_composed_or_if_rule_when_all_true(self):
        outcome = self.setup_outcome(self.get_composed_or_if_eq_spec(), key_values={"KEY_1": "yes"})
        result = outcome.evaluate_rules()

        self.assertEqual(result, "VAL_1")

    def test_composed_or_if_rule_when_partially_true(self):
        outcome = self.setup_outcome(self.get_composed_or_if_eq_spec(), key_values={"KEY_1": "no"})
        result = outcome.evaluate_rules()

        self.assertEqual(result, "VAL_1")

    def test_composed_or_if_rule_when_fails(self):
        outcome = self.setup_outcome(
            self.get_composed_or_if_eq_spec(), key_values={"KEY_1.1": "no"}
        )
        result = outcome.evaluate_rules()

        self.assertIsNone(result)

    def get_not_blank_spec(self):
        return [{"if": {"key": "KEY_1", "value": "VAL_1", "operator": {"name": "not_blank"}}}]

    def test_not_blank_operator(self):
        outcome = self.setup_outcome(self.get_not_blank_spec(), key_values={"KEY_1": "something"})
        result = outcome.evaluate_rules()

        self.assertEqual(result, "VAL_1")

    def test_not_blank_operator_when_fails(self):
        outcome = self.setup_outcome(self.get_not_blank_spec(), key_values={"KEY_1": ""})
        result = outcome.evaluate_rules()

        self.assertIsNone(result)

    def get_not_eq_spec(self):
        return [
            {
                "if": {
                    "key": "KEY_1",
                    "value": "VAL_1",
                    "operator": {"name": "not_eq", "value": "na",},
                }
            }
        ]

    def test_not_eq_operator(self):
        outcome = self.setup_outcome(self.get_not_eq_spec(), key_values={"KEY_1": "something"})
        result = outcome.evaluate_rules()

        self.assertEqual(result, "VAL_1")

    def test_not_eq_operator_when_fails(self):
        outcome = self.setup_outcome(self.get_not_eq_spec())
        result = outcome.evaluate_rules()

        self.assertIsNone(result)

    def get_always_spec(self):
        return [{"always": {"value": "VAL_1"}}]

    def test_always_operator(self):
        outcome = self.setup_outcome(self.get_always_spec())
        result = outcome.evaluate_rules()

        self.assertEqual(result, "VAL_1")
