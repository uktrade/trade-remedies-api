from django.db import models
from core.base import BaseModel


class ContentManager(models.Manager):
    def content_branch(self, case, root=None):
        """
        Return the content tree branch for a case.
        """
        content = self.filter(case=case, parent=root).order_by("name")
        return content


class Content(BaseModel):
    case = models.ForeignKey("cases.Case", null=False, blank=False, on_delete=models.PROTECT)
    name = models.CharField(max_length=250, null=False, blank=False)
    short_name = models.CharField(max_length=100, null=True, blank=True)
    order = models.SmallIntegerField(default=0)
    content = models.TextField(null=True, blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="parent_content"
    )
    documents = models.ManyToManyField("documents.Document", blank=True)

    objects = ContentManager()

    def __str__(self):
        return self.name

    @property
    def children(self):
        return Content.objects.filter(parent=self).order_by("name")

    def _to_dict(self):
        return {
            "name": self.name,
            "short_name": self.short_name,
            "order": self.order,
            "content": self.content,
            # 'parent': self.parent.to_dict() if self.parent else None,
            # 'children': [child.to_dict() for child in self.children],
            "documents": [doc.to_dict() for doc in self.documents.all()],
        }

    def to_embedded_dict(self):
        # For the navigator view on every page
        return {
            "id": str(self.id),
            "name": self.name,
            "short_name": self.short_name,
            "children": [child.to_embedded_dict() for child in self.children],
        }
