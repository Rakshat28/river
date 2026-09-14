import React from "react";
import { PlanResult } from "@/lib/types";
import { formatPaiseToRupees } from "@/lib/money";

interface FinalPlanCardProps {
  plan: PlanResult | null;
}

export const FinalPlanCard: React.FC<FinalPlanCardProps> = ({ plan }) => {
  if (!plan) {
    return (
      <div className="bg-zinc-950 border-2 border-zinc-800 rounded-lg p-5 font-mono text-zinc-100 shadow-2xl">
        <h3 className="text-xs uppercase tracking-widest text-zinc-400 font-bold mb-2">
          [ 30-DAY FINANCIAL PLAN ]
        </h3>
        <p className="text-zinc-500 text-xs italic">
          Waiting for income and expense details to build your 30-day plan.
        </p>
      </div>
    );
  }

  const getStatusBadge = () => {
    switch (plan.status) {
      case "surplus":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider bg-emerald-950 text-emerald-400 border border-emerald-600">
            SURPLUS / BALANCED
          </span>
        );
      case "solved_with_cuts":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider bg-amber-950 text-amber-400 border border-amber-600">
            BALANCED WITH PROPOSED ADJUSTMENTS
          </span>
        );
      case "unsolvable":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider bg-rose-950 text-rose-400 border border-rose-600">
            UNSOLVED SHORTFALL
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="bg-zinc-950 border-2 border-zinc-700 rounded-lg p-4 sm:p-6 font-mono text-zinc-100 shadow-2xl space-y-4 sm:space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b-2 border-zinc-800 pb-3">
        <div>
          <h3 className="text-[11px] sm:text-xs uppercase tracking-widest font-bold text-zinc-300">
            [ 30-DAY FINANCIAL PLAN SUMMARY ]
          </h3>
          <p className="text-[10px] sm:text-[11px] text-zinc-500 mt-0.5">30-Day Cash Flow Plan</p>
        </div>
        {getStatusBadge()}
      </div>

      {/* Projected 30-Day Balance */}
      <div className="flex flex-wrap items-baseline justify-between gap-1 py-2 border-b border-zinc-800">
        <span className="text-[11px] sm:text-xs uppercase text-zinc-400 font-semibold">
          Projected Final Balance:
        </span>
        <span
          className={`text-lg sm:text-xl font-bold tracking-tight ${
            plan.final_balance_paise >= 0 ? "text-emerald-400" : "text-rose-400"
          }`}
        >
          {formatPaiseToRupees(plan.final_balance_paise)}
        </span>
      </div>

      {/* Proposed Cuts */}
      {plan.cuts && plan.cuts.length > 0 && (
        <div className="border border-amber-500/40 bg-amber-950/30 rounded p-3 space-y-2">
          <span className="text-[11px] sm:text-xs font-bold text-amber-400 uppercase tracking-wide block">
            [ PROPOSED BUDGET ADJUSTMENTS ({plan.cuts.length}) ]
          </span>
          <ul className="space-y-1 text-xs text-amber-200">
            {plan.cuts.map((cut) => (
              <li key={cut.id} className="flex justify-between items-center gap-2 border-b border-amber-900/40 pb-1">
                <span className="truncate min-w-0 flex-1">{cut.name}</span>
                <span className="font-bold text-amber-300 flex-shrink-0">
                  {formatPaiseToRupees(cut.current.amount_paise)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Missed Obligations Alert */}
      {plan.missed_obligations && plan.missed_obligations.length > 0 && (
        <div className="border-2 border-rose-600/60 bg-rose-950/40 rounded p-3 space-y-2">
          <span className="text-[11px] sm:text-xs font-bold text-rose-400 uppercase tracking-wide block">
            [ UNPAID OBLIGATIONS ({plan.missed_obligations.length}) ]
          </span>
          <ul className="space-y-1.5 text-xs text-rose-300 divide-y divide-rose-900/40">
            {plan.missed_obligations.map((m) => (
              <li key={m.entry_id} className="flex flex-wrap justify-between items-center gap-1 pt-1">
                <span>
                  <strong>{m.name}</strong> (Due {m.due_date})
                </span>
                <span className="font-bold text-rose-400">
                  Shortfall: {formatPaiseToRupees(m.shortfall_paise)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Mathematical Strategy Insights Section */}
      {plan.insights && plan.insights.length > 0 && (
        <div className="border border-indigo-500/40 bg-zinc-900/80 rounded p-3 sm:p-4 space-y-2.5 sm:space-y-3">
          <span className="text-[11px] sm:text-xs font-bold text-indigo-400 uppercase tracking-wider block">
            [ FINANCIAL STRATEGY & INSIGHTS ]
          </span>
          <ul className="space-y-2 text-[11px] sm:text-xs text-zinc-300">
            {plan.insights.map((insight, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-indigo-400 font-bold select-none">&gt;</span>
                <span className="leading-relaxed">{insight}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Categorized Summary */}
      <div className="space-y-4 pt-2">
        <span className="text-[10px] sm:text-[11px] font-bold text-zinc-500 uppercase tracking-wider block border-b border-zinc-800 pb-2">
          [ BUDGET BREAKDOWN ]
        </span>
        
        {/* Income */}
        {plan.income && plan.income.length > 0 && (
          <div className="space-y-1">
            <span className="text-[10px] uppercase font-bold text-emerald-500/80 tracking-widest">Streams of Income</span>
            <ul className="text-xs text-zinc-300 divide-y divide-zinc-800/50">
              {plan.income.map(item => (
                <li key={item.id} className="flex justify-between py-1">
                  <span>{item.name}</span>
                  <span className="text-emerald-400 font-medium">+{formatPaiseToRupees(item.current.amount_paise)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Essential Expenses */}
        {plan.essential_expenses && plan.essential_expenses.length > 0 && (
          <div className="space-y-1">
            <span className="text-[10px] uppercase font-bold text-blue-500/80 tracking-widest">Essential Expenses</span>
            <ul className="text-xs text-zinc-300 divide-y divide-zinc-800/50">
              {plan.essential_expenses.map(item => (
                <li key={item.id} className="flex justify-between py-1">
                  <span>{item.name}</span>
                  <span className="text-zinc-400 font-medium">-{formatPaiseToRupees(item.current.amount_paise)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Debts / Loans */}
        {plan.debts && plan.debts.length > 0 && (
          <div className="space-y-1">
            <span className="text-[10px] uppercase font-bold text-amber-500/80 tracking-widest">Loans & EMIs</span>
            <ul className="text-xs text-zinc-300 divide-y divide-zinc-800/50">
              {plan.debts.map(item => (
                <li key={item.id} className="flex justify-between py-1">
                  <span>{item.name}</span>
                  <span className="text-zinc-400 font-medium">-{formatPaiseToRupees(item.min_payment_paise)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Optional Expenses */}
        {plan.optional_expenses && plan.optional_expenses.length > 0 && (
          <div className="space-y-1">
            <span className="text-[10px] uppercase font-bold text-purple-500/80 tracking-widest">Optional Expenses</span>
            <ul className="text-xs text-zinc-300 divide-y divide-zinc-800/50">
              {plan.optional_expenses.map(item => (
                <li key={item.id} className="flex justify-between py-1">
                  <span>{item.name}</span>
                  <span className="text-zinc-400 font-medium">-{formatPaiseToRupees(item.current.amount_paise)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Hardcoded Mandatory Disclaimer */}
      {plan.disclaimer && (
        <div className="border-t-2 border-zinc-800 pt-3 mt-4 text-[9px] sm:text-[10px] text-zinc-500 leading-relaxed italic">
          <strong>DISCLAIMER:</strong> {plan.disclaimer}
        </div>
      )}
    </div>
  );
};
