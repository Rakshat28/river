"use client";

import React from "react";
import type { SessionState } from "@/lib/types";
import { CashPositionCard } from "./cards/CashPositionCard";
import { ShortfallSurplusCard } from "./cards/ShortfallSurplusCard";
import { IncomeCard } from "./cards/IncomeCard";
import { EssentialExpensesCard } from "./cards/EssentialExpensesCard";
import { OptionalExpensesCard } from "./cards/OptionalExpensesCard";
import { DebtsCard } from "./cards/DebtsCard";
import { MissingInformationCard } from "./cards/MissingInformationCard";
import { FinalPlanCard } from "./cards/FinalPlanCard";
import { ConflictCard } from "./cards/ConflictCard";
import { DuplicateCard } from "./cards/DuplicateCard";

interface FullSummaryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  state: SessionState | null;
}

export function FullSummaryDrawer({ isOpen, onClose, state }: FullSummaryDrawerProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-md transition-opacity duration-300">
      <div className="relative w-full max-w-2xl bg-zinc-950 border-l border-zinc-800 h-full flex flex-col shadow-2xl overflow-hidden animate-in slide-in-from-right duration-300">
        {/* Drawer Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 p-4 sm:p-5 bg-zinc-900/50">
          <div>
            <h2 className="text-base sm:text-lg font-bold text-zinc-100">Complete Financial Summary</h2>
            <p className="text-[11px] sm:text-xs text-zinc-400">
              Overview of all recorded income, obligations, and plan calculations.
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg border border-zinc-800 p-2 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 transition-colors flex-shrink-0 ml-2"
            aria-label="Close summary drawer"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Drawer Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 sm:space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
            <CashPositionCard cashPositionPaise={state?.cash_position_paise ?? 0} />
            <ShortfallSurplusCard cashPositionPaise={state?.cash_position_paise ?? 0} />
          </div>

          {state?.conflicts && state.conflicts.some((c) => !c.resolved) && (
            <ConflictCard conflicts={state.conflicts} state={state} />
          )}

          <DuplicateCard state={state} />

          <MissingInformationCard missingFields={state?.missing_fields ?? []} />

          <IncomeCard income={state?.income ?? []} />

          <EssentialExpensesCard essentialExpenses={state?.essential_expenses ?? []} />

          <OptionalExpensesCard optionalExpenses={state?.optional_expenses ?? []} />

          <DebtsCard debts={state?.debts ?? []} />

          <FinalPlanCard plan={state?.plan ?? null} />
        </div>
      </div>
    </div>
  );
}
