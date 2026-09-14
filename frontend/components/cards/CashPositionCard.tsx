import React from "react";
import { paiseToRupeesDisplay } from "@/lib/money";

interface CashPositionCardProps {
  cashPositionPaise?: number;
}

export function CashPositionCard({ cashPositionPaise = 0 }: CashPositionCardProps) {
  const isPositive = cashPositionPaise >= 0;

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/90 p-5 shadow-lg backdrop-blur-sm">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
        <div className="flex items-center gap-2">
          <span
            className={`flex h-2 w-2 rounded-full ${
              isPositive ? "bg-emerald-400" : "bg-rose-400"
            }`}
          />
          <h3 className="text-base font-semibold text-zinc-100">Estimated Cash Position</h3>
        </div>
        <span className="rounded-md bg-zinc-800 px-2 py-0.5 text-xs font-medium text-zinc-400">
          Confirmed Only
        </span>
      </div>

      <div className="mt-4">
        <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">
          Current Net Flow (Confirmed)
        </p>
        <p
          className={`mt-1 text-2xl font-bold tracking-tight ${
            isPositive ? "text-emerald-400" : "text-rose-400"
          }`}
        >
          {paiseToRupeesDisplay(cashPositionPaise)}
        </p>
        <p className="mt-2 text-xs text-zinc-400">
          Calculated server-side from confirmed income and essential expenses.
        </p>
      </div>
    </div>
  );
}
