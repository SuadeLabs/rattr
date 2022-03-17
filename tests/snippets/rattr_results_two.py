@rattr_results(sets={"a.attr"}, gets={"b.attr"})
def fn_a(a, b):
    return "i dont do any of that!"


def fn_b(c):
    print(c.some_attr)
    return fn_a(c, c)
