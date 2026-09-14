export type Confidence = "confirmed" | "estimated";
export type RecurrenceUnit = "day" | "week" | "month";
export type DebtKind =
  | "personal_loan"
  | "credit_card"
  | "education_loan"
  | "vehicle_loan"
  | "home_loan"
  | "gold_loan"
  | "bnpl"
  | "informal"
  | "other";

export interface Recurrence {
  unit: RecurrenceUnit;
  interval: number;
  count: number;
  day_of_month?: number | null;
  day_of_week?: number | null;
}

export interface FieldHistory {
  amount_paise: number;
  confidence: Confidence;
  turn_index: number;
  timestamp: string; // ISO date string
}

export interface Entry {
  id: string;
  name: string;
  current: FieldHistory;
  history: FieldHistory[];
  recurrence: "one_time" | Recurrence;
  possible_duplicate: boolean;
  duplicate_of: string | null;
}

export interface Debt extends Entry {
  kind: DebtKind;
  kind_label: string | null;
  due_date: string; // ISO date string
  min_payment_paise: number;
  balance_paise: number | null;
  interest_rate_bps: number | null;
  is_secured: boolean | null;
}

export interface Conflict {
  id: string;
  entry_id: string;
  field_name: string;
  old_amount_paise: number;
  new_amount_paise: number;
  resolved: boolean;
  created_at: string; // ISO date string
}

export interface MissedObligation {
  entry_id: string;
  name: string;
  due_date: string;
  required_paise: number;
  available_paise: number;
  shortfall_paise: number;
}

export interface LedgerEntry {
  day_offset: number;
  balance_paise: number;
}

export interface PlanResult {
  status: "surplus" | "solved_with_cuts" | "unsolvable";
  final_balance_paise: number;
  cuts: Entry[];
  missed_obligations: MissedObligation[];
  ledger: LedgerEntry[];
}

export interface SessionState {
  room_name: string;
  today: string; // ISO date string
  income: Entry[];
  essential_expenses: Entry[];
  optional_expenses: Entry[];
  debts: Debt[];
  conflicts: Conflict[];
  plan: PlanResult | null;
  turn_index: number;
  state_version: number;
  updated_at: string; // ISO date string
  cash_position_paise?: number;
  missing_fields?: string[];
  blocking_issues?: string[];
}