import logging

from django.db import models
from django.contrib.postgres import fields
from core.base import BaseModel
from workflow.models import Workflow


logger = logging.getLogger(__name__)


class CaseWorkflowManager(models.Manager):
    def snapshot_from_template(self, case, template, reset_state=False, requested_by=None):
        created = True
        try:
            case_workflow = CaseWorkflow.objects.get(case=case)
            created = False
        except CaseWorkflow.DoesNotExist:
            case_workflow = CaseWorkflow.objects.create(case=case, user_context=requested_by)
        case_workflow.set_user_context(requested_by)
        case_workflow.workflow = template.workflow
        case_workflow.save()
        if reset_state:
            CaseWorkflowState.objects.filter(case=case).delete()
        return case_workflow, created


class CaseWorkflow(BaseModel):
    case = models.OneToOneField(
        "cases.Case", related_name="workflow", null=False, blank=False, on_delete=models.PROTECT
    )
    workflow = fields.JSONField(default=dict)

    objects = CaseWorkflowManager()

    BUILT_IN_STATE_KEYS = (
        "CURRENT_ACTION",
        "CURRENT_ACTION_DUE_DATE",
    )

    def __str__(self):
        return f"Workflow: {self.case}"

    def as_workflow(self):
        return Workflow(self.workflow)

    @property
    def meta(self):
        return self.workflow.get("meta", {})

    def replace_workflow(self, workflow):
        self.workflow = workflow
        return self.save()

    def state_index(self):
        """
        Return an index of saved key values as a dict of key: (value, due_date)
        """
        values = CaseWorkflowState.objects.filter(case=self.case, deleted_at__isnull=True)
        return {cws.key: (cws.value, cws.due_date) for cws in values}

    def get_state(self):
        """
        Return the current state data or a fresh one from workflow
        """
        # return Workflow(self.state) if self.state else self.as_workflow()
        state = self.as_workflow()
        value_index = self.state_index()
        for key in state.key_index:
            _value = value_index.get(key, (None, None))
            state.key_index[key]["value"] = _value[0]
            if _value[1]:  # due_date
                state.key_index[key]["due_date"] = _value[1]

        state["meta"] = {}
        for key in self.BUILT_IN_STATE_KEYS:
            _value = value_index.get(key, (None, None))
            state["meta"][key] = _value[0]
        return state


class CaseWorkflowStateManager(models.Manager):
    def set_forward_value(
        self, key, case, value, due_date=None, requested_by=None, reset_due_date=False
    ):
        current_value = self.current_value(case, key)
        workflow = case.workflow.as_workflow()
        if value and (not current_value or workflow.key_precedes(current_value, value)):
            state, created = self.set_value(
                case,
                key,
                value,
                due_date=due_date,
                requested_by=requested_by,
                reset_due_date=reset_due_date,
            )
            return state, created
        else:
            logger.info("Unable to set key %s: %s precedes %s", key, value, current_value)
            return None, False

    def set_next_action(self, case, value, due_date=None, requested_by=None):
        return self.set_forward_value(
            "CURRENT_ACTION", case, value, due_date=due_date, requested_by=requested_by
        )

    def set_next_notice(self, case, value, due_date=None, requested_by=None, reset_due_date=False):
        """
        Set the next action state key and it's due date if provided.
        If the reset_due_date argument is True,
        the due date will be reset to None regardless of due date provided
        """
        return self.set_forward_value(
            "NEXT_NOTICE",
            case,
            value,
            due_date=due_date,
            requested_by=requested_by,
            reset_due_date=reset_due_date,
        )

    def current_value(self, case, key):
        """
        Get the current (latest) value assigned to a workflow node
        """
        try:
            value = CaseWorkflowState.objects.get(case=case, key=key)
            return value.value
        except CaseWorkflowState.DoesNotExist:
            return None

    def current_due_date(self, case, key):
        """
        Get the current due date
        """
        try:
            value = CaseWorkflowState.objects.get(case=case, key=key)
            return value.due_date
        except CaseWorkflowState.DoesNotExist:
            return None

    def set_value(
        self, case, key, value, due_date=None, requested_by=None, mutate=True, reset_due_date=False
    ):
        """
        Set a value on a case state item.
        Returns a tuple of the state model and a boolean if it was created
        (new state value) or updated.
        If mutate is False, and a value already exists,
        it will be marked deleted and a new one created.
        If reset_due_date is True,
        the due date will be set to None regardless of the due date provided
        """
        created = None
        try:
            state = CaseWorkflowState.objects.get(case=case, key=key, deleted_at__isnull=True)
            created = False
            if state.value == value and state.due_date == due_date:
                return state, created
            if not mutate:
                state.delete()
                raise CaseWorkflowState.DoesNotExist()
        except CaseWorkflowState.DoesNotExist:
            state = CaseWorkflowState.objects.create(case=case, key=key)
            created = True
        state.set_user_context(requested_by)
        state.value = value
        if due_date or reset_due_date:
            state.due_date = None if reset_due_date else due_date
            state.save()
        state.save()
        return state, created

    def value_index(self, case, keys=None):
        """
        Index all or a list of given keys
        into a dict of tuples each in the shape of (value, due_date)
        """
        values = self.filter(case=case, deleted_at__isnull=True)
        if keys:
            values = values.filter(key__in=keys)
        return {val.key: (val.value, val.due_date) for val in values}


class CaseWorkflowState(BaseModel):
    """
    Workflow state is an insert only hold of updates regarding the
    progress of the case's workflow.
    Each item in this model represents an acknowledgement taken on
    any of the workflow's nodes. The item is indexed by the node key and
    can be used to construct the state of the case.
    It is allowed to insert multiple updates to this model, though only the last
    one is considered current.
    """

    case = models.ForeignKey("cases.Case", null=False, blank=False, on_delete=models.PROTECT)
    key = models.CharField(max_length=250, null=False, blank=False, db_index=True)
    value = fields.JSONField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)

    objects = CaseWorkflowStateManager()

    class Meta:
        index_together = [["case", "key"]]

    def __str__(self):
        return f"{self.key}={self.value}"
