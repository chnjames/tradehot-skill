# Data Quality and Source Policy

`tradehot` is an intelligence Skill. Its local JSON files are designed to guide collection, prioritization, and reporting, not to replace official databases or professional advice.

## Source Priority

| Tier | Source type | Usage |
| --- | --- | --- |
| 5 | Government, customs, tax, trade, official platform announcements, official international organizations | Use as primary evidence |
| 4 | Established industry media and official industry bodies | Use as supporting evidence |
| 3 | Third-party data tools, logistics indices, market dashboards | Use as directional signals |
| 1-2 | Forums, social media, seller discussions | Use only as leads; do not treat as verified facts |

## Static Knowledge Files

| File | Reliability note |
| --- | --- |
| `sources/tariff_reference.json` | Category-level tariff and market access reference. Always verify against official tariff databases before business decisions. |
| `sources/trade_calendar.json` | Planning calendar for exhibitions, promotions, seasonal demand, and holidays. Verify exact dates with event organizers or platform announcements. |
| `sources/competitors.json` | Competitor-country monitoring heuristics, not official market share data. |
| `sources/logistics_hotspots.json` | Logistics watchlist and route risk hints. Verify current disruption status with carriers, ports, or logistics indices. |
| `sources/fx_risk.json` | FX and payment risk reference. Verify with central banks, banks, credit insurers, or current market data. |

## Official Verification Targets

Use official or primary sources for high-risk topics:

- Tariffs and market access: ITC Market Access Map, USITC HTS, EU TARIC, WTO tariff data, target-country customs sites.
- Trade remedies: WTO trade remedies, US International Trade Commission, US Department of Commerce, EU trade defence, target-country trade remedy authorities.
- Sanctions and export controls: OFAC, BIS Entity List, EU sanctions map, UK sanctions list, UN sanctions list.
- Product safety and recalls: EU Safety Gate, US CPSC recalls, FDA, EPA, FCC, relevant national product-safety regulators.
- Platform policies: official seller centers and platform policy announcements.

## Reporting Rules

- Keep source names and URLs in generated reports when available.
- Mark uncertainty when sources conflict or when only media reports are available.
- Do not present static reference values as current official rates.
- For tariffs, always ask users to confirm product description, HS Code depth, origin, destination, and shipment date.
- For compliance, recall, sanctions, export control, tax, and customs matters, include a professional-advice disclaimer.
