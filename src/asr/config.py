
from dataclasses import dataclass

@dataclass
class ScoringConfig:
    product_weights: dict
    family_weights: dict
    eligibility_gate: int = 60

DEFAULT_SCORING = ScoringConfig(
    product_weights={
        "has_jsonld": 20,            # Server-rendered JSON-LD (in initial HTML)
        "has_jsonld_js": 15,         # JS-generated JSON-LD (requires browser execution)
        "has_product": 20,
        "has_offer": 15,
        # Identifier scoring is tiered: full credit for GTIN (13/14), discounted for Brand+MPN only
        "has_identifiers_gtin": 20,
        "has_identifiers_brand_mpn": 12,
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
