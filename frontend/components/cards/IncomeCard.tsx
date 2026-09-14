import React from "react";
import type { Entry } from "@/lib/types";
import { paiseToRupeesDisplay } from "@/lib/money";

interface IncomeCardProps {
  income: Entry[];
}

export function IncomeCard({ income }: IncomeCardProps) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/90 p-5 shadow-lg backdrop-blur-sm">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 rounded-full bg-emerald-400" />
          <h3 className="text-base font-semibold text-zinc-100">Income Sources</h3>
        </div>
        <span className="rounded-md bg-zinc-800 px-2 py-0.5 text-xs font-medium text-zinc-400">
          {income.length} {income.length === 1 ? "source" : "sources"}
        </span>
      </div>

      {income.length === 0 ? (
        <p className="mt-4 text-sm text-zinc-500 italic">No income entries recorded yet.</p>
      ) : (
        <div className="mt-3 space-y-2">
          {income.map((item) => {
            const isEstimated = item.current.confidence === "estimated";
            return (
              <div
                key={item.id}
                className={`flex items-center justify-between rounded-lg p-3 transition-all ${
                  isEstimated
                    ? "border border-dashed border-amber-500/50 bg-amber-950/20 text-zinc-300"
                    : "border border-zinc-800 bg-zinc-950/60 text-zinc-100"
                }`}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium">{item.name}</p>
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <span
                      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                        isEstimated
                          ? "bg-amber-950/90 text-amber-300 border border-amber-700/60"
                          : "bg-emerald-950/90 text-emerald-300 border border-emerald-700/60"
                      }`}
                    >
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${
                          isEstimated ? "bg-amber-400 animate-pulse" : "bg-emerald-400"
                        }`}
                      />
                      {isEstimated ? "Estimated (Unconfirmed)" : "Confirmed"}
                    </span>
                  </div>
                </div>
                <span
                  className={`text-sm font-semibold ${
                    isEstimated ? "text-amber-400 italic" : "text-emerald-400"
                  }`}
                >
                  {paiseToRupeesDisplay(item.current.amount_paise)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
