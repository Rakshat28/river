"use client";

import React, { useEffect, useState } from "react";

interface SubtitleTextProps {
  agentUtterance: string | null;
  userUtterance: string | null;
  isGeneratingPlan?: boolean;
}

export function SubtitleText({
  agentUtterance,
  userUtterance,
  isGeneratingPlan = false,
}: SubtitleTextProps) {
  const [activeText, setActiveText] = useState<string | null>(null);
  const [speaker, setSpeaker] = useState<"agent" | "user" | null>(null);

  useEffect(() => {
    if (agentUtterance) {
      setActiveText(agentUtterance);
      setSpeaker("agent");
    }
  }, [agentUtterance]);

  useEffect(() => {
    if (userUtterance) {
      setActiveText(userUtterance);
      setSpeaker("user");
    }
  }, [userUtterance]);

  if (isGeneratingPlan && speaker !== "agent") {
    return (
      <div className="min-h-12 px-4 text-center flex items-center justify-center text-amber-400 text-xs sm:text-sm font-semibold animate-pulse gap-2">
        <span className="h-2 w-2 rounded-full bg-amber-400 animate-ping flex-shrink-0" />
        Analyzing your cash flow &amp; generating your 30-day plan...
      </div>
    );
  }

  if (!activeText) {
    return (
      <div className="min-h-12 px-4 text-center flex items-center justify-center text-zinc-400 text-xs sm:text-sm font-medium animate-pulse">
        Connected — speak naturally anytime.
      </div>
    );
  }

  return (
    <div className="min-h-12 max-w-xl mx-auto flex flex-col items-center justify-center text-center px-3 sm:px-4 transition-all duration-300">
      <span
        className={`text-[9px] sm:text-[10px] uppercase tracking-widest font-semibold mb-0.5 ${
          speaker === "agent" ? "text-emerald-400" : "text-indigo-400"
        }`}
      >
        {speaker === "agent" ? "Assistant" : "You"}
      </span>
      <p className="text-sm sm:text-base md:text-lg font-medium text-zinc-100 leading-snug drop-shadow-md">
        "{activeText}"
      </p>
    </div>
  );
}
