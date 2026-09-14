import React from "react";
import type { Debt } from "@/lib/types";
import { paiseToRupeesDisplay } from "@/lib/money";

interface DebtsCardProps {
  debts: Debt[];
}

export function DebtsCard({ debts }: DebtsCardProps) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/90 p-4 sm:p-5 shadow-lg backdrop-blur-sm">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 rounded-full bg-amber-400" />
          <h3 className="text-sm sm:text-base font-semibold text-zinc-100">Debts &amp; EMIs</h3>
        </div>
        <span className="rounded-md bg-zinc-800 px-2 py-0.5 text-xs font-medium text-zinc-400">
          {debts.length} {debts.length === 1 ? "debt" : "debts"}
        </span>
      </div>

      {debts.length === 0 ? (
        <p className="mt-4 text-xs sm:text-sm text-zinc-500 italic">No debts or loans recorded yet.</p>
      ) : (
        <div className="mt-3 space-y-2">
          {debts.map((item) => {
            const interestPct = item.interest_rate_bps != null
              ? (item.interest_rate_bps / 100).toFixed(1) + "% p.a."
              : null;
            return (
              <div
                key={item.id}
                className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-2.5 sm:p-3 text-zinc-100 transition-all"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <p className="text-xs sm:text-sm font-medium truncate">{item.name}</p>
                      <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[9px] sm:text-[10px] text-zinc-400 capitalize">
                        {item.kind.replace(/_/g, " ")}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] sm:text-[11px] text-zinc-400">
                      <span>Due: {item.due_date}</span>
                      {interestPct && <span>Rate: {interestPct}</span>}
                      {item.duration_months != null && (
                        <span>{item.duration_months} months remaining</span>
                      )}
                      {item.balance_paise != null && (
                        <span>Balance: {paiseToRupeesDisplay(item.balance_paise)}</span>
                      )}
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-[10px] text-zinc-400">Min Payment</p>
                    <p className="text-xs sm:text-sm font-semibold text-amber-300">
                      {paiseToRupeesDisplay(item.min_payment_paise)}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
