import React from "react";
import type { Conflict, SessionState } from "@/lib/types";
import { paiseToRupeesDisplay } from "@/lib/money";

interface ConflictCardProps {
  conflicts: Conflict[];
  state: SessionState | null;
}

export function ConflictCard({ conflicts, state }: ConflictCardProps) {
  const unresolved = conflicts.filter((c) => !c.resolved);

  if (unresolved.length === 0) {
    return (
      <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-5 shadow-lg backdrop-blur-sm">
        <div className="flex items-center gap-2 border-b border-amber-500/20 pb-3">
          <span className="flex h-3 w-3 rounded-full bg-amber-400 animate-ping" />
          <h3 className="text-base font-semibold text-amber-200">Conflict Resolved</h3>
        </div>
        <p className="mt-3 text-sm text-zinc-400">All financial conflicts have been resolved.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-amber-500/40 bg-zinc-900/95 p-5 shadow-xl backdrop-blur-sm">
      <div className="flex items-center justify-between border-b border-amber-500/30 pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-500/20 text-amber-400 font-bold text-xs">
            !
          </div>
          <h3 className="text-base font-semibold text-amber-300">Conflict Detected</h3>
        </div>
        <span className="rounded-md bg-amber-950/80 border border-amber-700/50 px-2 py-0.5 text-xs font-semibold text-amber-300">
          Action Needed
        </span>
      </div>

      <div className="mt-4 space-y-4">
        {unresolved.map((conflict) => {
          // Find target entry name across state arrays
          let entryName = conflict.entry_id;
          if (state) {
            const allEntries = [
              ...state.income,
              ...state.essential_expenses,
              ...state.optional_expenses,
              ...state.debts,
            ];
            const found = allEntries.find((e) => e.id === conflict.entry_id);
            if (found) entryName = found.name;
          }

          return (
            <div key={conflict.id} className="rounded-lg border border-amber-500/30 bg-zinc-950/80 p-4">
              <div className="flex items-center justify-between text-xs text-amber-400 font-medium mb-3">
                <span>Item: <strong className="text-zinc-200">{entryName}</strong></span>
                <span>Updating: <strong className="text-zinc-200 capitalize">{conflict.field_name.replace("_paise", "").replace("_rupees", "").replace("_", " ")}</strong></span>
              </div>

              <p className="text-xs text-zinc-400 mb-3 text-center italic">
                "Which is right?" — Speak to confirm the correct value
              </p>

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-md border border-zinc-800 bg-zinc-900/90 p-3 text-center">
                  <span className="text-[11px] uppercase tracking-wider font-semibold text-zinc-500 block mb-1">
                    Previous Value
                  </span>
                  <span className="text-base font-bold text-zinc-300 line-through">
                    {paiseToRupeesDisplay(conflict.old_amount_paise)}
                  </span>
                </div>

                <div className="rounded-md border border-amber-500/60 bg-amber-950/40 p-3 text-center">
                  <span className="text-[11px] uppercase tracking-wider font-semibold text-amber-400 block mb-1">
                    New Value
                  </span>
                  <span className="text-base font-bold text-amber-300">
                    {paiseToRupeesDisplay(conflict.new_amount_paise)}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
