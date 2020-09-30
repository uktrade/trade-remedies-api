from django.db import models
from core.decorators import method_cache


class ArchiveReason(models.Model):
    """
    Determines the reason a case was archived. Cases which have an archive reason attached
    are deemed terminated/closed and are archived.
    """

    name = models.CharField(max_length=250, null=False, blank=False)
    key = models.CharField(max_length=250, null=True, blank=True)

    def __str__(self):
        return self.name

    @method_cache
    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "key": self.key,
        }
