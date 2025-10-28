# Category-Weighted LAR Scoring

## Problem

When comparing peers with different category coverage, simple averaging creates unfair comparisons:

- **Specialist** (Kjell: electronics only) vs. **Generalist** (Clas Ohlson: electronics + DIY + appliances + workwear)
- If you have 5 electronics intents and 15 DIY intents, the generalist's score is 75% determined by DIY performance
- A category with 9 competing peers vs. 6 peers creates unequal competitive pressure

## Solution: Category-Weighted Scoring

Instead of averaging all intent scores, we:

1. **Group intents by category** (Electronics, DIY_Tools, Building, Appliances, Workwear, Automotive)
2. **Compute per-category scores** for each peer (E, X, and eventually A)
3. **Average category scores** (not intent scores) to get overall LAR
4. **Only include categories where the peer competes** (defined in `peer_categories.csv`)

### Example

**Kjell (Electronics specialist)**:
- Competes in: Electronics (5 intents)
- Electronics category LAR: 78
- **Overall weighted LAR: 78** (1 category)

**Clas Ohlson (Multi-category generalist)**:
- Competes in: Electronics (5 intents), DIY_Tools (7 intents), Appliances (2 intents), Workwear (2 intents)
- Electronics LAR: 72, DIY_Tools LAR: 68, Appliances LAR: 70, Workwear LAR: 65
- **Overall weighted LAR: (72+68+70+65)/4 = 68.75** (4 categories, equal weight)

**Without weighting**: Clas would score (72×5 + 68×7 + 70×2 + 65×2)/16 = 69.1, but this gives DIY 44% weight just because it has more intents.

## Configuration Files

### `data/intent_categories.csv`
Maps each intent to a category:
```csv
intent_id,category
INT01,Electronics
INT02,Electronics
INT06,Appliances
INT08,DIY_Tools
...
```

### `data/peer_categories.csv`
Defines which categories each peer competes in (1 = competes, 0 = doesn't):
```csv
brand,Electronics,Appliances,DIY_Tools,Building,Workwear,Automotive
Kjell Group,1,0,0,0,0,0
Clas Ohlson,1,1,1,0,1,0
Byggmax Group,0,0,1,1,1,0
...
```

## Usage

```bash
# Standard LAR (simple average across all intents)
asr lar audit.csv soa.csv dist.csv service.csv --out lar_standard.csv

# Category-weighted LAR (fair comparison across categories)
asr lar audit.csv soa.csv dist.csv service.csv --out lar_weighted.csv --weighted
```

## Output

The weighted output includes:
- `brand`: Peer name
- `categories`: Categories where peer competes
- `num_categories`: Count of categories
- `E`, `X`, `A`, `D`, `S`: Overall scores (averaged across categories)
- `LAR_weighted`: Category-weighted LAR score
- `category_details`: Per-category E, X, LAR breakdown

## Benefits

1. **Fair peer comparisons**: Specialists aren't penalized for narrow focus
2. **Balanced category influence**: 9 DIY peers doesn't over-weight DIY in overall scores
3. **Category-specific insights**: See who dominates each vertical
4. **Flexible reporting**: Can show overall rankings and category leaderboards

## Future Enhancements

- **Category-level A (Share-of-Answer)**: Currently A is overall; could compute per-category from intent logs
- **Category weighting by revenue/margin**: Weight categories by business importance, not equally
- **Dynamic category detection**: Auto-detect which categories a peer competes in from audit results
