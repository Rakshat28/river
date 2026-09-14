import React from "react";
import { PlanResult } from "../../lib/types";
import { formatPaiseToRupees } from "../../lib/money";

interface ProposedActionsCardProps {
  plan: PlanResult | null;
}

export const ProposedActionsCard: React.FC<ProposedActionsCardProps> = ({ plan }) => {
  const cuts = plan?.cuts || [];

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg backdrop-blur-sm space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          Proposed Action Cuts
        </h3>
        <span className="text-xs text-slate-500">{cuts.length} Recommended</span>
      </div>

      {cuts.length === 0 ? (
        <p className="text-slate-500 text-sm italic">
          No expense cuts recommended. All obligations are covered or no optional expenses exist.
        </p>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-slate-400">
            Cutting the following optional expenses is recommended to balance your 30-day plan:
          </p>
          <ul className="space-y-2">
            {cuts.map((entry) => (
              <li
                key={entry.id}
                className="flex justify-between items-center bg-amber-950/30 border border-amber-900/40 rounded-lg p-3 text-xs"
              >
                <div>
                  <div className="font-semibold text-amber-300">{entry.name}</div>
                  <div className="text-slate-500 text-[10px]">Optional Expense</div>
                </div>
                <div className="text-right">
                  <div className="font-mono font-bold text-amber-400">
                    -{formatPaiseToRupees(entry.current.amount_paise)}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
