# Workflow

The Workflow package represents a particular flow of operations in the form of a
node tree.

Nodes can be represented using parent/child relationships to determine
a default connection between them. Top level nodes are typed as Action nodes
while their children are tasks. The idea being that an Action represents a broad
activity, and the tasks the specifics of that activity.  However, it is not a hard
requirement that when a workflow is constructed that relationship is maintained.

The workflow package represents the structure of a workflow. The state of the workflow
in practice and it's usage is determined by the client who uses it. The examples given will reprenset workflow in the Trade Remedies application context, how they relate
to cases and how state is maintained.

Each node in the workflow can trigger an outcome. An outcome can be internal to the
workflow, for example, if condition X is true, progress to action Y, otherwise progress
to action Z. Other outcomes can be registered externally by the client and are specific
to it's use case. For example, change case stage to X if a child node Y is acknowledged as True.


### Nodes

Node records have their unique UUID, though they also maintain a unique human readable key which allows easier handling. The `label` contains the actual description of the node.
A node has a `node_type` currently being either `Action` or `Task` as described above. Task nodes are expected to have a `parent` set which is simply a reference to their parent node model. As well, nodes have a `response_type` which describes what type of feedback the node expectes in the workflow. Normally this would be a boolean acknowledgemnt that the task has been done or not.
The `outcome_spec` of the node describes the specific data required to execute the outcome of each node if required.

### Outcomes

Outcomes are built by extending the `BaseOutcome` object which provides a common
interface the workflow can understand and use to decide if an outcome should trigger or not and what the resulting activity would be. Outcome objects can be created anywhere and registered in the outcome registry using `register_outcome` and passing the outcome class as an argument.

Outocome objects contain a unique `key` attribute and a `description` to announce their
purpose. Outcome objects will always be instantiated with the current action being performed and the full workflow state at the time which are then available to the Outcome object when it attempts to evaluate itself.
An outcome must implement the `execute` method which determines when and what should happen when this outcome is triggered against a node.

The initialisation `node` argument will determine the conditions the outcome execute against in the `outcome_spec` which is list representing the pipeline of operations.

For example:

```
[
    {
        "spec": [
            {
                "if": {
                    "key": "DRAFT_SUFFICIENT_TO_PROCEED",
                    "operator": {"name": "eq", "value": "yes"},
                    "value": "INFORM_FOREIGN_GOVERNMENT"
                }
            },
            {
                "if": {
                    "key": "DRAFT_SUFFICIENT_TO_PROCEED",
                    "operator": {"name": "eq", "value": "no"},
                    "value": "REVIEW_DRAFT"
                }
            }
        ],
        "type": "next_action"
    },
    {
        "spec": [
            {
                "if": {
                    "key": "DRAFT_SUFFICIENT_TO_PROCEED",
                    "operator": {"name": "eq", "value": "yes"},
                    "value": "SUFFICIENT_TO_PROCEED"
                }
            },
            {
                "if": {
                    "key": "DRAFT_SUFFICIENT_TO_PROCEED",
                    "operator": {"name": "eq", "value": "no"},
                    "value": "INSUFFICIENT_TO_PROCEED"
                }
            }
        ],
        "type": "case_stage_transition"
    }
]
```

The `outcome_spec` pipeline above describes two outcomes.
The first is internal (built-in) to the workflow. If the value given to `DRAFT_SUFFICIENT_TO_PROCEED` is true, return `INFORM_FOREIGN_GOVERNMENT`, otherwise, return `REVIEW_DRAFT`. The `next_action` Outcome object would know to use that value as the next node in the workflow tree.
Following that, the same condition is evaluated into the `case_stage_transition` Outcome object which knows to take the return value and use it to set the `stage` attribute of the case accordingly.

### Outcome spec rules

Outcome specs support multiple rules:

#### if

To evaluate a single element in the workflow tree, use the `if` rule, whose structure is:

```
{
    "if": {
        "key": "NODE_KEY_TO_EVALUATE",
        "operator": {"name": "eq", "value": "yes"},
        "value": "RETURN-VALUE"
    }
}
```
In this rule, the `key` is evaluated. If the value provided by the user matches the `operator` value, the `value` is returned.

#### any
Evaluates a list of workflow nodes and returns the value if any of them
evaluate to the given value
```
{
    "any": {
        "keys": ["NODE_1", "NODE_2"],
        "operator": {"name": "eq", "value": "yes"},
        "value": "RETURN-VALUE"
    }
}
```

#### all
Evaluates a list of workflow nodes and returns the value if *all* of them
evalutae to the given value.

```
{
    "all": {
        "keys": ["NODE_1", "NODE_2"],
        "operator": {"name": "eq", "value": "yes"},
        "value": "RETURN-VALUE"
    }
}
```

## The Workflow object and Workflow Templates

Although workflows can be customised per each individual use case, they can start as a copy of an existing Workflow template. These templates describe the structure of the workflow tree and are essnetially references to Node records.

At any time, a workflow template can represent itself as a `Workflow` object. Those are specialised dicts which cotains a set of additional methods and indeces to allow working with the workflow. A `Workflow` object can be instantiated using a template, in which case it will be expanded to the current set of nodes. Once it is attached to the model whose workflow is represented it's recommended to snapshot the state and retain it as to prevent mutating it if the nodes themeselves change. However, this is a specific implementation details up to the client. Workflow can also be shrunk to a collection similar to the templates where only  references to the nodes is present.


## Workflow Example using Trade Remedies Cases

Trade Remedies (TR) uses the workflow to represent the process of a case from start to finish. Each case can have a different version of the workflow which is why in the TR context, it was important to snapshot the initial workflow to retain it as is for the case's life cycle.

The TR api provides a CaseWorkflow model which ties a case to a snapshot of a workflow. It also provides a CaseWorkflowState model which holds the responses to each of the nodes. Together it is possible to overlay a current state of the case into the workflow. This also benefits from the automatic auditing functionality which allows us to provide an historic view for all the actions performed and data changed.
TR introduces the `CaseStageOutcome` outcome model which as shown in the outcome spec example above, can modify the `stage` attribute of a case based on the progress of the workflow process.


## Time Gates

Each node in the workflow can trigger a time gate. These time gates are define the number of days before the action is due.


For example, the REVIEW_DRAFT action node can trigger a time gate value of 30, which means this action is due within 30 days.
