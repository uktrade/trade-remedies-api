import pytest

import unittest

from model_bakery import baker


class OrganisationTest(unittest.TestCase):
    @pytest.mark.django_db
    def test_potential_duplicate_organisations(self):

        target_organisation = baker.make(
            "organisations.Organisation",
            name="Fake Company LTD",
            address="101 London, LD123",
            post_code="LD123",
            vat_number="GB123456789",
            eori_number="GB205672212000",
            duns_number="012345678",
            organisation_website="www.fakewebsite.com",
        )

        baker.make("organisations.Organisation", name=target_organisation.name)
        baker.make(
            "organisations.Organisation",
            address=target_organisation.address,
            post_code=target_organisation.post_code,
        )
        baker.make("organisations.Organisation", vat_number=target_organisation.vat_number)
        baker.make(
            "organisations.Organisation",
            name="Fake Company LTD 2",
            address="101 London, LD123E",
            post_code="LD123E",
            vat_number="GB123456788",
            eori_number="GB205672212001",
            duns_number="012345676",
            organisation_website="www.fakewebsite.co",
        )

        assert len(target_organisation.find_potential_duplicate_orgs()) == 3
