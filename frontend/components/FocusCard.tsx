"use client";

import React from "react";
import type { FocusTarget, SessionState } from "@/lib/types";
import { IncomeCard } from "./cards/IncomeCard";
import { EssentialExpensesCard } from "./cards/EssentialExpensesCard";
import { OptionalExpensesCard } from "./cards/OptionalExpensesCard";
import { DebtsCard } from "./cards/DebtsCard";
import { ConflictCard } from "./cards/ConflictCard";
import { DuplicateCard } from "./cards/DuplicateCard";
import { MissingInformationCard } from "./cards/MissingInformationCard";
import { FinalPlanCard } from "./cards/FinalPlanCard";

interface FocusCardProps {
  currentFocus: FocusTarget;
  state: SessionState | null;
}

export function FocusCard({ currentFocus, state }: FocusCardProps) {
  const renderCard = () => {
    switch (currentFocus) {
      case "income":
        return <IncomeCard income={state?.income ?? []} />;

      case "essential_expenses":
        return <EssentialExpensesCard essentialExpenses={state?.essential_expenses ?? []} />;

      case "optional_expenses":
        return <OptionalExpensesCard optionalExpenses={state?.optional_expenses ?? []} />;

      case "debts":
        return <DebtsCard debts={state?.debts ?? []} />;

      case "conflict":
        return <ConflictCard conflicts={state?.conflicts ?? []} state={state} />;

      case "duplicate":
        return <DuplicateCard state={state} />;

      case "plan":
        return <FinalPlanCard plan={state?.plan ?? null} />;

      case "idle":
        return null;

      case "missing_info":
      default:
        return <MissingInformationCard missingFields={state?.missing_fields ?? []} />;
    }
  };

  const card = renderCard();
  if (!card) return null;

  return (
    <div className="w-full max-w-xl mx-auto transition-all duration-500 transform animate-in fade-in zoom-in-95">
      {card}
    </div>
  );
}
