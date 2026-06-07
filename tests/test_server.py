import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server import (
    check_property_carrying_hos, check_passenger_carrying_hos,
    check_short_haul_exemption, check_eld_mandate_compliance,
    check_eld_supplier_registered, forecast_csa_score,
    audit_iep_inspection, prepare_safety_audit_pack,
    PROPERTY_HOS_LIMITS, PASSENGER_HOS_LIMITS,
    HOS_INFRINGEMENT_WEIGHTS, CSA_BASICS,
)


def _call(t, **kw):
    fn = t.fn if hasattr(t, "fn") else t
    return fn(**kw)


# ──────────────────────────────────────────────────────────────────────
# check_property_carrying_hos — 49 CFR 395.3
# ──────────────────────────────────────────────────────────────────────

def test_property_11h_driving_breach():
    r = _call(check_property_carrying_hos, driver_name="J",
              daily_segments=[{"date": "2026-06-02", "driving_hr": 11.5,
                               "on_duty_hr": 13, "longest_continuous_drive_hr": 7,
                               "break_min_after_8h": 30, "off_duty_hr": 10}])
    codes = [i["code"] for i in r["infringements"]]
    assert "exceeded_11h_driving" in codes


def test_property_14h_window_breach():
    r = _call(check_property_carrying_hos, driver_name="J",
              daily_segments=[{"date": "2026-06-02", "driving_hr": 10,
                               "on_duty_hr": 15, "longest_continuous_drive_hr": 7,
                               "break_min_after_8h": 30, "off_duty_hr": 10}])
    assert any(i["code"] == "exceeded_14h_on_duty_window" for i in r["infringements"])


def test_property_30min_break_missed():
    r = _call(check_property_carrying_hos, driver_name="J",
              daily_segments=[{"date": "2026-06-02", "driving_hr": 10,
                               "on_duty_hr": 12, "longest_continuous_drive_hr": 9,
                               "break_min_after_8h": 15, "off_duty_hr": 10}])
    assert any(i["code"] == "missed_30min_break_after_8h" for i in r["infringements"])


def test_property_60h_7day_breach():
    days = [{"date": f"2026-06-0{d+1}", "driving_hr": 10, "on_duty_hr": 11,
             "longest_continuous_drive_hr": 7, "break_min_after_8h": 30,
             "off_duty_hr": 10} for d in range(7)]
    r = _call(check_property_carrying_hos, driver_name="K",
              daily_segments=days, schedule="60_hr_7_day")
    assert any(i["code"] == "exceeded_60h_7_day" for i in r["infringements"])


def test_property_clean_week_no_infringements():
    r = _call(check_property_carrying_hos, driver_name="C",
              daily_segments=[{"date": "2026-06-02", "driving_hr": 8,
                               "on_duty_hr": 12, "longest_continuous_drive_hr": 7,
                               "break_min_after_8h": 30, "off_duty_hr": 10}])
    assert r["infringement_count"] == 0


def test_property_34h_restart_eligible():
    r = _call(check_property_carrying_hos, driver_name="R",
              daily_segments=[{"date": "2026-06-02", "driving_hr": 8,
                               "on_duty_hr": 12, "longest_continuous_drive_hr": 7,
                               "break_min_after_8h": 30, "off_duty_hr": 34}])
    assert r["restart_34h_eligible"] is True


# ──────────────────────────────────────────────────────────────────────
# check_passenger_carrying_hos — 49 CFR 395.5
# ──────────────────────────────────────────────────────────────────────

def test_passenger_10h_driving_breach():
    r = _call(check_passenger_carrying_hos, driver_name="P",
              daily_segments=[{"date": "2026-06-02", "driving_hr": 10.5,
                               "on_duty_hr": 14, "off_duty_hr": 9}])
    assert any(i["code"] == "exceeded_10h_driving_passenger" for i in r["infringements"])


def test_passenger_15h_on_duty_breach():
    r = _call(check_passenger_carrying_hos, driver_name="P",
              daily_segments=[{"date": "2026-06-02", "driving_hr": 9,
                               "on_duty_hr": 16, "off_duty_hr": 9}])
    assert any(i["code"] == "exceeded_15h_on_duty_passenger" for i in r["infringements"])


def test_passenger_8h_off_duty_insufficient():
    r = _call(check_passenger_carrying_hos, driver_name="P",
              daily_segments=[{"date": "2026-06-02", "driving_hr": 9,
                               "on_duty_hr": 13, "off_duty_hr": 6}])
    assert any(i["code"] == "insufficient_8h_off_duty_passenger" for i in r["infringements"])


def test_passenger_clean_no_30min_break_required():
    # passenger drivers exempt from 30-minute break — should not flag even with 0 min
    r = _call(check_passenger_carrying_hos, driver_name="P",
              daily_segments=[{"date": "2026-06-02", "driving_hr": 9,
                               "on_duty_hr": 13, "off_duty_hr": 9}])
    assert r["infringement_count"] == 0
    assert "passenger-carrying" in r["note"].lower()


# ──────────────────────────────────────────────────────────────────────
# check_short_haul_exemption — 150 air-mile
# ──────────────────────────────────────────────────────────────────────

def test_short_haul_eligible():
    r = _call(check_short_haul_exemption, operator_name="ACME",
              drivers=[{"name": "A", "max_air_mile_radius_d": 100,
                        "on_duty_window_hr": 13,
                        "off_duty_between_shifts_hr": 10,
                        "returns_to_normal_work_location": True,
                        "time_records_kept_months": 6}])
    assert r["eligible_count"] == 1
    assert r["ineligible_count"] == 0


def test_short_haul_ineligible_radius_too_big():
    r = _call(check_short_haul_exemption, operator_name="ACME",
              drivers=[{"name": "B", "max_air_mile_radius_d": 200,
                        "on_duty_window_hr": 13,
                        "off_duty_between_shifts_hr": 10,
                        "returns_to_normal_work_location": True,
                        "time_records_kept_months": 6}])
    assert r["eligible_count"] == 0
    assert r["ineligible_count"] == 1
    assert any("radius" in reason.lower() for reason in r["ineligible"][0]["reasons_failing"])


# ──────────────────────────────────────────────────────────────────────
# check_eld_mandate_compliance — 49 CFR 395.8
# ──────────────────────────────────────────────────────────────────────

def test_eld_required_interstate_heavy_no_eld():
    r = _call(check_eld_mandate_compliance, vrn_or_vin="VIN1",
              gvwr_lbs=26000, interstate_commerce=True,
              engine_model_year=2018, eld_installed=False)
    assert r["eld_required"] is True
    assert r["compliance_status"] == "NON_COMPLIANT"


def test_eld_pre_2000_engine_exempt():
    r = _call(check_eld_mandate_compliance, vrn_or_vin="VIN2",
              gvwr_lbs=26000, interstate_commerce=True,
              engine_model_year=1998, eld_installed=False)
    assert r["eld_required"] is False
    assert any("pre-2000" in e for e in r["exemptions"])


def test_eld_short_haul_exempt():
    r = _call(check_eld_mandate_compliance, vrn_or_vin="VIN3",
              gvwr_lbs=26000, interstate_commerce=True,
              engine_model_year=2020, short_haul_150_mi=True,
              eld_installed=False)
    assert r["eld_required"] is False
    assert any("short-haul" in e for e in r["exemptions"])


def test_eld_compliant_when_installed():
    r = _call(check_eld_mandate_compliance, vrn_or_vin="VIN4",
              gvwr_lbs=26000, interstate_commerce=True,
              engine_model_year=2020, eld_installed=True)
    assert r["eld_required"] is True
    assert r["compliance_status"] == "COMPLIANT_ELD_FITTED"


# ──────────────────────────────────────────────────────────────────────
# check_eld_supplier_registered
# ──────────────────────────────────────────────────────────────────────

def test_eld_supplier_registered_match():
    r = _call(check_eld_supplier_registered, eld_make="Geotab",
              eld_model="GO9", fmcsa_registration_id="ELD12345",
              fmcsa_registered_list=[
                  {"make": "Geotab", "model": "GO9", "registration_id": "ELD12345"},
              ])
    assert r["status"] == "REGISTERED"


def test_eld_supplier_revoked():
    r = _call(check_eld_supplier_registered, eld_make="BadCo",
              eld_model="X1", fmcsa_registration_id="ELD99999",
              is_on_revoked_list=True)
    assert r["status"] == "REVOKED"
    assert "REVOKED" in r["advisory"]


def test_eld_supplier_not_on_list():
    r = _call(check_eld_supplier_registered, eld_make="UnknownCo",
              eld_model="ZZZ", fmcsa_registration_id="ELD00000",
              fmcsa_registered_list=[
                  {"make": "Geotab", "model": "GO9", "registration_id": "ELD12345"},
              ])
    assert r["status"] == "NOT_FOUND_ON_LIST"


# ──────────────────────────────────────────────────────────────────────
# forecast_csa_score
# ──────────────────────────────────────────────────────────────────────

def test_csa_intervention_now():
    r = _call(forecast_csa_score, operator_name="ACME",
              operator_segment="general",
              basics_percentiles={"hours_of_service_compliance": 70,
                                  "unsafe_driving": 80},
              trend_per_basic_per_month={},
              forecast_months=3)
    assert len(r["alerts_now"]) >= 2
    assert "URGENT" in r["overall_advisory"]


def test_csa_intervention_forecast_but_not_now():
    r = _call(forecast_csa_score, operator_name="ACME",
              operator_segment="general",
              basics_percentiles={"hours_of_service_compliance": 50},
              trend_per_basic_per_month={"hours_of_service_compliance": 6},
              forecast_months=3)
    assert len(r["alerts_forecast"]) >= 1
    assert r["alerts_forecast"][0]["months_to_threshold"] is not None


def test_csa_passenger_segment_lower_threshold():
    # Passenger segment threshold for HOS is 50% (not 65%)
    r = _call(forecast_csa_score, operator_name="BUS",
              operator_segment="passenger",
              basics_percentiles={"hours_of_service_compliance": 55},
              forecast_months=3)
    hos_entry = next(b for b in r["basics"] if b["basic"] == "hours_of_service_compliance")
    assert hos_entry["intervention_threshold"] == 50
    assert hos_entry["intervention_now"] is True


def test_csa_all_clean():
    r = _call(forecast_csa_score, operator_name="OK",
              operator_segment="general",
              basics_percentiles={k: 10 for k in CSA_BASICS},
              forecast_months=3)
    assert r["alerts_now"] == []
    assert "below intervention thresholds" in r["overall_advisory"]


# ──────────────────────────────────────────────────────────────────────
# audit_iep_inspection
# ──────────────────────────────────────────────────────────────────────

def test_iep_high_iss_high_risk():
    r = _call(audit_iep_inspection, operator_name="ACME", iss_score=80,
              oos_violations_12mo=4)
    assert r["iss_band"] == "ISS_3_INSPECT"
    assert r["intervention_risk"] == "HIGH"


def test_iep_low_iss_low_risk():
    r = _call(audit_iep_inspection, operator_name="OK", iss_score=20,
              oos_violations_12mo=0)
    assert r["iss_band"] == "ISS_1_PASS"
    assert r["intervention_risk"] == "LOW"


def test_iep_medium_band():
    r = _call(audit_iep_inspection, operator_name="MED", iss_score=60,
              oos_violations_12mo=1)
    assert r["iss_band"] == "ISS_2_OPTIONAL"
    assert r["intervention_risk"] == "MEDIUM"


# ──────────────────────────────────────────────────────────────────────
# prepare_safety_audit_pack
# ──────────────────────────────────────────────────────────────────────

def test_safety_audit_in_window():
    r = _call(prepare_safety_audit_pack, operator_name="NEW",
              usdot_number="USDOT9999999", months_since_usdot_issued=14)
    assert r["in_new_entrant_audit_window"] is True
    assert r["audit_overdue"] is False
    assert len(r["evidence_checklist"]) >= 12
    assert any("Clearinghouse" in e for e in r["evidence_checklist"])


def test_safety_audit_overdue():
    r = _call(prepare_safety_audit_pack, operator_name="LATE",
              usdot_number="USDOT8888888", months_since_usdot_issued=24)
    assert r["audit_overdue"] is True
    assert "URGENT" in r["next_action"]


def test_safety_audit_automatic_failures_listed():
    r = _call(prepare_safety_audit_pack, operator_name="X",
              usdot_number="USDOT7777", months_since_usdot_issued=10)
    assert any("CDL" in f for f in r["automatic_failure_items"])
    assert any("drug" in f.lower() for f in r["automatic_failure_items"])


# ──────────────────────────────────────────────────────────────────────
# HMAC attestation chain
# ──────────────────────────────────────────────────────────────────────

def test_attestation_chain():
    r = _call(check_property_carrying_hos, driver_name="X",
              daily_segments=[{"date": "2026-06-02", "driving_hr": 8,
                               "on_duty_hr": 12, "longest_continuous_drive_hr": 7,
                               "break_min_after_8h": 30, "off_duty_hr": 10}])
    assert "sig" in r and "ts" in r
    assert r["issuer"] == "meok-fmcsa-hours-of-service-mcp"
    assert r["version"] == "1.0.0"


def test_attestation_with_hmac_secret():
    os.environ["MEOK_HMAC_SECRET"] = "test-secret-key"
    # re-import so module-level secret is picked up
    import importlib, server
    importlib.reload(server)
    r = _call(server.check_eld_supplier_registered,
              eld_make="Geotab", eld_model="GO9", fmcsa_registration_id="ELD1")
    assert r["sig"] != "unsigned-no-key-configured"
    assert len(r["sig"]) == 64  # sha256 hex
    del os.environ["MEOK_HMAC_SECRET"]


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
