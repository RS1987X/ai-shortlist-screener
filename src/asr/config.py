
from dataclasses import dataclass

@dataclass
class ScoringConfig:
    product_weights: dict
    family_weights: dict
    eligibility_gate: int = 60

DEFAULT_SCORING = ScoringConfig(
    product_weights={
        "has_jsonld": 20,
        "has_product": 20,
        "has_offer": 15,
        "has_identifiers": 20,
        "has_policies": 10,
        "has_specs_with_units": 15,
    },
    family_weights={
        "has_productgroup": 30,
        "has_hasvariant": 30,
        "links_to_children": 20,
        "policies": 10,
        "spec_ranges": 10,
    },
)
