"""France: number before the street, the street word first, five-digit postcode before the town (guide section 13)."""
from __future__ import annotations

import random

from addrgen.countries.base import CountryModule, _pick, register
from addrgen.model import Part, TownBlock

# (town, postcodes, arrondissements). A town with arrondissements has postcodes 'prefix' + number, e.g. Paris 8e is 75008.
PLAIN_TOWNS = (
    ("Toulouse", ("31000", "31100", "31200", "31300", "31400", "31500")), ("Nice", ("06000", "06100", "06200", "06300")),
    ("Nantes", ("44000", "44100", "44200", "44300")), ("Strasbourg", ("67000", "67100", "67200")),
    ("Montpellier", ("34000", "34070", "34080", "34090")), ("Bordeaux", ("33000", "33100", "33200", "33300", "33800")),
    ("Lille", ("59000", "59160", "59260", "59777")), ("Rennes", ("35000", "35200", "35700")), ("Reims", ("51100",)),
    ("Dijon", ("21000",)), ("Grenoble", ("38000", "38100")), ("Angers", ("49000", "49100")), ("Nîmes", ("30000", "30900")),
    ("Tours", ("37000", "37100", "37200")), ("Clermont-Ferrand", ("63000", "63100")), ("Brest", ("29200",)),
    ("Metz", ("57000",)), ("Orléans", ("45000", "45100")), ("Rouen", ("76000", "76100")), ("Besançon", ("25000",)),
)
ARRONDISSEMENT_TOWNS = (("Paris", "750", 20), ("Lyon", "690", 9), ("Marseille", "130", 16))

_STREET_TYPES = (("Rue", 0.55), ("Avenue", 0.12), ("Boulevard", 0.08), ("Place", 0.06), ("Chemin", 0.06), ("Impasse", 0.03),
                 ("Allée", 0.04), ("Quai", 0.02), ("Route", 0.02), ("Cours", 0.01), ("Passage", 0.005), ("Square", 0.005))
_STREET_NAMES = ("de la Paix", "des Tilleuls", "du Marché", "de la Gare", "de la République", "des Lilas", "du Château",
                 "de l'Église", "des Écoles", "du Moulin", "de Verdun", "des Fleurs", "Victor Hugo", "Jean Jaurès",
                 "Pasteur", "Gambetta", "Voltaire", "Anatole France", "Émile Zola", "Pierre Curie")
_BUILDING_NAMES = ("Les Tilleuls", "Le Parc", "Les Jardins", "Beau Séjour", "Les Lilas", "Le Clos", "Horizon", "Les Platanes",
                   "Le Central")
_BUILDING_WORDS = (("Résidence", 0.5), ("Bâtiment", 0.2), ("Immeuble", 0.15), ("Tour", 0.1), ("Villa", 0.05))


@register
class France(CountryModule):
    code = "FR"
    locale = "fr_FR"
    country_names = ("France",)
    street_bases = _STREET_NAMES
    street_suffixes = _STREET_TYPES  # the street word, which comes first
    building_bases = _BUILDING_NAMES
    building_words = _BUILDING_WORDS
    template_weights = {
        "number_street": 7, "street_only": 0.3, "house_name_street": 0.5, "building_number_street": 1.5,
        "flat_number_street": 2, "flat_in_building": 2, "floor_number_street": 1, "po_box": 0.7,
    }

    street_type_first = True
    postcode_has_space = False
    can_drop_postcode_space = False
    street_abbreviations = {"Avenue": ("Av.",), "Boulevard": ("Bd",), "Place": ("Pl.",), "Chemin": ("Ch.",),
                            "Impasse": ("Imp.",), "Allée": ("All.",)}
    room_abbreviations = {"Appartement": ("Appt",)}
    # The full words and the abbreviations a corruption may write instead.
    street_words = frozenset(w.casefold() for w, _ in _STREET_TYPES) | {"av", "bd", "pl", "ch", "imp", "all"}
    building_word_set = frozenset(w.casefold() for w, _ in _BUILDING_WORDS)
    protected_words = street_words | building_word_set
    room_pattern = r"(Appartement|Appt|Bureau) \d+"
    floor_pattern = r"(Rez-de-chaussée|1er étage|\d+(e|ème) étage)"
    po_box_pattern = r"BP \d+"
    building_number_pattern = r"\d+( (bis|ter))?"
    postcode_pattern = r"\d{5}"

    def street_name(self, rng, fake):
        street_type = _pick(rng, _STREET_TYPES)
        name = self.surname(rng, fake) if rng.random() < 0.2 else rng.choice(_STREET_NAMES)
        return f"{street_type} {name}"

    def building_name(self, rng, fake):
        word = _pick(rng, _BUILDING_WORDS)
        return f"Bâtiment {rng.choice('ABCDEF')}" if word == "Bâtiment" else f"{word} {rng.choice(_BUILDING_NAMES)}"

    def building_number(self, rng):
        n = rng.randint(1, 199)
        return f"{n} {rng.choice(('bis', 'ter'))}" if rng.random() < 0.05 else str(n)

    def room(self, rng):
        return f"Appartement {rng.randint(1, 60)}" if rng.random() < 0.7 else f"Bureau {rng.randint(1, 60)}"

    def floor(self, rng):
        roll = rng.random()
        if roll < 0.15:
            return "Rez-de-chaussée"
        n = rng.randint(1, 8)
        if n == 1 and roll < 0.5:
            return "1er étage"
        return f"{n}e étage" if roll < 0.7 else f"{n}ème étage"

    def po_box(self, rng):
        return f"BP {rng.randint(1, 99999)}"

    def town_block(self, rng: random.Random, difficulty: str, want_locality: bool) -> TownBlock:
        tags: set[str] = set()
        style = "cedex" if difficulty == "hard" and rng.random() < 0.18 else \
                "arrondissement" if difficulty == "hard" and rng.random() < 0.25 else "plain"
        if style == "arrondissement":
            town, prefix, count = rng.choice(ARRONDISSEMENT_TOWNS)
            n = rng.randint(1, count)
            postcode, written = f"{prefix}{n:02d}", f"{town} {'1er' if n == 1 else f'{n}e'}"
            tags.add("postal_district")
        else:
            if rng.random() < 0.25:  # a big city written plain; its arrondissement is only in the postcode
                town, prefix, count = rng.choice(ARRONDISSEMENT_TOWNS)
                postcode, written = f"{prefix}{rng.randint(1, count):02d}", town
            else:
                town, codes = rng.choice(PLAIN_TOWNS)
                postcode, written = rng.choice(codes), town
            if style == "cedex":
                written = f"{written} Cedex {rng.randint(1, 20):02d}"
                tags.add("cedex")
        return TownBlock([[Part("PstCd", postcode), Part("TwnNm", written)]], tags)

    def split_postcode(self, postcode):
        return None  # five digits, no natural split

    def known_towns(self):
        return frozenset(t.casefold() for t, _ in PLAIN_TOWNS) | frozenset(t.casefold() for t, _, _ in ARRONDISSEMENT_TOWNS)

    def is_known_town(self, text: str) -> bool:
        import re
        base = re.sub(r"(?i)( cedex \d+)?( (\d+)(e|er|ème))?$", "", text)  # drop a Cedex or arrondissement suffix
        return base.casefold() in self.known_towns()
