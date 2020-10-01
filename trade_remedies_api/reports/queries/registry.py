REPORT_REGISTRY = {}


def register_report(report_func):
    REPORT_REGISTRY[report_func.__name__] = report_func
    return REPORT_REGISTRY
