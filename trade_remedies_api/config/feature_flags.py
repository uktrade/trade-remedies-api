def part_of_group_condition(request, **kwargs):
    return (
        kwargs["user_object"].is_authenticated
        and kwargs["user_object"].groups.filter(name=kwargs["group_name"]).exists()
    )
