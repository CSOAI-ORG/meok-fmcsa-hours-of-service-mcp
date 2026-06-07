<!-- mcp-name: io.github.CSOAI-ORG/meok-fmcsa-hours-of-service-mcp -->
[![MCP Scorecard: 84/100](https://img.shields.io/badge/proofof.ai-84%2F100-5b21b6)](https://proofof.ai/scorecard/meok-fmcsa-hours-of-service-mcp.html)

# meok-fmcsa-hours-of-service-mcp

> US FMCSA Hours of Service + CSA score forecast + ELD mandate + New Entrant Safety Audit prep. 49 CFR Part 395 / Part 385 callable compliance toolkit. By **MEOK AI Labs**.

## Why this exists

US trucking's single biggest $ exposure is **CSA score deterioration + FMCSA intervention**. Once a carrier crosses a BASIC intervention threshold:
- Insurance premiums spike (often 40-300%)
- Shipper Smartway / Inspection-System gates close
- FMCSA roadside inspection frequency triples (ISS-2 lane)
- Compliance Review / Conditional or Unsatisfactory safety rating
- Out-of-service orders + loss of authority

This MCP gives Safety Directors, named DOT compliance staff, and owner-operators the callable toolkit to **prevent** CSA failure across property-carrying + passenger-carrying CMV operations.

This is the **US equivalent** of [`meok-tacho-audit-mcp`](https://pypi.org/project/meok-tacho-audit-mcp/) — extends MEOK from UK to the US market (~30,000+ ATA member firms).

## Install

```bash
pip install meok-fmcsa-hours-of-service-mcp
```

## Claude Desktop config

```json
{
  "mcpServers": {
    "fmcsa-hos": {
      "command": "meok-fmcsa-hours-of-service-mcp"
    }
  }
}
```

## Tools (8)

| Tool | Use case |
|------|----------|
| `check_property_carrying_hos` | 49 CFR 395.3 — 11/14/60-70/30-min/34-restart audit |
| `check_passenger_carrying_hos` | 49 CFR 395.5 — 10/15/60-70 (passenger split) |
| `check_short_haul_exemption` | 150 air-mile no-ELD eligibility |
| `check_eld_mandate_compliance` | ELD required >10k lbs interstate since Dec 2017 |
| `check_eld_supplier_registered` | FMCSA-published registered + revoked ELD cross-check |
| `forecast_csa_score` | 7 BASICs + intervention bands + month-to-threshold |
| `audit_iep_inspection` | ISS score + roadside inspection intervention review |
| `prepare_safety_audit_pack` | New Entrant Safety Audit checklist (12-18 months) |

## Pricing

- **Free** — MIT self-host
- **Starter** — $39/mo
- **Pro** — $99/mo (multi-driver)
- **Fleet** — $599/mo (50+ trucks, audit-export)

[Subscribe Pro → $99/mo](https://www.csoai.org/checkout)

## Regulatory basis

- 49 CFR Part 395 — Hours of Service of Drivers (property §395.3, passenger §395.5)
- 49 CFR Part 395.8 — ELD mandate (final compliance 18 Dec 2017)
- 49 CFR Part 395.22 — Registered ELD device requirement
- 49 CFR Part 385 — Safety Fitness Procedures (Compliance Review, Safety Ratings)
- 49 CFR Part 385 Subpart D — New Entrant Safety Audit
- 49 CFR Part 390/391/392/393/396 — operational, DQ files, maintenance, DVIRs
- FMCSA Compliance, Safety, Accountability (CSA) — 7 BASICs:
  Unsafe Driving · HOS · Driver Fitness · Controlled Substances/Alcohol ·
  Vehicle Maintenance · Hazardous Materials · Crash Indicator
- FMCSA Inspection Selection System (ISS) — carrier intervention prioritisation

## Sign your responses

```bash
export MEOK_HMAC_SECRET="your-secret"
meok-fmcsa-hours-of-service-mcp
```

## License

MIT © 2026 Nicholas Templeman / MEOK AI Labs · [haulage.app](https://haulage.app)


<!-- GEO-FOOTER:v1 -->

---

### Part of the MEOK constellation

This MCP is one node in a connected ecosystem built by **MEOK AI LABS** around a single
sovereign AI core — governed agents with a hash-chained audit trail, mapped to the CSOAI
compliance charter.

- 🌐 The whole map: **<https://meok.ai/constellation>**
- 🛡️ AI governance & certification: **<https://councilof.ai>** · **<https://csoai.org>**
- ✅ Verify any signed report: **<https://meok.ai/verify>**
