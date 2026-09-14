import React from "react";
import { paiseToRupeesDisplay } from "@/lib/money";

interface ShortfallSurplusCardProps {
  cashPositionPaise?: number;
}

export function ShortfallSurplusCard({ cashPositionPaise = 0 }: ShortfallSurplusCardProps) {
  const isSurplus = cashPositionPaise >= 0;

  return (
    <div
      className={`rounded-xl border p-5 shadow-lg backdrop-blur-sm ${
        isSurplus
          ? "border-emerald-900/60 bg-emerald-950/20"
          : "border-rose-900/60 bg-rose-950/20"
      }`}
    >
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
        <div className="flex items-center gap-2">
          <span
            className={`flex h-2 w-2 rounded-full ${
              isSurplus ? "bg-emerald-400" : "bg-rose-400"
            }`}
          />
          <h3 className="text-base font-semibold text-zinc-100">
            {isSurplus ? "Surplus Status" : "Shortfall Alert"}
          </h3>
        </div>
        <span
          className={`rounded-md px-2 py-0.5 text-xs font-semibold uppercase tracking-wider ${
            isSurplus
              ? "bg-emerald-950 text-emerald-300 border border-emerald-800/50"
              : "bg-rose-950 text-rose-300 border border-rose-800/50"
          }`}
        >
          {isSurplus ? "Surplus" : "Shortfall"}
        </span>
      </div>

      <div className="mt-4">
        <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">
          {isSurplus ? "Available Monthly Margin" : "Net Monthly Shortfall"}
        </p>
        <p
          className={`mt-1 text-3xl font-extrabold tracking-tight ${
            isSurplus ? "text-emerald-400" : "text-rose-400"
          }`}
        >
          {paiseToRupeesDisplay(cashPositionPaise)}
        </p>
        <p className="mt-2 text-xs text-zinc-400">
          {isSurplus
            ? "Your confirmed income exceeds your confirmed essential obligations."
            : "Your confirmed essential obligations exceed your confirmed monthly income."}
        </p>
      </div>
    </div>
  );
}
