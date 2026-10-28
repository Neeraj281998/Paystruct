"""Word lists shared by countries. They mirror the street and building words in data/labelling-guide.md section 3."""

# Full street word -> abbreviations a corruption may write instead.
STREET_ABBREVIATIONS = {
    "Street": ("St", "St."),
    "Road": ("Rd", "Rd."),
    "Avenue": ("Ave", "Ave."),
    "Drive": ("Dr", "Dr."),
    "Lane": ("Ln",),
    "Terrace": ("Ter",),
    "Close": ("Cl",),
    "Square": ("Sq",),
    "Gardens": ("Gdns",),
    "Crescent": ("Cres",),
}
ROOM_ABBREVIATIONS = {"Apartment": ("Apt", "Apt.")}

# Every street word the guide lists, written out in full and abbreviated.
STREET_WORDS = frozenset(
    {"Street", "Road", "Lane", "Avenue", "Drive", "Terrace", "Close", "Way", "Place", "Square", "Quay", "Crescent",
     "Gardens", "Grove", "Row", "Hill", "Walk"}
    | {a.rstrip(".") for abbrs in STREET_ABBREVIATIONS.values() for a in abbrs}
)

# Single-word building words; "Business Park" and "Industrial Estate" are multi-word and listed separately.
BUILDING_WORDS = frozenset({"House", "Court", "Lodge", "Tower", "Building", "Centre", "Plaza", "Mansions", "Cottage", "Block"})
BUILDING_PHRASES = ("Business Park", "Industrial Estate")

ROOM_KEYWORDS = frozenset({"Flat", "Apartment", "Apt", "Unit", "Suite", "Room"})
