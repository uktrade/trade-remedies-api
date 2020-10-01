from core.services.base import TradeRemediesApiView, ResponseSuccess
from security.models import CaseRole, get_role
from organisations.models import get_organisation


class CaseRolesAPI(TradeRemediesApiView):
    """
    Return all case roles

    `GET /roles/`
    Return all roles
    """

    def get(self, request, role_id=None, *args, **kwargs):
        if role_id:
            _role = get_role(role_id)
            return ResponseSuccess({"result": _role.to_dict()})
        exclude_list = request.query_params.getlist("exclude") or ["preparing"]
        roles = CaseRole.objects.all()
        if exclude_list:
            roles = roles.exclude(key__in=exclude_list)
        roles = roles.order_by("order")
        return ResponseSuccess({"results": [role.to_dict() for role in roles]})


class RepresentingAPI(TradeRemediesApiView):
    """
    Check if a user represents an organisation or return all represented organisations
    """

    def get(self, request, organisation_id=None, *args, **kwargs):
        return ResponseSuccess({"results": [org.to_dict() for org in request.user.representing]})

    def post(self, request, organisation_id=None, *args, **kwargs):
        return ResponseSuccess(
            {"result": request.user.is_representing(get_organisation(organisation_id))}
        )
