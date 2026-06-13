#!/usr/bin/env python3
"""
MEOK FMCSA Hours of Service + CSA Compliance MCP
=================================================

By MEOK AI Labs · https://haulage.app · MIT
<!-- mcp-name: io.github.CSOAI-ORG/meok-fmcsa-hours-of-service-mcp -->

WHAT THIS DOES
--------------
US trucking's single biggest $ exposure: **CSA Score deterioration + FMCSA
intervention**. Once a carrier crosses a BASIC intervention threshold:
  - Insurance premiums spike (often 40-300%)
  - Shipper Smartway/Inspection-System gates close
  - FMCSA roadside inspection frequency triples (ISS-2 lane)
  - Compliance Review / Conditional or Unsatisfactory safety rating
  - Out-of-service orders + loss of authority

This MCP gives Safety Directors, named DOT compliance staff, and owner-operators
the callable toolkit to PREVENT CSA failure by automating the daily compliance
work for US property-carrying + passenger-carrying CMV operations:

  - 49 CFR Part 395 Hours of Service (property + passenger split)
  - 150 air-mile short-haul exception (no ELD required)
  - ELD mandate (49 CFR 395.8 — Dec 2017 cliff still trapping carriers)
  - FMCSA-registered ELD device check (revoked-list cross-check)
  - CSA score forecast across the 7 BASICs
  - Roadside inspection (IEP/ISS) intervention-threshold audit
  - New Entrant Safety Audit prep (mandatory 12-18 months after USDOT)

TOOLS (8)
---------
- check_property_carrying_hos(driver_log)     → 11/14/60-70/30-min/34-restart
- check_passenger_carrying_hos(driver_log)    → 10/15/60-70 (passenger split)
- check_short_haul_exemption(operator)        → 150 air-mile no-ELD eligibility
- check_eld_mandate_compliance(vehicle_spec)  → ELD required >10k lbs interstate
- check_eld_supplier_registered(device)       → FMCSA-published list cross-check
- forecast_csa_score(operator_data)           → 7 BASICs + intervention bands
- audit_iep_inspection(roadside)              → ISS score + threshold review
- prepare_safety_audit_pack(operator_data)    → New Entrant Safety Audit checklist

WHY YOU PAY
-----------
One avoided Compliance Review = $30k-$200k saved (insurance + fines + lost
authority). $39/mo Starter is a rounding error vs the existential risk.

PRICING
-------
Free MIT self-host · $39/mo Starter · $99/mo Pro · $599/mo Fleet.

REGULATORY BASIS
----------------
49 CFR Part 395 — Hours of Service of Drivers
49 CFR Part 395.8 — Automatic On-Board Recording Devices / ELD mandate
49 CFR Part 385 — Safety Fitness Procedures
49 CFR Part 390 — General (USDOT registration)
FMCSA Compliance, Safety, Accountability (CSA) program — 7 BASICs
DOT/FMCSA New Entrant Safety Audit — 49 CFR 385 Subpart D
Inspection Selection System (ISS) — FMCSA carrier intervention prioritisation
"""

from __future__ import annotations
import urllib.request as _meter_urlreq
import urllib.error as _meter_urlerr
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone, date, timedelta
from typing import Optional
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("meok-fmcsa-hours-of-service")
_HMAC_SECRET = os.environ.get("MEOK_HMAC_SECRET", "")


# ──────────────────────────────────────────────────────────────────────
# Regulatory tables — 49 CFR Part 395
# ──────────────────────────────────────────────────────────────────────

# Property-carrying CMV (49 CFR 395.3)
PROPERTY_HOS_LIMITS = {
    "max_driving_hr": 11,                 # 11-hour driving limit (after 10h off)
    "max_on_duty_window_hr": 14,          # 14-hour on-duty window
    "max_weekly_60_hr_7_day": 60,         # 60h / 7-day rolling
    "max_weekly_70_hr_8_day": 70,         # 70h / 8-day rolling
    "mandatory_break_after_hr": 8,        # 30-min break after 8h driving
    "mandatory_break_min": 30,
    "restart_hr": 34,                     # 34-hour restart provision
    "min_off_duty_hr": 10,                # 10 consecutive hours off
}

# Passenger-carrying CMV (49 CFR 395.5) — different rules
PASSENGER_HOS_LIMITS = {
    "max_driving_hr": 10,                 # 10-hour driving limit
    "max_on_duty_window_hr": 15,          # 15-hour on-duty window
    "max_weekly_60_hr_7_day": 60,
    "max_weekly_70_hr_8_day": 70,
    "min_off_duty_hr": 8,                 # 8 consecutive hours off
    # Note: passenger drivers NOT required to take 30-min break (395.3(a)(3)(ii))
}

# 150 air-mile short-haul exception (49 CFR 395.1(e)(1))
SHORT_HAUL_RULES = {
    "max_air_mile_radius": 150,
    "max_on_duty_window_hr": 14,
    "min_off_duty_hr": 10,
    "must_return_to_normal_work_location": True,
    "no_eld_required_if_satisfied": True,
    "must_keep_time_records_6_months": True,
}

# ELD mandate (49 CFR 395.8 / Dec 18, 2017 final compliance)
ELD_MANDATE = {
    "effective_compliance_date": "2017-12-18",
    "aobrd_grandfather_ended": "2019-12-16",
    "required_vehicles": "CMV >10,000 lbs GVWR in interstate commerce, "
                         "or transporting hazmat in placardable quantities, "
                         "or designed to carry 9+ passengers (incl. driver) for hire / 16+ not for hire",
    "exempt_pre_2000_engine": True,        # vehicles with engine model year pre-2000 exempt
    "exempt_drive_away_tow_away": True,    # drive-away/tow-away operations
    "exempt_short_haul_150_mi": True,      # 150 air-mile short-haul drivers
    "exempt_8_day_or_fewer_per_30": True,  # drivers who keep RODS ≤8 days in any 30-day period
}

# CSA BASICs (FMCSA Compliance, Safety, Accountability)
CSA_BASICS = {
    "unsafe_driving": {
        "intervention_threshold_general": 65,        # percentile
        "intervention_threshold_passenger": 50,
        "intervention_threshold_hazmat": 60,
    },
    "hours_of_service_compliance": {
        "intervention_threshold_general": 65,
        "intervention_threshold_passenger": 50,
        "intervention_threshold_hazmat": 60,
    },
    "driver_fitness": {
        "intervention_threshold_general": 80,
        "intervention_threshold_passenger": 65,
        "intervention_threshold_hazmat": 75,
    },
    "controlled_substances_alcohol": {
        "intervention_threshold_general": 80,
        "intervention_threshold_passenger": 65,
        "intervention_threshold_hazmat": 75,
    },
    "vehicle_maintenance": {
        "intervention_threshold_general": 80,
        "intervention_threshold_passenger": 65,
        "intervention_threshold_hazmat": 75,
    },
    "hazardous_materials_compliance": {
        "intervention_threshold_general": 80,
        "intervention_threshold_passenger": 80,
        "intervention_threshold_hazmat": 80,
    },
    "crash_indicator": {
        "intervention_threshold_general": 65,
        "intervention_threshold_passenger": 50,
        "intervention_threshold_hazmat": 60,
    },
}

# Inspection Selection System bands (49 CFR Part 385 — risk tiers)
ISS_BANDS = {
    "iss_1_pass": "0-49 → Pass — no inspection priority",
    "iss_2_optional": "50-74 → Optional — inspector discretion",
    "iss_3_inspect": "75-100 → Inspect — selected for roadside inspection",
}

# HOS infringement severity weights (rough FMCSA CSA HOS BASIC contribution)
HOS_INFRINGEMENT_WEIGHTS = {
    "exceeded_11h_driving": 7,
    "exceeded_14h_on_duty_window": 5,
    "exceeded_60h_7_day": 7,
    "exceeded_70h_8_day": 7,
    "missed_30min_break_after_8h": 3,
    "insufficient_10h_off_duty": 5,
    "exceeded_10h_driving_passenger": 7,
    "exceeded_15h_on_duty_passenger": 5,
    "insufficient_8h_off_duty_passenger": 5,
    "eld_malfunction_unreported_8d": 4,
    "false_logs_or_log_falsification": 10,
    "no_eld_when_required": 5,
}

# New Entrant Safety Audit triggers (49 CFR 385 Subpart D)
SAFETY_AUDIT_TRIGGERS = [
    "Newly registered USDOT carrier — 12-18 months after USDOT issued",
    "Reincarnated carrier (chameleon) — FMCSA priority audit",
    "Petition for review of Conditional rating",
    "Post-Compliance-Review remedial action verification",
]


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _sign(payload: dict) -> str:
    if not _HMAC_SECRET:
        return "unsigned-no-key-configured"
    return hmac.new(
        _HMAC_SECRET.encode(),
        json.dumps(payload, sort_keys=True, default=str).encode(),
        hashlib.sha256,
    ).hexdigest()


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _attestation(payload: dict) -> dict:
    return {**payload, "ts": _ts(), "sig": _sign(payload),
            "issuer": "meok-fmcsa-hours-of-service-mcp", "version": "1.0.0"}


# ──────────────────────────────────────────────────────────────────────
# Tools
# ──────────────────────────────────────────────────────────────────────


def _server_meter_check(api_key: str = "") -> dict:
    """Calls the live /verify endpoint for server-side metering. Fail-open."""
    try:
        data = json.dumps({"api_key": api_key, "tool": ""}).encode()
        req = _meter_urlreq.Request(_METER_URL, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with _meter_urlreq.urlopen(req, timeout=2.5) as r:
            d = json.loads(r.read())
            if isinstance(d, dict) and "allowed" in d:
                return d
    except Exception:
        pass
    return {"allowed": True, "tier": "anonymous", "remaining": 200, "upgrade_url": "https://meok.ai/pricing"}


_METER_URL = "https://proofof.ai/verify"


@mcp.tool()
def check_property_carrying_hos(
    driver_name: str = "",
    daily_segments: Optional[list] = None,
    week_starting: str = "",
    schedule: str = "60_hr_7_day",
) -> dict:
    """Audit a property-carrying CMV driver against 49 CFR 395.3.

    Args:
      daily_segments: list of dicts per day, like
        {"date": "2026-06-02", "driving_hr": 11.5, "on_duty_hr": 13,
         "longest_continuous_drive_hr": 8.5, "break_min_after_8h": 25,
         "off_duty_hr": 10}
      schedule: '60_hr_7_day' or '70_hr_8_day'

    Returns infringement list + severity total + 34-hour restart eligibility.
    """
    daily_segments = daily_segments or []
    infringements = []

    # Weekly cumulative limit (rolling)
    weekly_on_duty = sum(d.get("on_duty_hr", d.get("driving_hr", 0)) for d in daily_segments)
    weekly_limit = (PROPERTY_HOS_LIMITS["max_weekly_60_hr_7_day"]
                    if schedule == "60_hr_7_day"
                    else PROPERTY_HOS_LIMITS["max_weekly_70_hr_8_day"])
    if weekly_on_duty > weekly_limit:
        code = "exceeded_60h_7_day" if schedule == "60_hr_7_day" else "exceeded_70h_8_day"
        infringements.append({
            "code": code,
            "actual_hr": round(weekly_on_duty, 2),
            "limit_hr": weekly_limit,
            "severity": HOS_INFRINGEMENT_WEIGHTS[code],
        })

    for d in daily_segments:
        dr = d.get("driving_hr", 0)
        on_duty = d.get("on_duty_hr", dr)
        longest_drive = d.get("longest_continuous_drive_hr", 0)
        break_min = d.get("break_min_after_8h", 30)
        off_duty = d.get("off_duty_hr", 24)

        # 11-hour driving limit
        if dr > PROPERTY_HOS_LIMITS["max_driving_hr"]:
            infringements.append({
                "code": "exceeded_11h_driving", "date": d.get("date"),
                "actual_hr": dr,
                "severity": HOS_INFRINGEMENT_WEIGHTS["exceeded_11h_driving"],
            })

        # 14-hour on-duty window
        if on_duty > PROPERTY_HOS_LIMITS["max_on_duty_window_hr"]:
            infringements.append({
                "code": "exceeded_14h_on_duty_window", "date": d.get("date"),
                "actual_hr": on_duty,
                "severity": HOS_INFRINGEMENT_WEIGHTS["exceeded_14h_on_duty_window"],
            })

        # 30-minute break after 8 hours driving
        if longest_drive >= PROPERTY_HOS_LIMITS["mandatory_break_after_hr"] and \
           break_min < PROPERTY_HOS_LIMITS["mandatory_break_min"]:
            infringements.append({
                "code": "missed_30min_break_after_8h", "date": d.get("date"),
                "actual_break_min": break_min,
                "severity": HOS_INFRINGEMENT_WEIGHTS["missed_30min_break_after_8h"],
            })

        # 10-hour off-duty between shifts
        if off_duty < PROPERTY_HOS_LIMITS["min_off_duty_hr"]:
            infringements.append({
                "code": "insufficient_10h_off_duty", "date": d.get("date"),
                "actual_hr": off_duty,
                "severity": HOS_INFRINGEMENT_WEIGHTS["insufficient_10h_off_duty"],
            })

    # 34-hour restart eligibility = any contiguous off-duty stretch ≥ 34h in the period
    restart_eligible = any(d.get("off_duty_hr", 0) >= PROPERTY_HOS_LIMITS["restart_hr"]
                           for d in daily_segments)

    payload = {
        "tool": "check_property_carrying_hos",
        "driver_name": driver_name,
        "week_starting": week_starting,
        "schedule": schedule,
        "weekly_on_duty_hr": round(weekly_on_duty, 2),
        "weekly_limit_hr": weekly_limit,
        "infringement_count": len(infringements),
        "infringements": infringements,
        "severity_total": sum(i.get("severity", 0) for i in infringements),
        "restart_34h_eligible": restart_eligible,
        "regulation": "49 CFR 395.3",
    }
    return _attestation(payload)


@mcp.tool()
def check_passenger_carrying_hos(
    driver_name: str = "",
    daily_segments: Optional[list] = None,
    week_starting: str = "",
    schedule: str = "60_hr_7_day",
) -> dict:
    """Audit a passenger-carrying CMV driver against 49 CFR 395.5.

    Args:
      daily_segments: list of dicts per day, like
        {"date": "2026-06-02", "driving_hr": 10.5, "on_duty_hr": 14,
         "off_duty_hr": 8}
      schedule: '60_hr_7_day' or '70_hr_8_day'

    Passenger rules differ from property:
      - 10h driving (vs 11h property)
      - 15h on-duty window (vs 14h property)
      - 8h off-duty minimum (vs 10h property)
      - No 30-minute break mandate
    """
    daily_segments = daily_segments or []
    infringements = []

    weekly_on_duty = sum(d.get("on_duty_hr", d.get("driving_hr", 0)) for d in daily_segments)
    weekly_limit = (PASSENGER_HOS_LIMITS["max_weekly_60_hr_7_day"]
                    if schedule == "60_hr_7_day"
                    else PASSENGER_HOS_LIMITS["max_weekly_70_hr_8_day"])
    if weekly_on_duty > weekly_limit:
        code = "exceeded_60h_7_day" if schedule == "60_hr_7_day" else "exceeded_70h_8_day"
        infringements.append({
            "code": code,
            "actual_hr": round(weekly_on_duty, 2),
            "limit_hr": weekly_limit,
            "severity": HOS_INFRINGEMENT_WEIGHTS[code],
        })

    for d in daily_segments:
        dr = d.get("driving_hr", 0)
        on_duty = d.get("on_duty_hr", dr)
        off_duty = d.get("off_duty_hr", 24)

        if dr > PASSENGER_HOS_LIMITS["max_driving_hr"]:
            infringements.append({
                "code": "exceeded_10h_driving_passenger", "date": d.get("date"),
                "actual_hr": dr,
                "severity": HOS_INFRINGEMENT_WEIGHTS["exceeded_10h_driving_passenger"],
            })

        if on_duty > PASSENGER_HOS_LIMITS["max_on_duty_window_hr"]:
            infringements.append({
                "code": "exceeded_15h_on_duty_passenger", "date": d.get("date"),
                "actual_hr": on_duty,
                "severity": HOS_INFRINGEMENT_WEIGHTS["exceeded_15h_on_duty_passenger"],
            })

        if off_duty < PASSENGER_HOS_LIMITS["min_off_duty_hr"]:
            infringements.append({
                "code": "insufficient_8h_off_duty_passenger", "date": d.get("date"),
                "actual_hr": off_duty,
                "severity": HOS_INFRINGEMENT_WEIGHTS["insufficient_8h_off_duty_passenger"],
            })

    payload = {
        "tool": "check_passenger_carrying_hos",
        "driver_name": driver_name,
        "week_starting": week_starting,
        "schedule": schedule,
        "weekly_on_duty_hr": round(weekly_on_duty, 2),
        "weekly_limit_hr": weekly_limit,
        "infringement_count": len(infringements),
        "infringements": infringements,
        "severity_total": sum(i.get("severity", 0) for i in infringements),
        "regulation": "49 CFR 395.5",
        "note": "Passenger-carrying drivers are not required to take the 30-minute break (49 CFR 395.3(a)(3)(ii)).",
    }
    return _attestation(payload)


@mcp.tool()
def check_short_haul_exemption(
    operator_name: str = "",
    drivers: Optional[list] = None,
) -> dict:
    """Verify which drivers qualify for the 150 air-mile short-haul exception
    (49 CFR 395.1(e)(1)) — no ELD / no RODS required.

    Args:
      drivers: list of dicts like
        {"name": "...", "max_air_mile_radius_d": 120, "on_duty_window_hr": 13,
         "off_duty_between_shifts_hr": 10, "returns_to_normal_work_location": True,
         "time_records_kept_months": 6}
    """
    drivers = drivers or []
    eligible = []
    ineligible = []

    for d in drivers:
        name = d.get("name", "")
        reasons_failing = []

        if d.get("max_air_mile_radius_d", 999) > SHORT_HAUL_RULES["max_air_mile_radius"]:
            reasons_failing.append(
                f"radius {d.get('max_air_mile_radius_d')} mi > 150 mi limit")

        if d.get("on_duty_window_hr", 99) > SHORT_HAUL_RULES["max_on_duty_window_hr"]:
            reasons_failing.append(
                f"on-duty window {d.get('on_duty_window_hr')}h > 14h limit")

        if d.get("off_duty_between_shifts_hr", 0) < SHORT_HAUL_RULES["min_off_duty_hr"]:
            reasons_failing.append(
                f"off-duty between shifts {d.get('off_duty_between_shifts_hr')}h < 10h required")

        if not d.get("returns_to_normal_work_location", False):
            reasons_failing.append("does not return to normal work location each day")

        if d.get("time_records_kept_months", 0) < 6:
            reasons_failing.append(
                f"time records only kept {d.get('time_records_kept_months')}mo < 6mo required")

        if reasons_failing:
            ineligible.append({"name": name, "reasons_failing": reasons_failing,
                               "eld_required": True})
        else:
            eligible.append({"name": name, "eld_required": False,
                             "rationale": "Satisfies 150 air-mile short-haul exception"})

    return _attestation({
        "tool": "check_short_haul_exemption",
        "operator_name": operator_name,
        "drivers_evaluated": len(drivers),
        "eligible_count": len(eligible),
        "eligible": eligible,
        "ineligible_count": len(ineligible),
        "ineligible": ineligible,
        "regulation": "49 CFR 395.1(e)(1)",
        "rules_reference": SHORT_HAUL_RULES,
    })


@mcp.tool()
def check_eld_mandate_compliance(
    vrn_or_vin: str = "",
    gvwr_lbs: int = 0,
    interstate_commerce: bool = True,
    engine_model_year: int = 2020,
    is_drive_away_tow_away: bool = False,
    short_haul_150_mi: bool = False,
    rods_days_per_30: int = 30,
    passenger_capacity: int = 0,
    hazmat_placardable: bool = False,
    eld_installed: bool = False,
) -> dict:
    """Determine if a CMV requires an ELD per 49 CFR 395.8 (effective Dec 2017).

    A vehicle requires an ELD if (interstate AND any of):
      - GVWR > 10,000 lbs
      - Carries hazmat in placardable quantities
      - Designed to carry 9+ passengers (incl driver) for hire OR 16+ not-for-hire

    Exemptions (do not require ELD even if above):
      - Engine model year pre-2000
      - Drive-away/tow-away operations
      - Short-haul 150 air-mile exception
      - Drivers keeping RODS ≤8 days in any 30-day period
    """
    triggers = []
    if interstate_commerce and gvwr_lbs > 10000:
        triggers.append(">10,000 lbs GVWR in interstate commerce")
    if interstate_commerce and hazmat_placardable:
        triggers.append("hazmat in placardable quantities")
    # 9+ for hire or 16+ not-for-hire
    if interstate_commerce and passenger_capacity >= 9:
        triggers.append(f"{passenger_capacity}-passenger CMV (passenger ELD trigger)")

    exemptions = []
    if engine_model_year < 2000:
        exemptions.append(f"engine model year {engine_model_year} < 2000 (pre-2000 exempt)")
    if is_drive_away_tow_away:
        exemptions.append("drive-away / tow-away operation")
    if short_haul_150_mi:
        exemptions.append("150 air-mile short-haul exception")
    if rods_days_per_30 <= 8:
        exemptions.append(f"only {rods_days_per_30} RODS days/30d (≤8d exempt)")

    eld_required = bool(triggers) and not exemptions

    compliance_status = "COMPLIANT"
    advisory = "No ELD obligation under 49 CFR 395.8."
    if eld_required:
        if eld_installed:
            compliance_status = "COMPLIANT_ELD_FITTED"
            advisory = "ELD fitted; verify FMCSA-registered with check_eld_supplier_registered."
        else:
            compliance_status = "NON_COMPLIANT"
            advisory = (
                "ELD REQUIRED but NOT installed. This is a CSA HOS BASIC violation"
                " + roadside out-of-service (OOS) risk. Fit FMCSA-registered ELD immediately."
            )

    return _attestation({
        "tool": "check_eld_mandate_compliance",
        "vrn_or_vin": vrn_or_vin,
        "gvwr_lbs": gvwr_lbs,
        "engine_model_year": engine_model_year,
        "interstate_commerce": interstate_commerce,
        "eld_required": eld_required,
        "eld_installed": eld_installed,
        "triggers": triggers,
        "exemptions": exemptions,
        "compliance_status": compliance_status,
        "advisory": advisory,
        "regulation": "49 CFR 395.8 (final compliance 18 Dec 2017)",
    })


@mcp.tool()
def check_eld_supplier_registered(
    eld_make: str = "",
    eld_model: str = "",
    fmcsa_registration_id: str = "",
    is_on_revoked_list: bool = False,
    fmcsa_registered_list: Optional[list] = None,
) -> dict:
    """Confirm an ELD device is on the FMCSA-published registered list
    and NOT on the revoked list.

    Args:
      fmcsa_registered_list: optional list of registered devices like
        [{"make": "Geotab", "model": "GO9", "registration_id": "ELD12345"}]
        — if omitted, the tool just validates the make/model/id triple
        against the revoked flag.
    """
    fmcsa_registered_list = fmcsa_registered_list or []
    match = None
    if fmcsa_registered_list:
        for d in fmcsa_registered_list:
            if (d.get("make", "").lower() == eld_make.lower()
                and d.get("model", "").lower() == eld_model.lower()):
                match = d
                break

    if is_on_revoked_list:
        status = "REVOKED"
        advisory = ("FMCSA has REVOKED this ELD. Drivers using a revoked ELD are "
                    "out of compliance after the 60-day transition (49 CFR 395.22(h))."
                    " Replace device + re-certify logs immediately.")
    elif match is not None:
        status = "REGISTERED"
        advisory = "Device is on the FMCSA registered list."
    elif fmcsa_registered_list:
        status = "NOT_FOUND_ON_LIST"
        advisory = ("Device not found on supplied FMCSA registered list."
                    " Verify make/model + registration ID at fmcsa.dot.gov/registered-eld-list.")
    else:
        status = "UNVERIFIED_NO_LIST_PROVIDED"
        advisory = ("No registered-list supplied — call this tool with"
                    " fmcsa_registered_list= the official FMCSA JSON to verify.")

    return _attestation({
        "tool": "check_eld_supplier_registered",
        "eld_make": eld_make,
        "eld_model": eld_model,
        "fmcsa_registration_id": fmcsa_registration_id,
        "status": status,
        "matched_record": match,
        "advisory": advisory,
        "regulation": "49 CFR 395.22(a) — only FMCSA-registered ELDs may be used",
    })


@mcp.tool()
def forecast_csa_score(
    operator_name: str = "",
    operator_segment: str = "general",
    basics_percentiles: Optional[dict] = None,
    trend_per_basic_per_month: Optional[dict] = None,
    forecast_months: int = 3,
) -> dict:
    """Forecast a carrier's CSA score across the 7 BASICs.

    Args:
      operator_segment: 'general' / 'passenger' / 'hazmat'
      basics_percentiles: current percentile per BASIC, like
        {"unsafe_driving": 55, "hours_of_service_compliance": 62, ...}
      trend_per_basic_per_month: deterioration trend (+) or improvement (-) per BASIC
      forecast_months: months forward to project (default 3)
    """
    basics_percentiles = basics_percentiles or {}
    trend_per_basic_per_month = trend_per_basic_per_month or {}

    threshold_key = {
        "general": "intervention_threshold_general",
        "passenger": "intervention_threshold_passenger",
        "hazmat": "intervention_threshold_hazmat",
    }.get(operator_segment, "intervention_threshold_general")

    basics_state = []
    alerts_now = []
    alerts_forecast = []
    for basic, cfg in CSA_BASICS.items():
        current = basics_percentiles.get(basic, 0)
        trend = trend_per_basic_per_month.get(basic, 0)
        threshold = cfg[threshold_key]
        forecast = min(100.0, max(0.0, current + trend * forecast_months))

        intervention_now = current >= threshold
        intervention_forecast = forecast >= threshold

        if intervention_now:
            alerts_now.append(
                f"{basic}: at {current}% ≥ {threshold}% intervention threshold")
        if intervention_forecast and not intervention_now:
            months_to_threshold = None
            if trend > 0:
                months_to_threshold = round((threshold - current) / trend, 1)
            alerts_forecast.append({
                "basic": basic,
                "current_pct": current,
                "forecast_pct": round(forecast, 1),
                "threshold_pct": threshold,
                "months_to_threshold": months_to_threshold,
            })

        basics_state.append({
            "basic": basic,
            "current_percentile": current,
            "forecast_percentile": round(forecast, 1),
            "intervention_threshold": threshold,
            "intervention_now": intervention_now,
            "intervention_forecast": intervention_forecast,
        })

    return _attestation({
        "tool": "forecast_csa_score",
        "operator_name": operator_name,
        "operator_segment": operator_segment,
        "forecast_months": forecast_months,
        "basics": basics_state,
        "alerts_now": alerts_now,
        "alerts_forecast": alerts_forecast,
        "overall_advisory": (
            "URGENT: at intervention NOW — expect Compliance Review/Conditional rating."
            if alerts_now else
            (f"{len(alerts_forecast)} BASIC(s) projected to cross threshold in"
             f" {forecast_months}mo — book corrective action."
             if alerts_forecast else
             "All 7 BASICs below intervention thresholds — maintain.")
        ),
        "regulation": "FMCSA CSA program — 7 BASICs, intervention bands per 49 CFR 385",
    })


@mcp.tool()
def audit_iep_inspection(
    operator_name: str = "",
    iss_score: int = 0,
    recent_inspections: Optional[list] = None,
    oos_violations_12mo: int = 0,
) -> dict:
    """Audit Inspection Selection System (ISS) score + roadside inspection
    intervention implications.

    Args:
      iss_score: 0-100 — FMCSA-calculated carrier inspection priority
      recent_inspections: list of dicts like
        {"date": "2026-05-15", "level": "Level I", "result": "no_violation",
         "violations": [], "oos": False}
      oos_violations_12mo: count of Out-of-Service violations in trailing 12mo
    """
    recent_inspections = recent_inspections or []

    if iss_score >= 75:
        band = "ISS_3_INSPECT"
        band_label = "Inspect"
    elif iss_score >= 50:
        band = "ISS_2_OPTIONAL"
        band_label = "Optional"
    else:
        band = "ISS_1_PASS"
        band_label = "Pass"

    # Aggregate stats
    inspections_12mo = len(recent_inspections)
    violations_total = sum(len(i.get("violations", [])) for i in recent_inspections)
    oos_count = sum(1 for i in recent_inspections if i.get("oos"))

    intervention_risk = "LOW"
    intervention_advisory = "Routine."
    if iss_score >= 75 or oos_violations_12mo >= 3:
        intervention_risk = "HIGH"
        intervention_advisory = (
            "FMCSA likely to issue Compliance Review or Off-Site Investigation."
            " Get root-cause analysis + corrective action plan filed now.")
    elif iss_score >= 50 or oos_violations_12mo >= 1:
        intervention_risk = "MEDIUM"
        intervention_advisory = (
            "Increased roadside inspection probability."
            " Audit current OOS exposure (brakes, lighting, tires, driver qualification).")

    return _attestation({
        "tool": "audit_iep_inspection",
        "operator_name": operator_name,
        "iss_score": iss_score,
        "iss_band": band,
        "iss_band_label": band_label,
        "iss_band_meaning": ISS_BANDS[band.lower()],
        "inspections_count_in_sample": inspections_12mo,
        "violations_total": violations_total,
        "oos_in_sample": oos_count,
        "oos_violations_12mo_reported": oos_violations_12mo,
        "intervention_risk": intervention_risk,
        "intervention_advisory": intervention_advisory,
        "regulation": "Inspection Selection System (ISS) — FMCSA carrier prioritisation;"
                      " intervention bands per 49 CFR 385 / SafeStat methodology.",
    })


@mcp.tool()
def prepare_safety_audit_pack(
    operator_name: str = "",
    usdot_number: str = "",
    mc_number: str = "",
    months_since_usdot_issued: int = 12,
    fleet_size: int = 0,
    expected_audit_date: str = "",
) -> dict:
    """Produce the New Entrant Safety Audit evidence checklist
    (49 CFR 385 Subpart D — typically 12-18 months after USDOT issued).
    """
    in_audit_window = 12 <= months_since_usdot_issued <= 18
    overdue = months_since_usdot_issued > 18

    return _attestation({
        "tool": "prepare_safety_audit_pack",
        "operator_name": operator_name,
        "usdot_number": usdot_number,
        "mc_number": mc_number,
        "months_since_usdot_issued": months_since_usdot_issued,
        "fleet_size": fleet_size,
        "expected_audit_date": expected_audit_date,
        "in_new_entrant_audit_window": in_audit_window,
        "audit_overdue": overdue,
        "audit_triggers_reference": SAFETY_AUDIT_TRIGGERS,
        "evidence_checklist": [
            "USDOT registration certificate + MCS-150 currency (<=24 months)",
            "Operating authority (MC number) if for-hire interstate",
            "BOC-3 process-agent designation on file",
            "UCR (Unified Carrier Registration) current year",
            "Driver Qualification (DQ) files per 49 CFR 391 — MVR, road test, medical card",
            "Drug & Alcohol Clearinghouse queries on each driver (pre-employment full + annual limited)",
            "Random drug & alcohol testing pool — 50% drug + 10% alcohol annual rate",
            "Hours of Service records — ELD logs / time records 6 months back",
            "Vehicle maintenance records — annual inspection per 49 CFR 396.17",
            "Driver Vehicle Inspection Reports (DVIRs) per 49 CFR 396.11 — file 3 months",
            "Hazmat training records (if hazmat carrier) — 49 CFR 172.704",
            "Accident register per 49 CFR 390.15 — 3 years",
            "Proof of financial responsibility — insurance certificates ($750K minimum general freight)",
            "Process for cargo securement compliance (49 CFR 393)",
            "ELD device list + FMCSA registration IDs (if applicable)",
            "Written Safety Management plan",
        ],
        "automatic_failure_items": [
            "Using a driver without a valid CDL",
            "Operating a vehicle declared OOS without repair",
            "Failing to require pre-employment drug test",
            "Failing to implement random drug & alcohol testing program",
            "Knowingly using a driver with prior alcohol/drug rule violation without RTD process",
            "Failing to maintain valid Accident Register",
            "Operating without required liability insurance",
        ],
        "regulation": "49 CFR 385 Subpart D (New Entrant Safety Audit);"
                      " 49 CFR 390, 391, 392, 393, 395, 396 (operational rules)",
        "next_action": (
            "URGENT: audit window passed — FMCSA may revoke new-entrant status."
            if overdue else
            ("Audit window OPEN — pre-audit gap analysis recommended."
             if in_audit_window else
             "Pre-window — start building Safety Management plan + DQ-file rigour now.")
        ),
    })


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()


# ── MEOK monetization layer (Stripe upgrade · PAYG · pricing) ──────────
# Free tier is zero-config. Upgrade to Pro (unlimited) or pay-as-you-go per call.
import os as _meok_os
MEOK_STRIPE_UPGRADE = "https://buy.stripe.com/5kQ6oJ0xS3ce8sl7ew8k91j"  # Pro (unlimited)
MEOK_PAYG_KEY = _meok_os.environ.get("MEOK_PAYG_KEY", "")  # set to enable PAYG (x402 / ~GBP0.05 per call)
MEOK_PRICING = "https://meok.ai/pricing"


def meok_upsell(tier: str = "free") -> dict:
    """Monetization options for free-tier callers: Pro upgrade, PAYG, or pricing page."""
    if tier != "free":
        return {}
    return {"upgrade_url": MEOK_STRIPE_UPGRADE,
            "payg_enabled": bool(MEOK_PAYG_KEY),
            "pricing": MEOK_PRICING}
