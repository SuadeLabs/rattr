def my_lib_function(thing) -> bool:
    if thing.is_a_good_thing:
        return True
    raise Exception(f"oh no! there was a {thing.type} error")
