import React from "react";
import { renderToString } from "react-dom/server";
import { IncomeCard } from "./IncomeCard";
import { EssentialExpensesCard } from "./EssentialExpensesCard";
import { DebtsCard } from "./DebtsCard";
import { MissingInformationCard } from "./MissingInformationCard";
import { CashPositionCard } from "./CashPositionCard";
import { ShortfallSurplusCard } from "./ShortfallSurplusCard";
import type { SessionState, Entry, Debt } from "@/lib/types";

function assert(condition: boolean, message: string) {
  if (!condition) {
    console.error("Assertion failed:", message);
    process.exit(1);
  }
}

// Hand-crafted mock SessionState for Step 6.1, 6.2, 6.3 acceptance checks
const mockIncome: Entry[] = [
  {
    id: "entry_inc1",
    name: "Primary Salary",
    current: {
      amount_paise: 5000000,
      confidence: "confirmed",
      turn_index: 1,
      timestamp: "2026-09-14T12:00:00Z",
    },
    history: [],
    recurrence: "one_time",
    possible_duplicate: false,
    duplicate_of: null,
  },
];

const mockEssential: Entry[] = [
  {
    id: "entry_exp1",
    name: "House Rent",
    current: {
      amount_paise: 1500000,
      confidence: "confirmed",
      turn_index: 1,
      timestamp: "2026-09-14T12:00:00Z",
    },
    history: [],
    recurrence: "one_time",
    possible_duplicate: false,
    duplicate_of: null,
  },
];

const mockDebts: Debt[] = [
  {
    id: "entry_debt1",
    name: "HDFC Credit Card",
    kind: "credit_card",
    kind_label: null,
    due_date: "2026-09-25",
    min_payment_paise: 300000,
    balance_paise: 5000000,
    interest_rate_bps: null,
    is_secured: null,
    current: {
      amount_paise: 300000,
      confidence: "confirmed",
      turn_index: 1,
      timestamp: "2026-09-14T12:00:00Z",
    },
    history: [],
    recurrence: "one_time",
    possible_duplicate: false,
    duplicate_of: null,
  },
];

const mockState: SessionState = {
  room_name: "test-card-room",
  today: "2026-09-14",
  income: mockIncome,
  essential_expenses: mockEssential,
  optional_expenses: [],
  debts: mockDebts,
  conflicts: [],
  plan: null,
  turn_index: 1,
  state_version: 1,
  updated_at: "2026-09-14T12:00:00Z",
  cash_position_paise: 3500000,
  missing_fields: [],
  blocking_issues: [],
};

// 1. Test IncomeCard
const incomeHtml = renderToString(React.createElement(IncomeCard, { income: mockState.income }));
assert(incomeHtml.includes("Primary Salary"), "IncomeCard missing entry name");
assert(incomeHtml.includes("₹50,000"), "IncomeCard missing formatted amount");

// 2. Test EssentialExpensesCard
const expenseHtml = renderToString(React.createElement(EssentialExpensesCard, { essentialExpenses: mockState.essential_expenses }));
assert(expenseHtml.includes("House Rent"), "EssentialExpensesCard missing entry name");
assert(expenseHtml.includes("₹15,000"), "EssentialExpensesCard missing formatted amount");

// 3. Test DebtsCard
const debtHtml = renderToString(React.createElement(DebtsCard, { debts: mockState.debts }));
assert(debtHtml.includes("HDFC Credit Card"), "DebtsCard missing entry name");
assert(debtHtml.includes("₹3,000"), "DebtsCard missing formatted min payment");

// 4. Test MissingInformationCard (Step 6.2 acceptance check)
const missingHtml1 = renderToString(React.createElement(MissingInformationCard, { missingFields: ["income", "obligations"] }));
assert(missingHtml1.includes("2 missing"), "MissingInformationCard does not reflect missing count");

const missingHtml2 = renderToString(React.createElement(MissingInformationCard, { missingFields: mockState.missing_fields }));
assert(missingHtml2.includes("Complete"), "MissingInformationCard does not show complete status when items filled");

// 5. Test CashPositionCard & ShortfallSurplusCard (Step 6.3 acceptance check)
const cashHtml = renderToString(React.createElement(CashPositionCard, { cashPositionPaise: mockState.cash_position_paise }));
assert(cashHtml.includes("₹35,000"), "CashPositionCard missing formatted cash position");
assert(cashHtml.includes("text-emerald-400"), "CashPositionCard missing green surplus color class");

const shortfallHtml = renderToString(React.createElement(ShortfallSurplusCard, { cashPositionPaise: -1000000 }));
assert(shortfallHtml.includes("-₹10,000"), "ShortfallSurplusCard missing negative shortfall formatting");
assert(shortfallHtml.includes("text-rose-400"), "ShortfallSurplusCard missing red shortfall color class");

console.log("All frontend card component unit tests passed!");
