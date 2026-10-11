from dataclasses import dataclass


@dataclass(frozen=True)
class Template:
    name: str
    description: str
    ids: tuple
    notes: str


TEMPLATES = {
    "tip_splitter": Template(
        "tip_splitter",
        "Split a bill plus tip between several people.",
        ("#bill", "#people", "#tip", "#calc", "#result", "#error"),
        "#tip is a percentage. Clicking #calc shows the per-person amount with two decimals in #result. "
        "Invalid input (anything for which a per-person amount cannot be meaningfully computed) must show a message in #error and leave #result empty or hidden. "
        "Valid input must show the per-person amount in #result with two decimals and hide #error.",
    ),
    "habit_tracker": Template(
        "habit_tracker",
        "Track daily habits and a streak.",
        ("#habit-input", "#add", "#list", ".habit", ".done-btn", "#streak"),
        "Clicking #add appends a .habit (with a .done-btn inside) to #list. Marking a habit done raises the "
        "number shown in #streak. Empty input must not add a habit. Keep everything in memory.",
    ),
    "flashcards": Template(
        "flashcards",
        "Create flashcards and flip through them.",
        ("#front", "#back", "#add-card", "#next", "#card-view", "#flip"),
        "#add-card stores the card from #front and #back. #card-view shows the current card's front. "
        "#next moves to the next card. #flip shows the current card's back text in #card-view.",
    ),
}


def get(name: str) -> Template:
    if name not in TEMPLATES:
        raise KeyError(f"unknown template {name!r}; supported: {sorted(TEMPLATES)}")
    return TEMPLATES[name]
