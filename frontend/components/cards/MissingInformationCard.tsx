import React from "react";

interface MissingInformationCardProps {
  missingFields?: string[];
}

const FIELD_LABELS: Record<string, string> = {
  income: "Income source (salary, business income, etc.)",
  obligations: "Obligations (essential expenses or debt/EMI payments)",
};

export function MissingInformationCard({ missingFields = [] }: MissingInformationCardProps) {
  const isComplete = missingFields.length === 0;

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/90 p-4 sm:p-5 shadow-lg backdrop-blur-sm">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
        <div className="flex items-center gap-2">
          <span
            className={`flex h-2 w-2 rounded-full ${
              isComplete ? "bg-emerald-400" : "bg-sky-400"
            }`}
          />
          <h3 className="text-sm sm:text-base font-semibold text-zinc-100">Intake Progress</h3>
        </div>
        <span
          className={`rounded-md px-2 py-0.5 text-xs font-medium ${
            isComplete
              ? "bg-emerald-950 text-emerald-300 border border-emerald-800/50"
              : "bg-sky-950 text-sky-300 border border-sky-800/50"
          }`}
        >
          {isComplete ? "Complete" : `${missingFields.length} pending`}
        </span>
      </div>

      {isComplete ? (
        <div className="mt-4 flex items-center gap-3 rounded-lg border border-emerald-900/50 bg-emerald-950/40 p-3 text-emerald-300">
          <svg className="h-5 w-5 flex-shrink-0 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <p className="text-xs sm:text-sm font-medium">All key financial details collected!</p>
        </div>
      ) : (
        <ul className="mt-3 space-y-2">
          {missingFields.map((field) => (
            <li
              key={field}
              className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950/60 p-3 text-zinc-300"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-sky-400" />
              <span className="text-sm font-medium">
                {FIELD_LABELS[field] ?? field}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
