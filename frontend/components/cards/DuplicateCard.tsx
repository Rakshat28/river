import React from "react";
import type { Entry, SessionState } from "@/lib/types";
import { paiseToRupeesDisplay } from "@/lib/money";

interface DuplicateCardProps {
  state: SessionState | null;
}

export function DuplicateCard({ state }: DuplicateCardProps) {
  if (!state) return null;

  const allEntries: Entry[] = [
    ...state.income,
    ...state.essential_expenses,
    ...state.optional_expenses,
    ...state.debts,
  ];

  const duplicateEntries = allEntries.filter((e) => e.possible_duplicate);

  if (duplicateEntries.length === 0) {
    return (
      <div className="rounded-xl border border-sky-500/30 bg-sky-950/20 p-5 shadow-lg backdrop-blur-sm">
        <div className="flex items-center gap-2 border-b border-sky-500/20 pb-3">
          <span className="flex h-3 w-3 rounded-full bg-sky-400" />
          <h3 className="text-base font-semibold text-sky-200">No Duplicates Detected</h3>
        </div>
        <p className="mt-3 text-sm text-zinc-400">All financial entries are unique.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-sky-500/40 bg-zinc-900/95 p-5 shadow-xl backdrop-blur-sm">
      <div className="flex items-center justify-between border-b border-sky-500/30 pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-sky-500/20 text-sky-400 font-bold text-xs">
            ?
          </div>
          <h3 className="text-base font-semibold text-sky-300">Possible Duplicate</h3>
        </div>
        <span className="rounded-md bg-sky-950/80 border border-sky-700/50 px-2 py-0.5 text-xs font-semibold text-sky-300">
          Verification Needed
        </span>
      </div>

      <div className="mt-4 space-y-4">
        {duplicateEntries.map((item) => {
          const original = item.duplicate_of
            ? allEntries.find((e) => e.id === item.duplicate_of)
            : null;

          return (
            <div key={item.id} className="rounded-lg border border-sky-500/30 bg-zinc-950/80 p-4">
              <p className="text-xs text-sky-300 font-medium mb-2 text-center">
                Are these the same item?
              </p>

              <div className="grid grid-cols-2 gap-3 mt-3">
                {/* Original Entry */}
                <div className="rounded-md border border-zinc-800 bg-zinc-900/90 p-3">
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-zinc-500 block mb-1">
                    Existing Entry
                  </span>
                  <p className="text-sm font-semibold text-zinc-200">{original ? original.name : "Existing Entry"}</p>
                  <p className="text-sm font-bold text-zinc-300 mt-1">
                    {original ? paiseToRupeesDisplay(original.current.amount_paise) : "-"}
                  </p>
                </div>

                {/* New Candidate */}
                <div className="rounded-md border border-sky-500/50 bg-sky-950/40 p-3">
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-sky-400 block mb-1">
                    New Entry
                  </span>
                  <p className="text-sm font-semibold text-sky-200">{item.name}</p>
                  <p className="text-sm font-bold text-sky-300 mt-1">
                    {paiseToRupeesDisplay(item.current.amount_paise)}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
