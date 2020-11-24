import uuid
from copy import deepcopy
import logging

from django.db import models
from django.contrib.postgres import fields
from graphviz import Digraph
from core.utils import rekey
from .exceptions import (
    DuplicateNode,
    InvalidArgument,
    InvalidNode,
)
from .outcomes import OUTCOME_REGISTRY
from .response_types import RESPONSE_TYPES

logger = logging.getLogger(__name__)


RT = rekey(RESPONSE_TYPES, "id", rekey_as="key")


class WorkflowTemplate(models.Model):
    """
    A template is a tree of actions and tasks that represent a potential
    starting point workflow for a case. The tree is built using references to
    Workflow Node models, and can be expanded into a snapshot view of that tree,
    capturing the current state of each node.
    Therefore, although the template can be modified at any time, once attached
    to a case a snapshot copy of it's workflow is then fixed to the case
    (yet still mutable in the case context)
    A template can be as simple as a list of node keys in the form of:
        {
            "key": "UNQIUE_KEY"
        }
    in which case, the template will always use the current set of children
    of that node, or specify an overriding "children" key which specifies a similar
    list of child keys.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=250, null=False, blank=False)
    locked = models.BooleanField(default=False)
    template = fields.JSONField(null=False, blank=False)

    def __str__(self):
        return self.name

    @property
    def workflow(self):
        return Workflow(init_from_template=self)

    def to_dict(self, expand=True):
        return {
            "id": str(self.id),
            "name": str(self.name),
            "locked": self.locked,
            "template": self.template,
            "workflow": self.workflow,
        }

    def to_dot_file(self):
        self.workflow.to_dot_file()


class Workflow(dict):
    """
    A dict based representation of a workflow which can be saved as a snapshot
    of that workflow for a given moment in time.
    """

    BOILERPLATE = {"meta": {}, "root": []}  # Empty workflow boilerplate

    def __init__(self, *args, **kwargs):
        self.template = None
        # hold an index by key and response type which will be lazy loaded on request
        self._index = {"key": {}, "type": {}}
        if kwargs.get("init_from_template"):
            self.template = deepcopy(kwargs["init_from_template"])
            args = [self.template.template]
        super().__init__(*args)
        self.key_set = set([])

    def index_workflow(self):
        """
        Index all nodes using the key and type
        """

        def index_level(level):
            for _item in level:
                self._index["key"][_item["key"]] = _item
                if _item.get("response_type"):
                    key = _item["response_type"].get("key", "")
                    self._index["type"].setdefault(key, [])
                    self._index["type"][key].append(_item)
                index_level(_item.get("children", []))

        index_level(self.get("root", []))
        return self._index

    @property
    def index(self):
        """
        DEPRECATED
        Index all actions and tasks using their unique ids
        """
        _index = {}
        for _action in self.get("root", []):
            _index[_action["id"]] = _action
            for _task in _action.get("children", []):
                _index[_task["id"]] = _task
        return _index

    @property
    def key_index(self):
        """
        Index all nodes using the key
        """
        if not self._index["key"]:
            self.index_workflow()
        return self._index["key"]

    @property
    def type_index(self):
        """
        Index all nodes using the key
        """
        if not self._index["type"]:
            self.index_workflow()
        return self._index["type"]

    def get_node(self, key):
        """
        Return a node by key
        """
        return self.key_index.get(key)

    def validate_node(self, node):
        """
        Validate a single node.
        A node requires a unique key and a label.
        If the node describes a response type, it should be one of the registered response types
        """
        required = ["key", "label"]
        if all([k in node for k in [key for key in required]]) and not node["key"] in self.key_set:
            self.key_set.add(node["key"])
            #  Code used to migrate the templates. Leave for now.
            # if 'id' in node:
            #     del node['id']
            # if 'node_type' in node:
            #     del node['node_type']
            # if 'parent' in node:
            #     del node['parent']
            # if 'order' in node:
            #     del node['order']
            # if node.get('response_type') and 'id' in node['response_type']
            # and node['response_type']['id'] in RT:
            #     rt = RT[node['response_type']['id']]
            #     if 'id' in rt:
            #         del rt['id']
            #     node['response_type'] = rt
            #############
            return True
        else:
            raise InvalidNode(f"The node {node['key']} is invalid")

    def validate_branch(self, node=None):
        if node is None:
            self.key_set = set([])
            valid = self.validate_branch(node=self.get("root", []))
        elif isinstance(node, list):
            for item in node:
                valid = self.validate_branch(node=item)
        elif isinstance(node, dict):
            valid = self.validate_node(node)
            if node.get("children", []):
                valid = self.validate_branch(node["children"])
        return valid

    def to_dot_file(self):
        dot = Digraph(comment=self.template.name)
        for action in self["root"]:
            dot.node(action["id"], action["label"])
            for task in action.get("children", []):
                dot.node(task["id"], task["label"])
                dot.edge(action["id"], task["id"])
        dot.render("./workflow.gv", view=True)

    def set(self, element, parent_id=None, index=None):
        """
        Set a given element into the workflow.
        The element will be assigned under the given parent, if the relationship is allowed.
        It will also append the element to the children list or insert at a given position.
        Attempting to assign an invalid relationship (e.g., Task->Stage) will raise an
        InvalidParentType exception.
        """
        _element = element.to_dict() if hasattr(element, "to_dict") else element
        if self.contains(_element.get("id")):
            raise DuplicateNode(f"{_element} is already included in this workflow")
        if parent_id:
            parent = self.index[parent_id]
        else:
            self["root"].append(_element)
            return self
        # if _element.get('node_type', {}).get('id') == 'Task' and parent.get('_type') != 'Action':
        #     raise InvalidParentType('Task must be a child of an Action')
        parent.setdefault("children", [])
        if index is None:
            parent["children"].append(_element)
        else:
            parent["children"].insert(index, _element)
        return self

    def shrink(self, root=None, shrink_keys=None, include_children=True):
        """
        Reduce the workflow into a minimal id-only structure.
        """
        shrink_keys = shrink_keys or ("key",)

        def reduce_dict(d):
            _reduced = {}
            for key in shrink_keys:
                if key in d:
                    _reduced[key] = d[key]
            return _reduced

        root = root if root is not None else self
        _reduced = reduce_dict(root)
        _types = ("root", "children") if include_children else ("root",)
        for _type in _types:
            if _type in root:
                _reduced[_type] = [self.shrink(item) for item in root[_type]]
                break
        return _reduced

    def contains(self, key):
        """
        Returns True if the given key (id) is already part of this workflow.
        """
        return key in self.index

    def evaluate_outcome(self, node_key, **kwargs):
        """
        Evaluate the outcome spec of a given node by it's unique key.
        Execute each outcome object resulting
        """
        node = self.key_index[node_key]
        if node.get("outcome_spec"):
            for spec in node["outcome_spec"]:
                if spec["type"].upper() in OUTCOME_REGISTRY:
                    Outcome = OUTCOME_REGISTRY[spec["type"].upper()]
                    outcome = Outcome(node, self, spec=spec, **kwargs)
                    result = outcome.execute()
        else:
            logger.debug(f"NO outcome spec: {node.get('outcome_spec')}")
        return

    def key_precedes(self, key_1, key_2):
        """
        Returns True if key_1 occurs before key_2 in the workflow.
        """

        def _key_precedes(key_1, key_2, nodes=None):
            workflow = nodes or self["root"]
            found = None
            for node in workflow:
                if found:
                    break
                if node["key"] == key_1:
                    found = key_1
                elif node["key"] == key_2:
                    found = key_2
                elif node.get("children"):
                    found = _key_precedes(key_1, key_2, node["children"])
            return found

        return _key_precedes(key_1, key_2) == key_1


class StateManager(models.Manager):
    MUTABLE = True

    def current_value(self, key, **kwargs):
        """
        Get the current (latest) value assigned to a workflow state.
        Additional kwargs can be passed to filter by a relevant model associated with
        the keys (as set by extending model)
        """
        try:
            if self.MUTABLE:
                value = self.get(key=key, **kwargs)
            else:
                value = self.filter(key=key, **kwargs).order_by("-created_at").first()
            return value.value if value else None
        except State.DoesNotExist:
            return None

    def set_value(self, key, value, due_date=None, **kwargs):
        """
        Set a value on a state item.
        Returns a tuple of the state model and a boolean if it was created
        (new state value) or updated
        """
        if self.MUTABLE:
            state = self.create(key=key, **kwargs)
        else:
            state, created = self.get_or_create(key=key, **kwargs)
        state.value = value
        if due_date:
            state.due_date = due_date
            state.save()
        state.save()
        return state, created

    def workflow_state(self, workflow, **kwargs):
        """
        For a given Workflow object, overlay the current state data or a
        fresh one from state.
        """
        if not isinstance(workflow, (Workflow, dict)):
            raise InvalidArgument(
                (
                    "Invalid argument passed to workflow_state."
                    "Requires a Workflow object or a dict representation of one."
                )
            )
        elif isinstance(workflow, dict):
            workflow = Workflow(workflow)
        for key in workflow.key_index:
            state.key_index[key]["value"] = self.current_value(key, **kwargs)  # noqa: F821
            # due_date = CaseWorkflowState.objects.current_due_date(self.case, key)
            # if due_date:
            #     state.key_index[key]['due_date'] = due_date

        state["meta"] = {}  # noqa: F821
        for key in State.BUILT_IN_STATE_KEYS:
            value = self.current_value(key, **kwargs)
            state["meta"][key] = value  # noqa: F821
        return state  # noqa: F821


class State(models.Model):
    """
    Workflow state is an insert only immutable key/value store of workflow state.
    Each key corresponds to a node's key and it's subsequent value as set in the application.
    Each item in this model represents an acknowledgement taken on
    any of the workflow's nodes. The item is indexed by the node key and
    can be used to construct the complete state.
    It is allowed to insert multiple updates to this model, though only the last
    one is considered current.
    Ths State model is abstract and is meant to be used by extension so that it can
    capture the context of the application. The extending object would probably add
    references to the relevant models this is relating to.
    Values are stored as JSON objects and can be as simple or as complex as required.
    """

    BUILT_IN_STATE_KEYS = (
        "CURRENT",
        "CURRENT_DUE_DATE",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=250, null=False, blank=False)
    value = fields.JSONField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    last_modified = models.DateTimeField(auto_now=True, null=True)

    objects = StateManager()

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.key}={self.value}"
