import React from "react";
import { PlanResult } from "../../lib/types";
import { formatPaiseToRupees } from "../../lib/money";

interface FinalPlanCardProps {
  plan: PlanResult | null;
}

export const FinalPlanCard: React.FC<FinalPlanCardProps> = ({ plan }) => {
  if (!plan) {
    return (
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg backdrop-blur-sm">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-2">
          30-Day Plan Ledger
        </h3>
        <p className="text-slate-500 text-sm italic">
          Plan not yet finalized. Provide your income and obligations to generate a 30-day plan.
        </p>
      </div>
    );
  }

  const getStatusBadge = () => {
    switch (plan.status) {
      case "surplus":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Balanced / Surplus
          </span>
        );
      case "solved_with_cuts":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            Solved with Proposed Cuts
          </span>
        );
      case "unsolvable":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
            Unsolvable Shortfall
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg backdrop-blur-sm space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
            30-Day Plan Ledger
          </h3>
          <p className="text-xs text-slate-500">Day-by-day cash flow simulation</p>
        </div>
        {getStatusBadge()}
      </div>

      <div className="flex items-baseline justify-between pt-2 border-t border-slate-800/60">
        <span className="text-xs text-slate-400">Projected 30-Day Final Balance:</span>
        <span
          className={`text-lg font-bold ${
            plan.final_balance_paise >= 0 ? "text-emerald-400" : "text-rose-400"
          }`}
        >
          {formatPaiseToRupees(plan.final_balance_paise)}
        </span>
      </div>

      {/* Missed Obligations Alert */}
      {plan.missed_obligations.length > 0 && (
        <div className="bg-rose-950/40 border border-rose-900/50 rounded-lg p-3 space-y-2">
          <span className="text-xs font-semibold text-rose-400 uppercase tracking-wide">
            Missed Obligations ({plan.missed_obligations.length}):
          </span>
          <ul className="space-y-1.5 text-xs text-rose-300">
            {plan.missed_obligations.map((m) => (
              <li key={m.entry_id} className="flex justify-between items-center">
                <span>
                  <strong>{m.name}</strong> (Due {m.due_date})
                </span>
                <span className="font-semibold text-rose-400">
                  Shortfall: {formatPaiseToRupees(m.shortfall_paise)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Ledger Trail */}
      {plan.ledger && plan.ledger.length > 0 && (
        <div className="space-y-2 pt-2">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
            Calculation Trail:
          </span>
          <div className="max-h-40 overflow-y-auto pr-1 space-y-1 text-xs text-slate-300 font-mono divide-y divide-slate-800/40">
            {plan.ledger.map((entry, idx) => (
              <div key={idx} className="flex justify-between py-1 px-1 hover:bg-slate-800/30 rounded">
                <span className="text-slate-400">Day +{entry.day_offset}</span>
                <span className={entry.balance_paise >= 0 ? "text-slate-200" : "text-rose-400"}>
                  {formatPaiseToRupees(entry.balance_paise)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
