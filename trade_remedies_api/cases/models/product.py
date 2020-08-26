from django.db import models, transaction
from django.utils import timezone
from django_countries.fields import CountryField
from core.decorators import method_cache
from core.models import SimpleBaseModel, BaseModel


class Sector(models.Model):
    name = models.CharField(max_length=250, null=False, blank=False)
    code = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        return f"{self.code}: {self.name}"

    @method_cache
    def to_dict(self):
        return {"id": self.id, "name": self.name, "code": self.code}


class HSCode(SimpleBaseModel):
    code = models.CharField(max_length=50, null=False, blank=False, unique=True)

    def __str__(self):
        return self.code

    @method_cache
    def to_dict(self):
        return {"id": str(self.id), "code": self.code}


class ProductManager(models.Manager):
    @transaction.atomic
    def set_hs_codes(self, product, hs_codes, reset=False):
        """
        Adds hs_codes to the product instance provided.
        Deletes all existing codes if reset is True
        Returns the hs codes queryset
        """
        if reset:
            product.hs_codes.all().delete()
        for hs_code in hs_codes:
            if hs_code:
                product.add_hs_code(hs_code)
        return product.hs_codes.all()


class Product(BaseModel):
    case = models.ForeignKey("cases.Case", null=True, blank=False, on_delete=models.PROTECT)
    name = models.CharField(max_length=250, null=True, blank=True)
    sector = models.ForeignKey(Sector, null=False, blank=False, on_delete=models.PROTECT)
    hs_codes = models.ManyToManyField(HSCode, blank=True)
    description = models.TextField(null=True, blank=True)

    objects = ProductManager()

    def __str__(self):
        return f"{self.sector} - {self.name}"

    @method_cache
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "sector": self.sector.to_dict(),
            "description": self.description,
            "hs_codes": [code.to_dict() for code in self.hs_codes.all()],
        }

    def add_hs_code(self, code):
        """
        Add an HS code.
        Temporarily validate that the code is between 6 to 10 digits though this might
        change later for more specific and accurate validation.
        """
        if code and len(code) in (6, 8, 10) and str(code).isdigit():
            hscode, created = HSCode.objects.get_or_create(code=code)
            self.hs_codes.add(hscode)
            self.last_modified = timezone.now()
            self.save()
            return hscode
        return None

    def remove_hs_code(self, code):
        """
        Remove HS code.
        """
        if code:
            self.hs_codes.remove(code)
            self.last_modified = timezone.now()
            self.save()
        return self.hs_codes.all()


class ExportSource(BaseModel):
    case = models.ForeignKey("cases.Case", null=True, blank=False, on_delete=models.PROTECT)
    country = CountryField(blank_label="Select Country", null=False, blank=False)

    class Meta:
        unique_together = ["case", "country"]

    def __str__(self):
        return f"{self.case.name}: {self.country.name}"

    def _to_dict(self):
        return {
            "country": self.country.name,
            "country_code": self.country.code,
        }
