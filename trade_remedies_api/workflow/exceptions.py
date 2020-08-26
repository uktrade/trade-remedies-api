class InvalidParentType(Exception):
    message = "You cannot assign this element to the parent."


class DuplicateNode(Exception):
    message = "This element is already used in the workflow"


class InvalidOutcomeOperator(Exception):
    message = "Operator not implemented"


class InvalidArgument(Exception):
    message = "Invalid argument provided"


class InvalidOperatorForRule(Exception):
    message = "The operator used is not compatible with the rule"


class InvalidNode(Exception):
    message = "Invalid node"
