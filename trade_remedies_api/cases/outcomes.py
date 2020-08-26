import datetime
import logging
from dateutil.parser import parse
from django.utils import timezone
from audit.models import AUDIT_TYPE_EVENT
from audit.utils import audit_log
from cases.models import CaseWorkflowState
from workflow.outcomes import BaseOutcome, register_outcome
from cases.constants import SUBMISSION_TYPE_HEARING_REQUEST


logger = logging.getLogger(__name__)


class CaseAction(BaseOutcome):
    """
    A specialised Outcome dealing with Cases.
    Allows passing the case model through to the action and making it available
    via the case property
    """

    @property
    def case(self):
        return self.kwargs.get("case")


class ModifyExitPath(CaseAction):
    """
    Depending on the evaluated rule value, modify the exit path of the case
    by either removing the reject or the close tasks in the Close Case
    group of actions.
    """

    key = "MODIFY_EXIT_PATH"
    description = "Modify the Close Case paths depending on decision to initiate outcome"
    valid_outcomes = ["INITIATION", "NO_INITIATION", "APPEAL", "NO_APPEAL"]

    def execute(self):
        rule_outcome = self.evaluate_rules()
        if rule_outcome in self.valid_outcomes:
            logger.debug("Modifying exit path: %s", rule_outcome)
            workflow = self.case.workflow
            workflow.refresh_from_db()
            workflow_tree = workflow.as_workflow()
            if rule_outcome == "NO_INITIATION":
                workflow_tree.key_index["CLOSE_APPEAL"]["active"] = False
                workflow_tree.key_index["CLOSE_CASE"]["active"] = False
                workflow_tree.key_index["CLOSE_REJECT"]["active"] = True
            elif rule_outcome == "INITIATION":
                workflow_tree.key_index["CLOSE_APPEAL"]["active"] = True
                workflow_tree.key_index["CLOSE_CASE"]["active"] = True
                workflow_tree.key_index["CLOSE_REJECT"]["active"] = False
            elif rule_outcome == "NO_APPEAL":
                workflow_tree.key_index["CLOSE_APPEAL"]["active"] = False
            elif rule_outcome == "APPEAL":
                workflow_tree.key_index["CLOSE_REJECT"]["active"] = False
                workflow_tree.key_index["CLOSE_CASE"]["active"] = False
            workflow.workflow = workflow_tree
            workflow.save()


class NextAction(CaseAction):
    """
    Sets the case workflow state key of CURRENT_ACTION to the next action in line,
    and CURRENT_ACTION_DUE_DATE to the due date if a timegate is available for it.
    """

    key = "NEXT_ACTION"
    description = "Transition to the next action"

    def execute(self):
        from cases.models import CaseWorkflowState, TimeGateStatus

        next_action = self.evaluate_rules()
        if next_action:
            # if the next action is a dict, extract they key and any other meta data within in
            if isinstance(next_action, dict):
                reason = next_action.get("reason")
                is_next_notice = next_action.get("next_notice")
                reset_next_notice_due = next_action.get("reset") is True
                next_action = next_action["key"]
            else:
                # otherwise, default all extra options
                reset_next_notice_due = None
                reason = None
                is_next_notice = None
            next_action_state, _ = CaseWorkflowState.objects.set_next_action(
                self.case, next_action, requested_by=self.kwargs.get("requested_by")
            )
            next_action_obj = self.workflow.key_index.get(next_action)
            time_gate = next_action_obj.get("time_gate") if next_action_obj else None
            # evaluate the next due date based on this action's time gate
            if time_gate:
                due_date = timezone.now() + datetime.timedelta(days=int(time_gate))
                if next_action_state:
                    next_action_state.due_date = due_date
                    next_action_state.save()
                # Set due date in action.
                state, created = CaseWorkflowState.objects.set_value(
                    case=self.case,
                    key=next_action,
                    value=reason,
                    requested_by=self.kwargs.get("requested_by"),
                )
                state.due_date = due_date
                state.save()
                if self.has_timegate_actions(next_action_obj):
                    TimeGateStatus.objects.get_or_create(workflow_state=state)
                if is_next_notice:
                    CaseWorkflowState.objects.set_next_notice(
                        case=self.case,
                        value=next_action,
                        due_date=due_date,
                        requested_by=self.kwargs.get("requested_by"),
                        reset_due_date=reset_next_notice_due,
                    )

    def has_timegate_actions(self, action):
        return action.get("response_type", {}).get("key") == "TIMER" and action.get("outcome_spec")


class NoNextAction(CaseAction):
    """
    Blanks the next action value, until the next trigger.
    """

    key = "NO_NEXT_ACTION"
    description = "Blank out next action"

    def execute(self):
        from cases.models import CaseWorkflowState

        rule_outcome = self.evaluate_rules()
        if rule_outcome and rule_outcome.upper() == "TRUE":
            state, created = CaseWorkflowState.objects.set_next_action(
                self.case, "", requested_by=self.kwargs.get("requested_by")
            )


class CaseStageChange(CaseAction):
    key = "STAGE_CHANGE"
    description = "Change the stage of the case"

    def execute(self):
        next_stage = self.evaluate_rules()
        if next_stage:
            self.case.set_user_context(self.kwargs.get("requested_by"))
            stage = self.case.set_stage_by_key(next_stage)
            if stage:
                stage_name = stage.name if stage else "N/A"
                # Add to audit
                audit_log(
                    audit_type=AUDIT_TYPE_EVENT,
                    model=self.case,
                    case=self.case,
                    milestone=True,
                    data={"message": stage_name},
                )


class CaseArchive(CaseAction):
    key = "ARCHIVE"
    description = "Archive the case"

    def execute(self):
        from cases.models import ArchiveReason
        from cases.models import CaseWorkflowState

        next_stage = self.evaluate_rules()
        if next_stage:
            archive_reason = ArchiveReason.objects.get(key=next_stage.upper())
            self.case.set_user_context(self.kwargs.get("requested_by"))
            self.case.archive_reason = archive_reason
            self.case.archived_at = timezone.now()
            self.case.set_stage_by_key("CASE_CLOSED")
            self.case.save()
            CaseWorkflowState.objects.set_next_action(
                self.case, "", requested_by=self.kwargs.get("requested_by")
            )
            audit_log(
                audit_type=AUDIT_TYPE_EVENT,
                model=self.case,
                case=self.case,
                milestone=True,
                data={"message": "Case archived"},
            )


class PublishInitiation(CaseAction):
    key = "PUBLISH_INITIATION"

    def execute(self):
        value = self.evaluate_rules()
        if value == "PUBLISHED":
            self.case.set_user_context(self.kwargs.get("requested_by"))
            self.case.initiated_at = timezone.now()
            self.case.save()
            self.case.set_stage_by_key("CASE_INITIATED")
            audit_log(
                audit_type=AUDIT_TYPE_EVENT,
                model=self.case,
                case=self.case,
                milestone=True,
                data={"message": "Case initiated"},
            )


class TimeGate(CaseAction):
    """
    Sets a time gate against a particular state node.
    The outcome evaluated value is a dict with the following sets of keys:
        To set a time gate explicitly:
            key: the key to set due date on
            reason: the value to set
            unit: minutes/hours/days
            value: numeric number of units

        or

        To reset a timegate to nothing:
            key: the key to set due date on
            reason: the value to set
            reset: True

    If the `key` exists in `timegates.TIMEGATE_ACTION_MAP` then any associated
    timegate actions will be processed when the due date passes.
    """

    key = "TIME_GATE"
    description = "Set or reset a time gate"

    def execute(self):
        from cases.models import CaseWorkflowState, TimeGateStatus

        self.case.set_user_context(self.kwargs.get("requested_by"))
        time_gate_value = self.evaluate_rules()
        if time_gate_value and isinstance(time_gate_value, dict):
            state, created = CaseWorkflowState.objects.set_value(
                self.case,
                time_gate_value["key"],
                time_gate_value.get("reason"),
                requested_by=self.kwargs.get("requested_by"),
            )

            if time_gate_value.get("reset"):
                state.due_date = None
            elif "unit" in time_gate_value and "value" in time_gate_value:
                time_delta_kwargs = {time_gate_value["unit"]: time_gate_value["value"]}
                state.due_date = timezone.now() + datetime.timedelta(**time_delta_kwargs)

            state.save()

            if time_gate_value.get("next_notice"):
                CaseWorkflowState.objects.set_next_notice(
                    self.case,
                    time_gate_value["key"],
                    state.due_date,
                    requested_by=self.kwargs.get("requested_by"),
                )

            if time_gate_value.get("reset"):
                TimeGateStatus.objects.filter(workflow_state=state, ack_at__isnull=True).delete()
            elif self.has_timegate_actions(time_gate_value):
                TimeGateStatus.objects.get_or_create(workflow_state=state)

            self.post_execute(state)

    def has_timegate_actions(self, rules):
        target_key = rules["key"]
        workflow = self.case.workflow
        workflow_tree = workflow.as_workflow()
        target = workflow_tree.key_index.get(target_key)
        return (
            target
            and target.get("outcome_spec")
            and target.get("response_type", {}).get("key") == "TIMER"
        )

    def post_execute(self, state):
        """ To be implemented in sub-classes if required."""
        pass


class HearingRequestClosesTimeGate(TimeGate):
    key = "HEARING_REQUEST_CLOSES_TIME_GATE"
    description = "Timegate specifically for when hearing request windows close"

    def post_execute(self, state):
        from cases.models import Submission

        Submission.objects.filter(
            case=state.case, type=SUBMISSION_TYPE_HEARING_REQUEST, status__default=True
        ).update(due_at=state.due_date)


class AssignCaseNumber(CaseAction):
    key = "CASE_NUMBER"
    description = "Assign the case number"

    def execute(self):
        self.case.set_user_context(self.kwargs.get("requested_by"))
        _value = self.evaluate_rules()
        if _value == "ASSIGN":
            case_number = self.case.get_next_initiated_sequence()
            self.case.initiated_sequence = case_number
            self.case.save()


class ChangeTaskAttributes(CaseAction):
    key = "CHANGE_TASK_ATTRIBUTES"
    description = "Change attributes on a task(s) eg active, required"

    def execute(self):
        self.case.set_user_context(self.kwargs.get("requested_by"))
        _value = self.evaluate_rules()
        if _value:
            workflow = self.case.workflow
            workflow.refresh_from_db()
            workflow_tree = workflow.as_workflow()
            for key, attrs in _value.items():
                for attr, val in attrs.items():
                    workflow_tree.key_index[key][attr] = val
            workflow.workflow = workflow_tree
            workflow.save()


class SetCaseMilestone(CaseAction):
    """
    Set a milestone date.
    The rule will return either the milestone key (or list of),
    in which case the milestone date for that key is set to now,
    or, a dict specifying the milestone key and which value_key
    from workflow state to grab the date from.
    """

    key = "SET_MILESTONE"
    description = "Set a milestone date on a case"

    def execute(self):
        milestone_types = self.evaluate_rules()
        if milestone_types:
            if not isinstance(milestone_types, list):
                milestone_types = [milestone_types]
            now = timezone.now()
            for milestone_type in milestone_types:
                milestone_date = now
                if isinstance(milestone_type, dict):
                    try:
                        workflow = self.case.workflow.as_workflow()
                        value_key = milestone_type.get("value_key")
                        _value = parse(
                            CaseWorkflowState.objects.value_index(self.case, keys=[value_key])
                        )
                        milestone_date = _value.get(value_key)[0]
                    except Exception as exc:
                        milestone_date = None
                    finally:
                        milestone_type = milestone_type["key"]
                if milestone_type:
                    self.case.set_milestone(
                        milestone_type=milestone_type,
                        date=milestone_date,
                        set_by=self.kwargs.get("requested_by"),
                    )


def register_outcomes():
    register_outcome(NextAction)
    register_outcome(CaseStageChange)
    register_outcome(CaseArchive)
    register_outcome(PublishInitiation)
    register_outcome(TimeGate)
    register_outcome(NoNextAction)
    register_outcome(ModifyExitPath)
    register_outcome(HearingRequestClosesTimeGate)
    register_outcome(AssignCaseNumber)
    register_outcome(ChangeTaskAttributes)
    register_outcome(SetCaseMilestone)
