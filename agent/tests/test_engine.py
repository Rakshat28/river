"""Unit tests for agent/app/engine.py functions and 30-day plan simulation fixtures."""

from datetime import date, datetime, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from agent.app.engine import (
        SessionState,
        build_plan,
        calculate_emi_paise,
        compute_blocking_issues,
        compute_cash_position,
        compute_missing_fields,
    )
    from agent.app.state import Debt, Entry, FieldHistory, Recurrence
except ImportError:
    from app.engine import (
        SessionState,
        build_plan,
        calculate_emi_paise,
        compute_blocking_issues,
        compute_cash_position,
        compute_missing_fields,
    )
    from app.state import Debt, Entry, FieldHistory, Recurrence


def _make_state(today: date = date(2026, 9, 14)) -> SessionState:
    return SessionState(
        room_name="test-engine-room",
        today=today,
        updated_at=datetime.now(timezone.utc),
    )


def _make_entry(
    name: str, amount_paise: int, day_of_month: int, confidence: str = "confirmed"
) -> Entry:
    return Entry(
        name=name,
        current=FieldHistory(
            amount_paise=amount_paise,
            confidence=confidence,  # type: ignore
            turn_index=1,
            timestamp=datetime.now(timezone.utc),
        ),
        recurrence=Recurrence(
            unit="month", interval=1, count=1, day_of_month=day_of_month
        ),
    )


def _make_debt(
    name: str,
    min_payment_paise: int,
    due_date: date,
    kind: str = "vehicle_loan",
    confidence: str = "confirmed",
) -> Debt:
    return Debt(
        name=name,
        kind=kind,  # type: ignore
        due_date=due_date,
        min_payment_paise=min_payment_paise,
        current=FieldHistory(
            amount_paise=min_payment_paise,
            confidence=confidence,  # type: ignore
            turn_index=1,
            timestamp=datetime.now(timezone.utc),
        ),
        recurrence=Recurrence(
            unit="month", interval=1, count=1, day_of_month=due_date.day
        ),
    )


class TestEngineCalculations:
    def test_compute_cash_position_surplus(self):
        state = _make_state()
        history_inc = FieldHistory(
            amount_paise=5000000,
            confidence="confirmed",
            turn_index=1,
            timestamp=datetime.now(timezone.utc),
        )
        history_exp = FieldHistory(
            amount_paise=2000000,
            confidence="confirmed",
            turn_index=1,
            timestamp=datetime.now(timezone.utc),
        )
        state.income.append(Entry(name="Salary", current=history_inc))
        state.essential_expenses.append(Entry(name="Rent", current=history_exp))

        assert compute_cash_position(state) == 3000000

    def test_compute_cash_position_exact_break_even(self):
        state = _make_state()
        history = FieldHistory(
            amount_paise=5000000,
            confidence="confirmed",
            turn_index=1,
            timestamp=datetime.now(timezone.utc),
        )
        state.income.append(Entry(name="Salary", current=history))
        state.essential_expenses.append(Entry(name="Rent", current=history))

        assert compute_cash_position(state) == 0

    def test_compute_cash_position_shortfall(self):
        state = _make_state()
        history_inc = FieldHistory(
            amount_paise=2000000,
            confidence="confirmed",
            turn_index=1,
            timestamp=datetime.now(timezone.utc),
        )
        history_exp = FieldHistory(
            amount_paise=5000000,
            confidence="confirmed",
            turn_index=1,
            timestamp=datetime.now(timezone.utc),
        )
        state.income.append(Entry(name="Salary", current=history_inc))
        state.essential_expenses.append(Entry(name="Rent", current=history_exp))

        assert compute_cash_position(state) == -3000000

    def test_compute_cash_position_zero_or_missing_income(self):
        state = _make_state()
        history_exp = FieldHistory(
            amount_paise=2000000,
            confidence="confirmed",
            turn_index=1,
            timestamp=datetime.now(timezone.utc),
        )
        state.essential_expenses.append(Entry(name="Rent", current=history_exp))

        assert compute_cash_position(state) == -2000000

    def test_compute_missing_fields_and_blocking_issues(self):
        state = _make_state()
        assert compute_missing_fields(state) == ["income", "obligations"]
        assert compute_blocking_issues(state) == ["income", "obligations"]


class TestBuildPlanFixtures:
    """Phase 7 Worked Fixtures (Step 7.1)."""

    def test_fixture_a_clean_surplus(self):
        """Fixture A: Clean surplus, no missed obligations, final balance 1,350,000 paise."""
        state = _make_state(today=date(2026, 9, 14))
        # Income: salary ₹50,000 on day 0 (2026-09-14)
        state.income.append(_make_entry("Salary", 5000000, 14))
        # Essential: rent ₹15,000 on day 4 (2026-09-18), groceries ₹6,000 on day 10 (2026-09-24)
        state.essential_expenses.append(_make_entry("Rent", 1500000, 18))
        state.essential_expenses.append(_make_entry("Groceries", 600000, 24))
        # Optional: OTT ₹500 on day 5 (2026-09-19), dining ₹4,000 on day 12 (2026-09-26)
        state.optional_expenses.append(_make_entry("OTT", 50000, 19))
        state.optional_expenses.append(_make_entry("Dining", 400000, 26))
        # Debts: loan EMI ₹8,000 on day 15 (2026-09-29), credit card min ₹3,000 on day 20 (2026-10-04)
        state.debts.append(
            _make_debt("Loan EMI", 800000, date(2026, 9, 29), kind="vehicle_loan")
        )
        state.debts.append(
            _make_debt("Credit Card Min", 300000, date(2026, 10, 4), kind="credit_card")
        )

        plan = build_plan(state)
        assert plan.status == "surplus"
        assert plan.missed_obligations == []
        assert plan.final_balance_paise == 1350000
        assert plan.cuts == []

    def test_fixture_b_exact_break_even(self):
        """Fixture B: Exact break-even. Balance after rent = 0 exactly. Status is surplus (< 0 vs <= 0 check)."""
        state = _make_state(today=date(2026, 9, 14))
        # Income: ₹10,000 on day 0
        state.income.append(_make_entry("Salary", 1000000, 14))
        # Essential: rent ₹10,000 on day 0
        state.essential_expenses.append(_make_entry("Rent", 1000000, 14))

        plan = build_plan(state)
        assert plan.status == "surplus"
        assert plan.missed_obligations == []
        assert plan.final_balance_paise == 0

    def test_fixture_c_shortfall_resolved_by_cuts(self):
        """Fixture C: Shortfall resolved entirely by cutting OTT (₹500) and Dining (₹4,000)."""
        state = _make_state(today=date(2026, 9, 14))
        # Income: ₹30,000 on day 0
        state.income.append(_make_entry("Salary", 3000000, 14))
        # Essential: rent ₹15,000 on day 4, groceries ₹6,000 on day 10
        state.essential_expenses.append(_make_entry("Rent", 1500000, 18))
        state.essential_expenses.append(_make_entry("Groceries", 600000, 24))
        # Optional: OTT ₹500 on day 5, dining ₹4,000 on day 12
        state.optional_expenses.append(_make_entry("OTT", 50000, 19))
        state.optional_expenses.append(_make_entry("Dining", 400000, 26))
        # Debts: loan EMI ₹8,000 on day 15, credit card min ₹1,000 on day 20
        state.debts.append(
            _make_debt("Loan EMI", 800000, date(2026, 9, 29), kind="vehicle_loan")
        )
        state.debts.append(
            _make_debt("Credit Card Min", 100000, date(2026, 10, 4), kind="credit_card")
        )

        plan = build_plan(state)
        assert plan.status == "solved_with_cuts"
        assert len(plan.cuts) == 2
        assert plan.missed_obligations == []
        assert plan.final_balance_paise == 0

    def test_fixture_d_unsolvable_balance_ends_at_zero(self):
        """Fixture D: Unsolvable (loan EMI missed on day 15). Final balance = 0."""
        state = _make_state(today=date(2026, 9, 14))
        # Income: ₹20,000 on day 0
        state.income.append(_make_entry("Salary", 2000000, 14))
        # Essential: rent ₹15,000 on day 4
        state.essential_expenses.append(_make_entry("Rent", 1500000, 18))
        # Debts: loan EMI ₹8,000 on day 15, credit card min ₹5,000 on day 20
        state.debts.append(
            _make_debt("Loan EMI", 800000, date(2026, 9, 29), kind="vehicle_loan")
        )
        state.debts.append(
            _make_debt("Credit Card Min", 500000, date(2026, 10, 4), kind="credit_card")
        )

        plan = build_plan(state)
        assert plan.status == "unsolvable"
        assert len(plan.missed_obligations) == 2
        
        missed_loan = plan.missed_obligations[0]
        assert missed_loan.name == "Loan EMI"
        assert missed_loan.shortfall_paise == 300000  # 8,000 - 5,000 = 3,000 paise
        
        missed_cc = plan.missed_obligations[1]
        assert missed_cc.name == "Credit Card Min"
        assert missed_cc.shortfall_paise == 500000  # 5,000 - 0 = 5,000 paise
        
        assert plan.final_balance_paise == -800000

    def test_same_day_debt_collision_loan_vs_credit_card(self):
        """Test same-day collision between a loan EMI (rank 2) and credit card (rank 3).

        Even if the credit card is added to state.debts FIRST, the priority rank (secured loan=2 < credit card=3)
        ensures the loan EMI is paid first, and the credit card is recorded as missed.
        """
        state = _make_state(today=date(2026, 9, 14))
        # Income: ₹10,000 on day 0
        state.income.append(_make_entry("Salary", 1000000, 14))
        # Debts due on the exact same day (2026-09-20)
        # Add Credit Card FIRST to ensure list order doesn't cause false positive
        state.debts.append(
            _make_debt("Credit Card Min", 600000, date(2026, 9, 20), kind="credit_card")
        )
        state.debts.append(
            _make_debt(
                "Vehicle Loan EMI", 600000, date(2026, 9, 20), kind="vehicle_loan"
            )
        )

        plan = build_plan(state)
        assert plan.status == "unsolvable"
        assert len(plan.missed_obligations) == 1
        missed = plan.missed_obligations[0]
        assert missed.name == "Credit Card Min"
        assert missed.due_date == date(2026, 9, 20)
        assert missed.shortfall_paise == 200000  # 6,000 - 4,000 = 2,000 shortfall
        assert (
            plan.final_balance_paise == -200000
        )  # 10,000 - 6,000 (vehicle loan) - 6,000 (credit card) = -2,000 deficit


class TestEngineEdgeCases:
    """Step 7.6 Edge-case tests beyond the 4 core fixtures."""

    def test_zero_income_entries(self):
        """Edge case 1: Zero income entries. Balance starts and stays 0; essential expense missed immediately."""
        state = _make_state(today=date(2026, 9, 14))
        # Zero income entries
        state.essential_expenses.append(_make_entry("Rent", 1000000, 14))

        plan = build_plan(state)
        assert plan.status == "unsolvable"
        assert len(plan.missed_obligations) == 1
        missed = plan.missed_obligations[0]
        assert missed.name == "Rent"
        assert missed.shortfall_paise == 1000000
        assert plan.final_balance_paise == -1000000

    def test_same_day_income_expense_debt(self):
        """Edge case 2: Income, essential expense, and debt due on day 0. Income applied first."""
        state = _make_state(today=date(2026, 9, 14))
        state.income.append(_make_entry("Salary", 2000000, 14))  # ₹20,000
        state.essential_expenses.append(_make_entry("Rent", 1500000, 14))  # ₹15,000
        state.debts.append(
            _make_debt("Vehicle Loan", 500000, date(2026, 9, 14), kind="vehicle_loan")
        )  # ₹5,000

        plan = build_plan(state)
        assert plan.status == "surplus"
        assert plan.missed_obligations == []
        assert plan.final_balance_paise == 0  # 20,000 - 15,000 - 5,000 = 0

    def test_equal_amount_optional_expense_cut_tie_break(self):
        """Edge case 3: Two optional expenses with exact same amount. Tie-break by entry id ascending."""
        state = _make_state(today=date(2026, 9, 14))
        state.income.append(_make_entry("Salary", 2000000, 14))  # ₹20,000
        state.essential_expenses.append(_make_entry("Rent", 1600000, 14))  # ₹16,000

        # Two optionals with same amount (₹3,000 each = 300,000 paise). Shortfall is ₹2,000 (200,000 paise). Cutting 1 is enough.
        e1 = _make_entry("Gym", 300000, 14)
        e1.id = "entry_b"
        e2 = _make_entry("Sub", 300000, 14)
        e2.id = "entry_a"
        state.optional_expenses.extend([e1, e2])

        plan = build_plan(state)
        assert plan.status == "solved_with_cuts"
        assert len(plan.cuts) == 1
        # entry_a ("Sub") should be cut first because "entry_a" < "entry_b"
        assert plan.cuts[0].id == "entry_a"
        assert plan.cuts[0].name == "Sub"

    def test_exact_balance_boundary_paid_in_full(self):
        """Edge case 4: Entry amount_paise exactly equals remaining balance (affordability boundary check)."""
        state = _make_state(today=date(2026, 9, 14))
        state.income.append(_make_entry("Salary", 1000000, 14))  # ₹10,000
        state.essential_expenses.append(_make_entry("Rent", 1000000, 14))  # ₹10,000

        plan = build_plan(state)
        assert plan.status == "surplus"
        assert plan.missed_obligations == []
        assert plan.final_balance_paise == 0
        # Explicitly confirm the entry is NOT in missed_obligations
        missed_ids = [m.entry_id for m in plan.missed_obligations]
        assert state.essential_expenses[0].id not in missed_ids

    def test_step_8_5_financial_insights_and_disclaimer(self):
        """Step 8.5 test: Verify deterministic insights for high interest credit card + unsolvable deficit & verbatim disclaimer."""
        state = _make_state(today=date(2026, 9, 14))
        # Income: ₹10,000 on day 0
        state.income.append(_make_entry("Salary", 1000000, 14))
        # Essential: rent ₹15,000 on day 4 (causes unsolvable deficit of ₹5,000)
        state.essential_expenses.append(_make_entry("Rent", 1500000, 18))
        # Debt: Credit Card with 24% APR (2400 bps)
        debt = _make_debt(
            "HDFC Credit Card", 200000, date(2026, 9, 25), kind="credit_card"
        )
        debt.interest_rate_bps = 2400
        state.debts.append(debt)

        plan = build_plan(state)

        assert plan.status == "unsolvable"
        assert plan.disclaimer == (
            "Please note: This assistant is an AI tool, not a SEBI-registered or government-certified financial advisor. "
            "These insights are mathematical projections, not professional financial advice."
        )

        # Assert plan.insights contains both consolidation & tenure extension strings
        consolidation_found = any("consolidate" in insight for insight in plan.insights)
        tenure_extension_found = any(
            "tenure extension" in insight for insight in plan.insights
        )

        assert (
            consolidation_found
        ), "High-interest debt consolidation insight expected in plan.insights"
        assert (
            tenure_extension_found
        ), "Unsolvable deficit tenure extension insight expected in plan.insights"


class TestCalculateEmiPaise:
    """Unit tests for the reducing-balance EMI calculator.

    These tests are the sole authoritative verification that the EMI formula
    is correct — no other module may re-implement EMI arithmetic.
    """

    def test_standard_home_loan(self):
        """₹30L at 8.5% p.a. for 240 months → approx ₹26,035/month."""
        emi = calculate_emi_paise(
            balance_paise=3_000_000 * 100,  # ₹30,00,000 = 3_000_000 rupees = 300_000_000 paise
            annual_rate_bps=850,             # 8.5%
            duration_months=240,
        )
        # Expected: ~₹26,035. Accepted tolerance: ±100 rupees (rounding)
        assert 2_600_000 <= emi <= 2_610_000, f"Expected ~₹26,035; got ₹{emi // 100}"

    def test_personal_loan(self):
        """₹1L at 12% p.a. for 12 months → approx ₹8,885/month."""
        emi = calculate_emi_paise(
            balance_paise=100_000 * 100,  # ₹1,00,000 = 100_000 rupees = 10_000_000 paise
            annual_rate_bps=1200,
            duration_months=12,
        )
        assert 885_000 <= emi <= 890_000, f"Expected ~₹8,885; got ₹{emi // 100}"

    def test_zero_interest_loan(self):
        """₹12,000 at 0% for 12 months → exactly ₹1,000/month."""
        emi = calculate_emi_paise(
            balance_paise=1_200_000,  # ₹12,000 in paise
            annual_rate_bps=0,
            duration_months=12,
        )
        assert emi == 100_000, f"Expected ₹1,000; got ₹{emi // 100}"

    def test_single_month_loan(self):
        """A 1-month loan is always equal to the full principal (plus 1 month interest)."""
        emi = calculate_emi_paise(
            balance_paise=500_000,  # ₹5,000
            annual_rate_bps=1200,   # 12% p.a. → 1% per month
            duration_months=1,
        )
        # EMI = 5000 * 0.01 * 1.01 / (1.01 - 1) = 5000 * 1.01 = 5050
        assert 504_000 <= emi <= 506_000, f"Expected ~₹5,050; got ₹{emi // 100}"

    def test_invalid_duration_raises(self):
        """duration_months=0 must raise ValueError."""
        import pytest
        with pytest.raises(ValueError, match="duration_months"):
            calculate_emi_paise(balance_paise=100_000, annual_rate_bps=1200, duration_months=0)

    def test_invalid_balance_raises(self):
        """balance_paise=0 must raise ValueError."""
        import pytest
        with pytest.raises(ValueError, match="balance_paise"):
            calculate_emi_paise(balance_paise=0, annual_rate_bps=1200, duration_months=12)

