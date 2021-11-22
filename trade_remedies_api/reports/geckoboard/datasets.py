DATASETS = {
    "users_by_date": {
        "query": "users_by_date",
        "mode": "replace",
        "fields": {
            "date": {"type": "date", "name": "Date"},
            "total": {"type": "number", "name": "Total"},
        },
        "unique_by": ["date"],
    },
    "total_public_users": {
        "query": "total_public_users",
        "mode": "replace",
        "fields": {
            "total": {
                "type": "number",
                "name": "Total Users",
            },
            "type": {"type": "string", "name": "Type"},
        },
    },
    "roi_by_date": {
        "query": "roi_by_date",
        "mode": "replace",
        "fields": {
            "date": {"type": "date", "name": "Date"},
            "status": {"type": "string", "name": "Status"},
            "total": {
                "type": "number",
                "name": "Total",
            },
        },
        "unique_by": ["date", "status"],
    },
}


def get_dataset(key, env=None):
    """
    Return a tuple of a full dataset name, and the dataset definition
    """
    if key in DATASETS:
        return f"trade-remedies.{env}.{key}", DATASETS[key]
    return None, None
