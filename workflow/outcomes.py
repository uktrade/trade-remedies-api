"""
Workflow actions trigger one or more outcomes.
Outcomes are defined as Outcome objects. Some outcomes are internal/built-in to the workflow,
and some can be injected in by external modules. An action will always have at least one action,
which is to determine the next action in the workflow.
Outcomes are registered with the outcome_registry dictionary.

Outcome objects implement BaseOutcome, define a unique key and provide an execute method
to perform the desired outcome.
When an outcome initialises it will receive the the triggering action and the entire workflow
and state which will be available to the execute method in order to determine what/if the
outcome should be. The details of the decision logic are defined within the action itself
as the outcome_spec, and can be changed from workflow to workflow.

Rules can also specify a `break` key which if set will stop any further rules from
processing if the rule evaluates to a truthful value

## Examples:

consider the action "Review Draft" has the following action spec which:
    * determines that the next action is either to Inform foreign governments or to go back
      to draft review, depending if the draft is deemed sufficient to proceed.
    * Changes the status of the case to 'SUFFICIENT_TO_PROCEED' if the review is deemed ok,
      or INSUFFICIENT_TO_PROCEED if not.

Action: Review Draft
outcome_spec:
    [
        {
            "type": "stage_change",
            "spec": [
                {
                    "if": {
                        "key": "DRAFT_SUFFICIENT_TO_PROCEED",
                        "operator": {
                            "name": "eq",
                            "value": "no"
                        },
                        "value": "INSUFFICIENT_TO_PROCEED"
                    }
                },
                {
                    "if": {
                        "key": "DRAFT_SUFFICIENT_TO_PROCEED",
                        "operator": {
                            "name": "eq",
                            "value": "yes"
                        },
                        "value": "SUFFICIENT_TO_PROCEED"
                    }
                }
            ]
        }
    ]


In the following example, we trigger a termination and archiving of a case, if all parties were notified.
The case is then archived using the given `value` as archiving reason.
This rule defines two outcomes: archving if the case is simply complete, or failed due to insufficient
evidence. In both cases all parties and users should be acknowledged as notified.

Action: Terminate and Archive Case
outcome_spec:
    [
        {
            "type": "archive",
            "spec": [
                {
                    "all": {
                        "key": ["NOTIFY_PARTIES", "NOTIFY_ASSIGNED_USERS", "COMPLETE"],
                        "operator": {
                            "name": "eq",
                            "value": "yes"
                        }
                        "value": "ARCHIVE_DUE_TO_COMPLETION"
                    }
                },
                {
                    "all": {
                        "key": ["NOTIFY_PARTIES", "NOTIFY_ASSIGNED_USERS", "INSUFFICIENT_EVIDENCE"],
                        "operator": {
                            "name": "eq",
                            "value": "yes"
                        }
                        "value": "ARCHIVE_DUE_TO_INSUFICIENV_EVIDENCE"
                    }
                }
            ]
        }
    ]

More complex conditions can be created using the "or" and "and" composite rule types.
eg. To return a value when all values are "yes" or "na", but at least one is "yes":

outcome_spec:
    [
        {
            "type": "archive",
            "spec": [
                {
                    "and": {
                        "conditions": [
                            {
                                "rule": "all",
                                "key": ["NOTIFY_PARTIES", "NOTIFY_ASSIGNED_USERS"],
                                "operator": {
                                    "name": "in_list",
                                    "value": ["na", "yes"]
                                }
                            },
                            {
                                "rule": "any",
                                "key": ["NOTIFY_PARTIES", "NOTIFY_ASSIGNED_USERS"],
                                "operator": {
                                    "name": "eq",
                                    "value": "yes"
                                }
                            }
                        ],
                        "value": "ARCHIVE_DUE_TO_COMPLETION"
                    }
                }
            ]
        }
    ]

"""
import os
import importlib
import inspect
import logging
from os.path import isfile, join

from .exceptions import InvalidOutcomeOperator, InvalidOperatorForRule


logger = logging.getLogger(__name__)


OUTCOME_REGISTRY = {}


def register_outcome(outcome):
    OUTCOME_REGISTRY[outcome.key.upper()] = outcome
    return OUTCOME_REGISTRY


def auto_discover_package(root_path, dir_name):
    """
    For a given package, discover all outcome artifacts within
    """
    path = os.path.join(root_path, dir_name)
    files = [f for f in os.listdir(path) if isfile(join(path, f))]
    files = [f.split(".")[0] for f in files]
    for module_name in files:
        module = importlib.import_module("{0}.{1}".format(dir_name, module_name))
        cls_members = inspect.getmembers(module, inspect.isclass)
        for _class in cls_members:
            if issubclass(_class[1], BaseOutcome):
                register_outcome(_class[1])


def auto_discover():
    """
    Auto discover all outcome artifacts and load them into the registry
    """
    path = os.path.dirname(os.path.abspath(__file__))
    for package in ["."]:
        auto_discover_package(path, package)


##########################################################################


class BaseOutcome:
    key = "UNDEFINED"
    description = "Undefined"

    def __init__(self, action, workflow, spec=None, **kwargs):
        self.action = action
        if spec:
            self.outcome_spec = [spec]
        else:
            self.outcome_spec = self.action.get("outcome_spec", [])
        self.workflow = workflow
        self.kwargs = kwargs

    def evaluate_rules(self):
        value = None
        for spec in self.outcome_spec:
            logger.debug("Spec: %s", spec["type"])
            if spec["type"].upper() == self.key.upper():
                for rule in spec.get("spec", []):
                    logger.debug("Rule: %s", rule)
                    rule_keys = list(rule.keys())
                    logger.debug("Rule keys: %s", rule_keys)
                    for key in rule_keys:
                        rule_method = f"{key}_rule"
                        logger.debug("Method: %s", rule_method)
                        if hasattr(self, rule_method):
                            new_value = getattr(self, rule_method)(rule[key])
                            value = new_value if new_value is not None else value
        return value

    def get_operator(self, operator):
        return operator.get("name", "eq"), operator.get("value")

    def eval_operator(self, operator, left, right):
        logger.debug("Operator: %s, L: %s, R: %s", operator, left, right)

        negate = operator.startswith("not_")
        if negate:
            operator = operator[4:]

        try:
            val = getattr(self, operator)(left, right)
        except AttributeError:
            raise InvalidOutcomeOperator(f"{operator} is not implemented")
        if negate:
            return not val
        else:
            return val

    def if_rule(self, rule):
        """
        A basic condition where a value is evaluated using an operator
        """
        if "key" in rule:
            eval_node = self.workflow.key_index.get(rule["key"])
        else:
            eval_node = self.action
        operator_name, operator_value = self.get_operator(rule.get("operator"))
        if eval_node:
            if self.eval_operator(operator_name, eval_node.get("value"), operator_value):
                return rule["value"]
            return None

    def any_rule(self, rule):
        """
        Any rule dictates that at least one values must be evaluated truthfully.
        """
        operator_name, operator_value = self.get_operator(rule.get("operator"))
        for key in rule["key"]:
            if self.eval_operator(
                operator_name, self.workflow.key_index.get(key, {}).get("value"), operator_value
            ):
                return rule["value"]
        return None

    def all_children_rule(self, rule):
        """
        Like all rule but looks at all children of a node, instead of a list of predefined nodes
        """
        operator_name, operator_value = self.get_operator(rule.get("operator"))
        all_rules = [
            self.eval_operator(operator_name, action.get("value"), operator_value)
            for action in self.action["children"]
        ]
        if all(all_rules):
            return rule["value"]
        return None

    def all_rule(self, rule):
        """
        All rule dictates all values must be evaluated truthfully.
        """
        operator_name, operator_value = self.get_operator(rule.get("operator"))
        all_rules = [
            self.eval_operator(
                operator_name, self.workflow.key_index.get(key, {}).get("value"), operator_value
            )
            for key in rule["key"]
        ]
        if all(all_rules):
            return rule["value"]
        return None

    def always_rule(self, rule):
        """
        Always does not require any conditions or operators.
        It will always run regardless.
        """
        return rule["value"]

    def all_variate_rule(self, rule):
        """
        Similar to all rule, but requires at least one of each of values checked (i.e., must include
        a variation of the values). This is usable when using the in_list operator as otherwise variation
        is not possible
        """
        operator_name, operator_value = self.get_operator(rule.get("operator"))
        if operator_name not in ("in_list",):
            raise InvalidOperatorForRule(
                "all_variate rule requires an interable based operator like in_list"
            )
        distinct_values = set([])
        all_rules = []
        for key in rule["key"]:
            node_value = self.workflow.key_index.get(key, {}).get("value")
            all_rules.append(self.eval_operator(operator_name, node_value, operator_value))
            distinct_values.add(node_value)
        if all(all_rules) and len(operator_value) == len(distinct_values):
            return rule["value"]
        return None

    def and_rule(self, rule):
        for spec in rule["conditions"]:
            inner_rule = spec.pop("rule")
            rule_method = f"{inner_rule}_rule"
            if hasattr(self, rule_method):
                temp_spec = spec.copy()
                temp_spec["value"] = rule["value"]
                value = getattr(self, rule_method)(temp_spec)
                if value is None:
                    return
        return rule["value"]

    def or_rule(self, rule):
        results = []
        for spec in rule["conditions"]:
            inner_rule = spec.pop("rule")
            rule_method = f"{inner_rule}_rule"
            if hasattr(self, rule_method):
                temp_spec = spec.copy()
                temp_spec["value"] = rule["value"]
                value = getattr(self, rule_method)(temp_spec)
                results.append(value is not None)
        if any(results):
            return rule["value"]

    def eq(self, left, right):
        """
        Equals operator - left must be equal to right
        """
        return left == right

    def oneof(self, left, right):
        return left in right.split(",")

    def in_list(self, left, right):
        """
        In operator - left must be in right
        """
        return left in right

    def blank(self, left, right):
        return left in [None, ""]

    def execute(self):
        raise NotImplementedError()
