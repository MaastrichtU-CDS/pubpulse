from pubpulse.groups import role_group, role_groups, role_title

PEOPLE = [
    {"slug": "andre-dekker", "name": "Andre Dekker", "role": "Professor"},
    {"slug": "joshi-hogenboom", "name": "Joshi Hogenboom", "role": "PhD student"},
    {"slug": "leonard-wee", "name": "Leonard Wee", "role": "Assistant Professor"},
]


def test_roles_are_normalised_and_grouped():
    assert role_title("Former PhD Student") == "PhD student" == role_title("Phd student")
    assert role_title("Management Assistent") == "Management assistant"
    assert role_title("Postdoc – Artificial Intelligence & Implementation Science in Radiotherapy (OPERAI") == "Postdoc"
    assert role_title("Visiting researcher from Magna Græcia University") == "Visiting researcher"
    assert role_title("Student- assistant") == "Student assistant" and role_title(None) == ""
    assert role_group("Former Assistant Professor") == "Senior staff" == role_group("Professor")
    assert role_group("Researcher") == "Senior staff" == role_group("Postdoc – AI") == role_group("Visiting postdoctoral researcher")
    assert role_group("PhD Student") == "Non-senior staff" == role_group("Senior Software Engineer") == role_group("Intern")
    assert role_group("") is None


def test_former_staff_form_their_own_group():
    people = PEOPLE + [{"slug": "ex", "name": "Ex Postdoc", "role": "Former Postdoc", "active": False},
                       {"slug": "ex2", "name": "Ex Intern", "role": None, "active": False}]
    out = role_groups(people)
    assert [(g["name"], g["members"]) for g in out["groups"]] == [
        ("Senior staff", ["andre-dekker", "leonard-wee"]), ("Non-senior staff", ["joshi-hogenboom"]), ("Former staff", ["ex", "ex2"])]
    assert out["seniors"] == ["andre-dekker", "leonard-wee", "ex"]
