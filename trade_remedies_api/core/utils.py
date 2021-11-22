import logging
import hashlib
import phonenumbers
import dpath
import gevent
from django.conf import settings
from django.db import connection
from django.contrib.contenttypes.models import ContentType
from core.constants import STATE_INCOMPLETE


logger = logging.getLogger(__name__)


XLSX_INJECTION_CHECK_CHARS = ["=", "+", "-", "@"]

MAX_INJECTION_CHECK_STR_LENGTH = 10000


def deep_index_items_by(items, key):
    """
    Index a list of dicts by a given key.
    Returns a dict of the items based on the value of `key` in each item.
    """
    index = {}
    for item in items:
        index_key = str((dpath.util.get(item, key) or "")).lower()
        index.setdefault(index_key, [])
        index[index_key].append(item)
    return index


def get(item, key, default=None):
    """
    Safe get to find a value based on a path
    """
    val = default
    try:
        val = dpath.util.get(item, key)
    except KeyError:
        pass
    return val


def key_by(items, key):
    """
    Index a list of dicts by the value of given key.
    Returns a dict of the values. One item per key.
    """
    index = {}
    for item in items:
        _item_key = item[key] if isinstance(item[key], int) else str(item[key]).lower()
        index[_item_key] = item
    return index


def filter_dict(dict_, allowed):
    out = {}
    for key, val in dict_.items():
        if key in allowed:
            out[key] = val
    return out


def rekey(item, key, rekey_as=None):
    """
    reindex a dict by a different key
    if rekey_as is provided, the original key will be inserted back into the dict under the key name
    specified in rekey_as
    """
    rekeyed = {}
    for k in item:
        if rekey_as:
            item[k][rekey_as] = k
        rekeyed[item[k][key]] = item[k]
    return rekeyed


def convert_to_e164(raw_phone, country=None):
    """
    Convert a phone number to E.164 standard format.
    :param raw_phone: Any phone number
    :return: E.164 phone number
    """
    if not raw_phone:
        return

    if raw_phone[0] == "+":
        # Phone number may already be in E.164 format.
        parse_type = None
    else:
        # If no country code information present, assume it's a British number
        parse_type = country.upper() if country else "GB"
    try:
        phone_representation = phonenumbers.parse(raw_phone, parse_type)
        e164_phone = phonenumbers.format_number(
            phone_representation, phonenumbers.PhoneNumberFormat.E164
        )
    except Exception:
        logger.debug(f"Invalid phone number: {raw_phone} / {country}")
        raise
    return e164_phone


def init_application_state():
    return {
        "status": {
            "organisation": STATE_INCOMPLETE,
            "product": STATE_INCOMPLETE,
            "source": STATE_INCOMPLETE,
            "documents": STATE_INCOMPLETE,
            "review": STATE_INCOMPLETE,
        },
        "organisation": None,
        "case": None,
        "submission": None,
        "product": None,
        "source": None,
        "documents": [],
    }


def get_content_type(path):
    app_label, model = path.split(".")
    return ContentType.objects.get(app_label=app_label, model=model)


def update_object_from_request(target, source, field_list):
    """
    Overwrite only the fields cited in field_list in target dict from source dict
    Useful for update handlers to update model fields
    """
    for field in field_list:
        setattr(target, field, source.get(field, getattr(target, field)))


def pluck(dict, attr_list):
    """
    Return a dict containing the attributes listed, plucked from the given dict.
    """
    out = {}
    for key in attr_list:
        if key in dict:
            out[key] = dict[key]
    return out


def is_valid_email(email):
    """
    Light validation on email address: require @ and at least one dot.
    """
    return "@" in email and "." in email


def extract_error_from_api_exception(exc):
    """
    Attempts to extract a detailed response from an API exception.
    If this fails, returns the exception as string.
    """
    try:
        status = exc.response.status_code
        response = exc.response.json()
        response["messages"] = []
        try:
            errors = response.get("errors", [])
            for error in errors:
                response["messages"].append(error.get("message"))
        except Exception:
            pass
        return response, status
    except Exception:
        return str(exc), None


def public_login_url():
    return f"{settings.PUBLIC_ROOT_URL}/"


def sql_get_list(sql):
    """
    Pass in some sql and get back a list of the first item in each row.
    simple as that.
    """
    crsr = connection.cursor()
    crsr.execute(sql)
    return [i[0] for i in crsr.fetchall()]


def gt(val_a, val_b):
    """A greater operator wrapped in a function"""
    return val_a > val_b


def lt(val_a, val_b):
    """A less than operator wrapped in a function"""
    return val_a < val_b


def remove_xlsx_injection_attack_chars(value):
    if len(value) > MAX_INJECTION_CHECK_STR_LENGTH:
        return ""

    if len(value) > 0 and str(value)[0] in XLSX_INJECTION_CHECK_CHARS:
        return remove_xlsx_injection_attack_chars(value[1 : len(value)])

    return value
