import uuid
from django.db import models
from core.decorators import method_cache


class CaseStage(models.Model):
    """
    A global stage of a case. Each case type can have their own set of stage
    indicators. Certain stages can be designated as "locking", which will cause the
    underlying case to go into a locked state.
    A stage entry has a unique code (uppercase) used for easy identification.
    Flow restricted  stages mean that after they are set, only stages with a higher
    order can be set on the case. In other words, that is the lowest stage order
    that the case can be set to.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=100, null=False, blank=False, unique=True)
    name = models.CharField(max_length=100, null=False, blank=False)
    public_name = models.CharField(max_length=150, null=True, blank=True)
    type = models.ForeignKey("cases.CaseType", null=True, blank=True, on_delete=models.PROTECT)
    order = models.SmallIntegerField(default=0)
    locking = models.BooleanField(default=False)
    flow_restrict = models.BooleanField(default=False)

    def __str__(self):
        locking_indicator = "*" if self.locking else ""
        return f"{self.name}{locking_indicator}"

    @method_cache
    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "public_name": self.public_name,
            "order": self.order,
            "locking": self.locking,
            "flow_restrict": self.flow_restrict,
            "type": self.type.to_dict() if self.type else None,
        }

    @method_cache
    def to_embedded_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "public_name": self.public_name,
            "key": self.key,
        }
