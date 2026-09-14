import React from "react";
import type { Entry } from "@/lib/types";
import { paiseToRupeesDisplay } from "@/lib/money";

interface OptionalExpensesCardProps {
  optionalExpenses: Entry[];
}

export function OptionalExpensesCard({ optionalExpenses }: OptionalExpensesCardProps) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/90 p-4 sm:p-5 shadow-lg backdrop-blur-sm">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="flex h-2 w-2 rounded-full bg-amber-400 flex-shrink-0" />
          <h3 className="text-sm sm:text-base font-semibold text-zinc-100 truncate">Optional / Discretionary Expenses</h3>
        </div>
        <span className="rounded-md bg-zinc-800 px-2 py-0.5 text-xs font-medium text-zinc-400 flex-shrink-0 ml-2">
          {optionalExpenses.length} {optionalExpenses.length === 1 ? "item" : "items"}
        </span>
      </div>

      {optionalExpenses.length === 0 ? (
        <p className="mt-4 text-xs sm:text-sm text-zinc-500 italic">No optional expenses recorded.</p>
      ) : (
        <div className="mt-3 space-y-2">
          {optionalExpenses.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-zinc-950/60 p-2.5 sm:p-3 text-zinc-100 transition-all"
            >
              <p className="text-xs sm:text-sm font-medium truncate min-w-0 flex-1">{item.name}</p>
              <span className="text-xs sm:text-sm font-semibold text-zinc-200 whitespace-nowrap">
                {paiseToRupeesDisplay(item.current.amount_paise)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
