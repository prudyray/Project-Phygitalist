from shop.apps.main.models import State, Postoffice


def run(*args):
    states = State.objects.all()
    
    seen_codes = set()
    duplicates_to_delete = []
    
    for state in states:
        print(state.code)
        if state.code not in seen_codes:
            seen_codes.add(state.code)
        else:
            duplicates_to_delete.append(state)
    
    # Delete the duplicate entries
    if duplicates_to_delete:
        State.objects.filter(pk__in=[state.pk for state in duplicates_to_delete]).delete()
        print(f"Deleting {[state.pk for state in duplicates_to_delete]}")
        print(f"Deleted {len(duplicates_to_delete)} duplicate states.")
    else:
        print("No duplicate states found.")
