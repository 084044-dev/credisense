"""Sample (fictional) applicants used to showcase the app. Any resemblance to
real people is coincidental. All figures are synthetic."""
import random
from engine import Applicant, DPD_OPTIONS, PURPOSES

PERSONAS = {
    "Priya Sharma - IT professional, strong profile": Applicant(
        name="Priya Sharma", age=29, employment_type="Salaried", years_in_job=5,
        monthly_income=95_000, existing_emi=8_000, cibil_score=782, loan_amount=5_00_000,
        tenure_months=36, purpose="Home renovation", dpd_12m=DPD_OPTIONS[0], enquiries_6m=1),
    "Rahul Verma - salaried, some late payments": Applicant(
        name="Rahul Verma", age=34, employment_type="Salaried", years_in_job=2,
        monthly_income=55_000, existing_emi=12_000, cibil_score=712, loan_amount=3_00_000,
        tenure_months=48, purpose="Wedding", dpd_12m=DPD_OPTIONS[1], enquiries_6m=3),
    "Anita Desai - boutique owner (self-employed)": Applicant(
        name="Anita Desai", age=42, employment_type="Self-employed", years_in_job=8,
        monthly_income=1_20_000, existing_emi=22_000, cibil_score=756, loan_amount=8_00_000,
        tenure_months=48, purpose="Business expansion", dpd_12m=DPD_OPTIONS[0], enquiries_6m=2),
    "Vikram Singh - low CIBIL score": Applicant(
        name="Vikram Singh", age=26, employment_type="Salaried", years_in_job=0.8,
        monthly_income=32_000, existing_emi=9_000, cibil_score=640, loan_amount=3_00_000,
        tenure_months=36, purpose="Travel", dpd_12m=DPD_OPTIONS[1], enquiries_6m=5),
    "Farhan Qureshi - first job, no credit history": Applicant(
        name="Farhan Qureshi", age=23, employment_type="Salaried", years_in_job=1.5,
        monthly_income=42_000, existing_emi=0, cibil_score=None, loan_amount=1_50_000,
        tenure_months=24, purpose="Education", dpd_12m=DPD_OPTIONS[0], enquiries_6m=1),
    "Meera Iyer - senior manager close to retirement": Applicant(
        name="Meera Iyer", age=57, employment_type="Salaried", years_in_job=20,
        monthly_income=1_40_000, existing_emi=0, cibil_score=810, loan_amount=8_00_000,
        tenure_months=60, purpose="Medical", dpd_12m=DPD_OPTIONS[0], enquiries_6m=0),
    "Suresh Patil - already carrying heavy EMIs": Applicant(
        name="Suresh Patil", age=45, employment_type="Salaried", years_in_job=12,
        monthly_income=60_000, existing_emi=26_000, cibil_score=731, loan_amount=6_00_000,
        tenure_months=36, purpose="Debt consolidation", dpd_12m=DPD_OPTIONS[0], enquiries_6m=2),
    "Kavya Reddy - many recent loan applications": Applicant(
        name="Kavya Reddy", age=31, employment_type="Self-employed", years_in_job=3,
        monthly_income=75_000, existing_emi=5_000, cibil_score=768, loan_amount=3_00_000,
        tenure_months=24, purpose="Consumer durables", dpd_12m=DPD_OPTIONS[0], enquiries_6m=7),
}

FIRST = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Rohan", "Karan", "Arjun", "Nikhil", "Sanjay",
         "Deepak", "Ananya", "Diya", "Sneha", "Pooja", "Neha", "Ritu", "Kavita", "Shreya",
         "Lakshmi", "Fatima", "Imran", "Gurpreet", "Joseph", "Mary", "Tenzin"]
LAST = ["Sharma", "Gupta", "Nair", "Menon", "Rao", "Das", "Bose", "Khan", "Singh", "Joshi",
        "Kulkarni", "Pillai", "Chatterjee", "Mehta", "Shah", "Fernandes", "Ahmed", "Kaur"]


def synthetic_batch(n=40, seed=7):
    """Random but realistic-looking applicant book for batch screening."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        emp = rng.choices(["Salaried", "Self-employed"], [0.7, 0.3])[0]
        age = rng.randint(22, 58)
        yrs = round(min(age - 21, rng.choice([0.5, 1, 1.5, 2, 3, 4, 6, 8, 10, 15])), 1)
        inc = rng.choice([28, 35, 42, 50, 60, 75, 90, 1_10, 1_40, 1_80]) * 1000
        emi_ = round(inc * rng.choice([0, 0, 0, 0.1, 0.1, 0.15, 0.2, 0.3, 0.4]), -2)
        cib = None if rng.random() < 0.08 else int(min(880, max(600, rng.gauss(735, 50))))
        loan = max(50_000, min(40_00_000, round(inc * rng.choice([2, 3, 4, 5, 6, 8, 10, 12, 15, 20]), -4)))
        ten = rng.choice([12, 24, 36, 48, 60])
        dpd = rng.choices(DPD_OPTIONS, [0.72, 0.16, 0.08, 0.04])[0]
        rows.append(dict(
            name=f"{rng.choice(FIRST)} {rng.choice(LAST)}", age=age, employment_type=emp,
            years_in_job=yrs, monthly_income=inc, existing_emi=emi_,
            cibil_score="NTC" if cib is None else cib, loan_amount=int(loan), tenure_months=ten,
            purpose=rng.choice(PURPOSES), dpd_12m=dpd, enquiries_6m=rng.choice([0, 1, 1, 2, 2, 3, 4, 6, 8])))
    # two deliberately bad rows to show batch validation
    rows.append(dict(name="Test Row - typo in income", age=35, employment_type="Salaried",
                     years_in_job=5, monthly_income=9_00_00_000, existing_emi=0, cibil_score=760,
                     loan_amount=5_00_000, tenure_months=36, purpose="Travel", dpd_12m=DPD_OPTIONS[0],
                     enquiries_6m=1))
    rows.append(dict(name="Test Row - impossible experience", age=24, employment_type="Salaried",
                     years_in_job=12, monthly_income=50_000, existing_emi=0, cibil_score=720,
                     loan_amount=2_00_000, tenure_months=24, purpose="Other", dpd_12m=DPD_OPTIONS[0],
                     enquiries_6m=0))
    return rows
