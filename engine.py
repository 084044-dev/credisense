"""
CrediSense - deterministic credit pre-screening engine.

The DECISION is made here, by transparent, auditable rules.
The AI layer (ai.py) only EXPLAINS the decision; it can never change it.

All thresholds are illustrative, loosely modelled on common practice for
unsecured personal loans in India (CIBIL score bands, FOIR caps, age at
maturity). They are NOT any real lender's credit policy.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field, asdict

# --------------------------------------------------------------------------
# Policy parameters (one place, so a credit manager can tune them)
# --------------------------------------------------------------------------
POLICY = {
    "min_age": 21,
    "max_age_at_maturity_salaried": 60,
    "max_age_at_maturity_self_employed": 65,
    "min_net_monthly_income": 25_000,
    "min_cibil": 650,                 # below this -> hard decline
    "cibil_full_marks": 820,          # at/above this -> full points
    "foir_cap_hard": 0.65,            # above this -> hard decline
    "foir_cap_approve": 0.55,         # above this -> cannot auto-approve
    "foir_target": 0.50,              # used to compute max eligible loan
    "max_enquiries_6m": 4,            # above this -> 'credit hungry' flag
    "min_loan": 50_000,
    "max_loan": 40_00_000,
    "min_tenure": 12,
    "max_tenure": 60,
    "approve_score": 70,
    "refer_score": 50,
    "borderline_band": 3,             # +/- points around a cut-off
    "assessment_rate": 0.14,          # notional rate used to test affordability
}

EMPLOYMENT_TYPES = ["Salaried", "Self-employed"]
DPD_OPTIONS = [
    "No delays",
    "1-30 days late",
    "31-89 days late",
    "90+ days late / default",
]
PURPOSES = [
    "Home renovation", "Medical", "Education", "Wedding", "Travel",
    "Debt consolidation", "Business expansion", "Consumer durables", "Other",
]

# Indicative annual interest rate by outcome band (risk-based pricing)
RATE_TABLE = [  # (min_score, annual_rate)
    (85, 0.1099),
    (70, 0.1250),
    (50, 0.1450),
    (0, 0.1650),
]


# --------------------------------------------------------------------------
# Data classes
# --------------------------------------------------------------------------
@dataclass
class Applicant:
    name: str = ""
    age: int = 30
    employment_type: str = "Salaried"
    years_in_job: float = 3.0
    monthly_income: float = 60_000
    existing_emi: float = 0
    cibil_score: int | None = 750      # None = New-to-credit (no history)
    loan_amount: float = 3_00_000
    tenure_months: int = 36
    purpose: str = "Home renovation"
    dpd_12m: str = "No delays"
    enquiries_6m: int = 1
    remarks: str = ""                  # free text, NOT used for scoring

    def fingerprint(self) -> str:
        """Deterministic ID so the same inputs always map to the same assessment."""
        d = asdict(self)
        d.pop("name", None)            # identity doesn't change the risk
        d.pop("remarks", None)
        raw = json.dumps(d, sort_keys=True, default=str)
        return "CS-" + hashlib.sha256(raw.encode()).hexdigest()[:8].upper()


@dataclass
class Factor:
    name: str
    points: float
    max_points: float
    value_display: str
    comment: str


@dataclass
class Assessment:
    assessment_id: str
    decision: str                      # APPROVE / REFER / DECLINE
    score: float
    factors: list[Factor]
    knockouts: list[str]
    flags: list[str]
    metrics: dict
    sensitivity: list[str] = field(default_factory=list)
    borderline: bool = False
    primary_reason: str = ""

    def facts_for_ai(self, applicant: Applicant) -> dict:
        """The ONLY data sent to the language model. No name, no remarks
        unless sanitised separately. Numbers are pre-formatted so the model
        doesn't have to do arithmetic."""
        return {
            "assessment_id": self.assessment_id,
            "decision": self.decision,
            "score_out_of_100": round(self.score, 1),
            "primary_reason": self.primary_reason,
            "borderline": self.borderline,
            "hard_policy_breaches": self.knockouts,
            "risk_flags": self.flags,
            "score_drivers": [
                {
                    "factor": f.name,
                    "points": round(f.points, 1),
                    "max_points": f.max_points,
                    "applicant_value": f.value_display,
                    "note": f.comment,
                }
                for f in self.factors
            ],
            "key_numbers": {
                "loan_requested": inr(applicant.loan_amount),
                "tenure_months": applicant.tenure_months,
                "new_emi_tested_at_14pct_assessment_rate": inr(self.metrics["new_emi"]),
                "foir_after_loan": pct(self.metrics["foir_post"]),
                "max_eligible_loan_at_50pct_foir": inr(self.metrics["max_eligible_loan"]),
                "indicative_interest_rate": pct(self.metrics["rate"]),
                "employment_type": applicant.employment_type,
                "loan_purpose": applicant.purpose,
            },
            "what_would_change_the_outcome": self.sensitivity,
            "policy_reference": {
                "score_scale": "0-100",
                "auto_approve_min_score": POLICY["approve_score"],
                "refer_min_score": POLICY["refer_score"],
                "min_cibil": POLICY["min_cibil"],
                "cibil_range": "300-900",
                "foir_target": "50%",
                "foir_max_for_auto_approval": "55%",
                "foir_hard_limit": "65%",
                "assessment_rate_for_emi_test": "14%",
                "min_net_monthly_income": inr(POLICY["min_net_monthly_income"]),
                "max_age_at_maturity": "60 salaried / 65 self-employed",
                "max_enquiries_6m_without_flag": POLICY["max_enquiries_6m"],
            },
        }


# --------------------------------------------------------------------------
# Formatting helpers (Indian numbering: 12,34,567)
# --------------------------------------------------------------------------
def inr(x: float) -> str:
    x = int(round(x))
    neg = x < 0
    s = str(abs(x))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-₹" if neg else "₹") + s


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


# --------------------------------------------------------------------------
# Finance maths
# --------------------------------------------------------------------------
def emi(principal: float, annual_rate: float, months: int) -> float:
    r = annual_rate / 12
    if r == 0:
        return principal / months
    f = (1 + r) ** months
    return principal * r * f / (f - 1)


def principal_from_emi(emi_amt: float, annual_rate: float, months: int) -> float:
    if emi_amt <= 0:
        return 0.0
    r = annual_rate / 12
    f = (1 + r) ** months
    return emi_amt * (f - 1) / (r * f)


def rate_for_score(score: float) -> float:
    for min_s, rate in RATE_TABLE:
        if score >= min_s:
            return rate
    return RATE_TABLE[-1][1]


# --------------------------------------------------------------------------
# 1) INPUT VALIDATION  (runs BEFORE anything reaches scoring or the AI)
# --------------------------------------------------------------------------
def validate(a: Applicant) -> tuple[list[str], list[str]]:
    """Returns (errors, warnings). Errors block the assessment."""
    e, w = [], []
    P = POLICY

    if not (18 <= a.age <= 75):
        e.append("Age must be between 18 and 75.")
    if a.employment_type not in EMPLOYMENT_TYPES:
        e.append("Choose an employment type.")
    if a.years_in_job < 0 or a.years_in_job > 50:
        e.append("Years in current job/business must be between 0 and 50.")
    elif a.years_in_job > max(0, a.age - 16):
        e.append(f"{a.years_in_job:g} years of work is not possible at age {a.age}. "
                 "Check the age or the work experience.")
    if a.monthly_income <= 0:
        e.append("Net monthly income is required.")
    elif a.monthly_income > 50_00_000:
        e.append("Net monthly income above ₹50,00,000 looks like a typing error "
                 "(did you enter annual income?).")
    if a.existing_emi < 0:
        e.append("Existing EMIs cannot be negative.")
    elif a.monthly_income > 0 and a.existing_emi >= a.monthly_income:
        e.append("Existing EMIs are equal to or more than monthly income. "
                 "Please re-check both values.")
    if a.cibil_score is not None and not (300 <= a.cibil_score <= 900):
        e.append("CIBIL score must be between 300 and 900 (or tick 'No credit history').")
    if not (P["min_loan"] <= a.loan_amount <= P["max_loan"]):
        e.append(f"Loan amount must be between {inr(P['min_loan'])} and {inr(P['max_loan'])} "
                 "for this product.")
    if not (P["min_tenure"] <= a.tenure_months <= P["max_tenure"]):
        e.append(f"Tenure must be {P['min_tenure']}-{P['max_tenure']} months.")
    if a.dpd_12m not in DPD_OPTIONS:
        e.append("Choose the repayment history option.")
    if not (0 <= a.enquiries_6m <= 30):
        e.append("Credit enquiries in last 6 months must be between 0 and 30.")
    if len(a.remarks) > 400:
        e.append("Remarks are limited to 400 characters.")

    # Soft sanity checks - allowed, but shown to the user
    if not e:
        if a.monthly_income > 0 and a.loan_amount > 30 * a.monthly_income:
            w.append("Loan requested is more than 30x monthly income - unusually high.")
        if a.monthly_income < 10_000:
            w.append("Monthly income below ₹10,000 - is this monthly (not weekly) income?")
        if a.age < 23 and a.monthly_income > 5_00_000:
            w.append("Very high income for age - please double-check.")
        if a.cibil_score is not None and a.cibil_score >= 800 and a.dpd_12m == DPD_OPTIONS[3]:
            w.append("A default in the last 12 months is unusual with a 800+ CIBIL score - "
                     "verify the bureau report.")
    return e, w


# --------------------------------------------------------------------------
# 2) SCORING  (transparent points scorecard, 100 points)
# --------------------------------------------------------------------------
def _lin(x, x0, x1, y0, y1):
    """Linear interpolation, clamped. Used instead of step bands so that
    two nearly-identical applicants get nearly-identical scores."""
    if x0 == x1:
        return y1
    t = max(0.0, min(1.0, (x - x0) / (x1 - x0)))
    return y0 + t * (y1 - y0)


def _score_components(a: Applicant, rate: float):
    P = POLICY
    factors, knockouts, flags = [], [], []

    new_emi = emi(a.loan_amount, rate, a.tenure_months)
    foir_pre = a.existing_emi / a.monthly_income
    foir_post = (a.existing_emi + new_emi) / a.monthly_income
    lti = a.loan_amount / (a.monthly_income * 12)

    # --- Credit bureau score (35) ---
    if a.cibil_score is None:
        pts = 15.0
        flags.append("New-to-credit: no bureau history, so repayment behaviour cannot be verified")
        factors.append(Factor("Credit score (CIBIL)", pts, 35, "No history (NTC)",
                              "Neutral points given; needs manual review"))
    else:
        pts = _lin(a.cibil_score, P["min_cibil"], P["cibil_full_marks"], 5, 35)
        if a.cibil_score < P["min_cibil"]:
            pts = 0.0
            knockouts.append(f"CIBIL score {a.cibil_score} is below the minimum {P['min_cibil']}")
        comment = ("Excellent" if a.cibil_score >= 780 else
                   "Good" if a.cibil_score >= 730 else
                   "Fair" if a.cibil_score >= P["min_cibil"] else "Below policy minimum")
        factors.append(Factor("Credit score (CIBIL)", pts, 35, str(a.cibil_score), comment))

    # --- Affordability: FOIR after the new loan (25) ---
    if foir_post <= 0.30:
        pts = 25.0
    elif foir_post <= 0.50:
        pts = _lin(foir_post, 0.30, 0.50, 25, 12)
    elif foir_post <= P["foir_cap_hard"]:
        pts = _lin(foir_post, 0.50, P["foir_cap_hard"], 12, 0)
    else:
        pts = 0.0
    if foir_post > P["foir_cap_hard"]:
        knockouts.append(f"FOIR after this loan would be {pct(foir_post)}, above the "
                         f"{pct(P['foir_cap_hard'])} hard limit")
    elif foir_post > P["foir_cap_approve"]:
        flags.append(f"FOIR after this loan is {pct(foir_post)} (above {pct(P['foir_cap_approve'])})"
                     " - repayment could be stretched")
    factors.append(Factor("Affordability (FOIR after loan)", pts, 25, pct(foir_post),
                          f"New EMI {inr(new_emi)} + existing {inr(a.existing_emi)} "
                          f"on income {inr(a.monthly_income)}"))

    # --- Employment stability (15) ---
    full_years = 3 if a.employment_type == "Salaried" else 5
    min_years = 1 if a.employment_type == "Salaried" else 2
    pts = _lin(a.years_in_job, 0, full_years, 0, 15)
    if a.years_in_job < min_years:
        flags.append(f"Only {a.years_in_job:g} yr(s) in current "
                     f"{'job' if a.employment_type == 'Salaried' else 'business'} "
                     f"(policy prefers {min_years}+)")
    factors.append(Factor("Employment stability", pts, 15,
                          f"{a.years_in_job:g} yrs ({a.employment_type})",
                          f"Full marks at {full_years}+ years"))

    # --- Repayment history + credit hunger (15) ---
    dpd_pts = {DPD_OPTIONS[0]: 15.0, DPD_OPTIONS[1]: 8.0,
               DPD_OPTIONS[2]: 2.0, DPD_OPTIONS[3]: 0.0}[a.dpd_12m]
    if a.dpd_12m == DPD_OPTIONS[3]:
        knockouts.append("90+ days past due / default in the last 12 months")
    elif a.dpd_12m == DPD_OPTIONS[2]:
        flags.append("Serious delay (31-89 days) in the last 12 months")
    enq_penalty = 0.0
    if a.enquiries_6m > P["max_enquiries_6m"]:
        enq_penalty = min(5.0, (a.enquiries_6m - P["max_enquiries_6m"]) * 1.5)
        flags.append(f"{a.enquiries_6m} credit enquiries in 6 months - possible 'credit hungry' behaviour")
    pts = max(0.0, dpd_pts - enq_penalty)
    factors.append(Factor("Repayment history", pts, 15,
                          f"{a.dpd_12m}; {a.enquiries_6m} enquiries",
                          "Past 12 months DPD + recent loan applications"))

    # --- Loan size vs income (10) ---
    pts = _lin(lti, 0.5, 2.0, 10, 0)
    if lti > 3:
        flags.append(f"Loan is {lti:.1f}x annual income")
    factors.append(Factor("Loan size vs annual income", pts, 10, f"{lti:.2f}x",
                          "Full marks up to 0.5x annual income"))

    # --- Hard eligibility rules (no points, pass/fail) ---
    max_age = (P["max_age_at_maturity_salaried"] if a.employment_type == "Salaried"
               else P["max_age_at_maturity_self_employed"])
    age_at_maturity = a.age + a.tenure_months / 12
    if a.age < P["min_age"]:
        knockouts.append(f"Applicant age {a.age} is below the minimum {P['min_age']}")
    if age_at_maturity > max_age:
        knockouts.append(f"Age at loan maturity would be {age_at_maturity:.1f}, above the "
                         f"{max_age} limit for {a.employment_type.lower()} applicants")
    if a.monthly_income < P["min_net_monthly_income"]:
        knockouts.append(f"Net monthly income {inr(a.monthly_income)} is below the minimum "
                         f"{inr(P['min_net_monthly_income'])}")

    score = sum(f.points for f in factors)
    metrics = dict(new_emi=new_emi, foir_pre=foir_pre, foir_post=foir_post, lti=lti,
                   age_at_maturity=age_at_maturity, max_age=max_age)
    return score, factors, knockouts, flags, metrics


def _decide(score, knockouts, flags):
    P = POLICY
    if knockouts:
        return "DECLINE"
    if score >= P["approve_score"] and not flags:
        return "APPROVE"
    if score >= P["refer_score"]:
        return "REFER"
    return "DECLINE"


def assess(a: Applicant, with_sensitivity: bool = True) -> Assessment:
    P = POLICY
    # Affordability is always tested at one fixed, slightly conservative
    # "assessment rate" so the score doesn't depend on the price it produces.
    score, factors, knockouts, flags, m = _score_components(a, P["assessment_rate"])
    decision = _decide(score, knockouts, flags)

    max_emi = max(0.0, P["foir_target"] * a.monthly_income - a.existing_emi)
    m["rate"] = rate_for_score(score)
    m["assessment_rate"] = P["assessment_rate"]
    m["max_eligible_loan"] = min(P["max_loan"],
                                 principal_from_emi(max_emi, P["assessment_rate"], a.tenure_months))

    # Grey zone: anything within +/-3 points of a cut-off goes to a human.
    borderline = (not knockouts) and any(
        abs(score - t) < P["borderline_band"] for t in (P["approve_score"], P["refer_score"]))
    if borderline:
        flags = flags + ["Score is within 3 points of a cut-off (grey zone) - "
                         "routed to an underwriter instead of an automatic outcome"]
        decision = "REFER"

    if knockouts:
        reason = knockouts[0]
    elif borderline:
        reason = (f"Score {score:.1f} is within {P['borderline_band']} points of a cut-off, "
                  "so a credit officer reviews it")
    elif decision == "APPROVE":
        reason = f"All policy rules are met and the score is at least {P['approve_score']}"
    elif decision == "REFER" and flags:
        reason = flags[0]
    elif decision == "REFER":
        reason = (f"Score {score:.1f} is below the {P['approve_score']} needed for automatic "
                  "approval")
    else:
        reason = f"Score {score:.1f} is below the minimum of {P['refer_score']}"
    res = Assessment(
        assessment_id=a.fingerprint(), decision=decision, score=score,
        factors=factors, knockouts=knockouts, flags=flags, metrics=m, borderline=borderline,
        primary_reason=reason,
    )
    if with_sensitivity:
        res.sensitivity = sensitivity(a, res)
    return res


# --------------------------------------------------------------------------
# 3) SENSITIVITY: "what would change the outcome?" (counterfactuals)
# --------------------------------------------------------------------------
def _clone(a: Applicant, **kw) -> Applicant:
    d = asdict(a)
    d.update(kw)
    return Applicant(**d)


def sensitivity(a: Applicant, res: Assessment) -> list[str]:
    tips = []
    if res.decision == "APPROVE":
        headroom = res.metrics["max_eligible_loan"] - a.loan_amount
        if headroom > 0:
            tips.append(f"Within policy. Could borrow up to about {inr(res.metrics['max_eligible_loan'])} "
                        f"at the same tenure while keeping FOIR at 50%.")
        return tips

    # a) Shorter tenure fixes age-at-maturity breaches
    if res.metrics["age_at_maturity"] > res.metrics["max_age"]:
        max_months = int((res.metrics["max_age"] - a.age) * 12) // 12 * 12
        if max_months >= POLICY["min_tenure"]:
            alt = assess(_clone(a, tenure_months=max_months), with_sensitivity=False)
            tips.append(f"Reduce tenure to {max_months} months to meet the age-at-maturity rule "
                        f"(outcome would be {alt.decision}, score {alt.score:.0f}).")

    # b) Smaller loan amount
    for frac in (0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3):
        amt = round(a.loan_amount * frac / 10_000) * 10_000
        if amt < POLICY["min_loan"]:
            break
        alt = assess(_clone(a, loan_amount=amt), with_sensitivity=False)
        if _rank(alt.decision) > _rank(res.decision):
            tips.append(f"Lower the loan to about {inr(amt)} -> outcome {alt.decision} "
                        f"(score {alt.score:.0f}).")
            break

    # c) Longer tenure (lower EMI) if age allows
    for t in (48, 60):
        if t > a.tenure_months:
            alt = assess(_clone(a, tenure_months=t), with_sensitivity=False)
            if _rank(alt.decision) > _rank(res.decision):
                tips.append(f"Extend tenure to {t} months (lower EMI) -> outcome {alt.decision}.")
                break

    # d) Credit score improvement
    if a.cibil_score is not None and a.cibil_score < 900:
        for bump in (10, 20, 30, 50, 75, 100):
            s = min(900, a.cibil_score + bump)
            alt = assess(_clone(a, cibil_score=s), with_sensitivity=False)
            if _rank(alt.decision) > _rank(res.decision):
                tips.append(f"A CIBIL score of {s} (+{s - a.cibil_score}) would change the outcome "
                            f"to {alt.decision}, other things equal.")
                break

    # e) Paying down existing EMIs
    if a.existing_emi > 0:
        for frac in (0.75, 0.5, 0.25, 0.0):
            alt = assess(_clone(a, existing_emi=a.existing_emi * frac), with_sensitivity=False)
            if _rank(alt.decision) > _rank(res.decision):
                tips.append(f"Closing existing loans so EMIs fall to {inr(a.existing_emi * frac)} "
                            f"-> outcome {alt.decision}.")
                break

    # f) Fewer recent credit enquiries
    if a.enquiries_6m > POLICY["max_enquiries_6m"]:
        alt = assess(_clone(a, enquiries_6m=POLICY["max_enquiries_6m"]), with_sensitivity=False)
        if _rank(alt.decision) > _rank(res.decision):
            tips.append(f"Avoiding new loan/card applications until recent enquiries drop to "
                        f"{POLICY['max_enquiries_6m']} or fewer -> outcome {alt.decision}.")

    # g) New-to-credit guidance
    if a.cibil_score is None:
        tips.append("Build 6-12 months of bureau history (e.g. a secured credit card or small "
                    "consumer loan repaid on time) so the application can be scored automatically.")

    if not tips:
        tips.append("No single small change moves this application to a better outcome; "
                    "the underwriter should review the full file.")
    return tips


def _rank(decision: str) -> int:
    return {"DECLINE": 0, "REFER": 1, "APPROVE": 2}[decision]


# --------------------------------------------------------------------------
# Batch helper
# --------------------------------------------------------------------------
BATCH_COLUMNS = ["name", "age", "employment_type", "years_in_job", "monthly_income",
                 "existing_emi", "cibil_score", "loan_amount", "tenure_months",
                 "purpose", "dpd_12m", "enquiries_6m"]


def applicant_from_row(row: dict) -> Applicant:
    def num(k, cast=float, default=None):
        v = row.get(k)
        if v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() == "":
            return default
        return cast(float(str(v).replace(",", "").replace("₹", "")))

    cibil_raw = row.get("cibil_score")
    cibil = None
    if cibil_raw is not None and str(cibil_raw).strip().upper() not in ("", "NTC", "NAN", "NONE"):
        cibil = int(float(cibil_raw))
    return Applicant(
        name=str(row.get("name", "") or ""),
        age=num("age", int, 0),
        employment_type=str(row.get("employment_type", "")).strip(),
        years_in_job=num("years_in_job", float, -1),
        monthly_income=num("monthly_income", float, 0),
        existing_emi=num("existing_emi", float, 0),
        cibil_score=cibil,
        loan_amount=num("loan_amount", float, 0),
        tenure_months=num("tenure_months", int, 0),
        purpose=str(row.get("purpose", "Other") or "Other"),
        dpd_12m=str(row.get("dpd_12m", "")).strip(),
        enquiries_6m=num("enquiries_6m", int, 0),
    )
