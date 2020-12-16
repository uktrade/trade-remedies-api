import json
from core.services.base import TradeRemediesApiView, ResponseSuccess
from tasks.models import Task
from rest_framework import status
from core.services.exceptions import NotFoundApiExceptions
from django.db import transaction
from django.db.models import Q
from core.utils import get_content_type
from cases.models import get_case


class TaskAPIView(TradeRemediesApiView):
    """
    Create or retrieve tasks
    """

    def get(self, request, task_id=None, case_id=None, *args, **kwargs):  # noqa: C901
        """
        Get one or more tasks based on a set of query parameters and fields.
        """
        query_str = request.GET.get("query")
        query_dict = json.loads(query_str) if query_str else {}
        fields_str = request.GET.get("fields")
        fields = json.loads(fields_str) if fields_str else {}
        if task_id:
            try:
                task = Task.objects.get(id=task_id)
                return ResponseSuccess({"result": task.to_dict()})
            except Task.DoesNotExist:
                raise NotFoundApiExceptions("Task not found id")
        else:
            query = Q(deleted_at__isnull=True)
            orquery = None
            exclude_exp = Q(id__isnull=True)
            for query_item in query_dict:
                field = query_item.get("field")
                field_val = query_item.get("value")

                if field_val:
                    queue = None
                    if field_val == "null":
                        queue = Q(**{field + "__isnull": True})
                    else:
                        queue = Q(**{field: field_val})

                    if query_item.get("combine") == "not":
                        exclude_exp.add(queue, Q.OR)

                    elif query_item.get("combine") == "or":
                        if orquery:
                            orquery.add(queue, Q.OR)
                        else:
                            orquery = queue
                    else:
                        query.add(queue, Q.AND)

            tasks = Task.objects.filter(query).exclude(exclude_exp)
            if orquery:
                tasks = Task.objects.filter(query).exclude(exclude_exp).filter(orquery)
            else:
                tasks = Task.objects.filter(query).exclude(exclude_exp)
        return ResponseSuccess({"results": [_task.to_dict(fields=fields) for _task in tasks]})

    @transaction.atomic
    def post(
        self, request, task_id=None, case_id=None, model_id=None, content_type=None, *args, **kwargs
    ):
        """
        create / update a Task
        """
        task_id = task_id or request.data.get("id")
        case_id = case_id or request.data.get("case_id")
        if task_id:
            try:
                task = Task.objects.get(id=task_id)
            except Task.DoesNotExist:
                raise NotFoundApiExceptions("Invalid task id")
        else:
            # we must be creating a task, so get the key params
            case = get_case(case_id)
            model_id = model_id or request.data.get("model_id")
            content_type = content_type or request.data.get("content_type")
            _content_type = content_type and get_content_type(content_type)
            task = Task(
                case=case,
                created_by=request.user,
                model_id=model_id,
                content_type=_content_type,
                user_context=[request.user],
            )
        data = request.data.get("data")
        if data:
            task.data = task.data or {}
            task.data.update(json.loads(data))

        task.load_attributes(
            request.data,
            [
                "name",
                "description",
                "model_key",
                "due_date",
                "assignee",
                "assignee_id",
                "case_id",
                "priority",
                "status",
            ],
        )
        task.save()
        return ResponseSuccess(
            {"result": task.to_dict(fields=json.dumps({"Task": {"id": 0}}))},
            http_status=status.HTTP_201_CREATED,
        )

    @transaction.atomic
    def delete(self, request, task_id=None, *args, **kwargs):
        task = Task.objects.get(id=task_id)
        task.delete()
        return ResponseSuccess({"result": {"id": task_id}}, http_status=status.HTTP_201_CREATED)
