def process_data(data):
    """Process user data through the pipeline.

    Args:
        data: List of user records (dicts)

    Returns:
        List of processed records
    """
    results = []
    for record in data:
        # BUG: No null check before accessing keys
        processed = {
            "name": record["name"].upper(),
            "age": record["age"] * 2,
            "email": record["email"].lower(),
        }
        results.append(processed)
    return results


def filter_active_users(users):
    """Filter to only active users.

    Args:
        users: List of user records

    Returns:
        List of active users
    """
    # BUG: No null check
    return [u for u in users if u["active"]]
