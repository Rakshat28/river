"use client";

import React from "react";

export type OrbState = "idle" | "listening" | "speaking";

interface AgentOrbProps {
  orbState?: OrbState;
  onClick?: () => void;
  className?: string;
}

export function AgentOrb({ orbState = "idle", onClick, className = "" }: AgentOrbProps) {
  return (
    <div
      onClick={onClick}
      className={`relative flex items-center justify-center cursor-pointer select-none transition-all duration-500 ${className}`}
      role="button"
      tabIndex={0}
      aria-label={`Agent Orb - State: ${orbState}`}
    >
      {/* Outer Ambient Glow Ring */}
      <div
        className={`absolute rounded-full filter blur-xl transition-all duration-700 ${
          orbState === "speaking"
            ? "h-48 w-48 bg-gradient-to-r from-emerald-500/50 via-teal-400/60 to-cyan-500/50 animate-pulse scale-125"
            : orbState === "listening"
            ? "h-44 w-44 bg-gradient-to-r from-indigo-500/50 via-purple-500/60 to-pink-500/50 animate-ping opacity-75"
            : "h-36 w-36 bg-gradient-to-r from-blue-600/30 to-indigo-600/30 animate-pulse opacity-40"
        }`}
      />

      {/* Secondary Pulse Ring */}
      <div
        className={`absolute rounded-full border transition-all duration-500 ${
          orbState === "speaking"
            ? "h-40 w-40 border-emerald-400/40 animate-ping"
            : orbState === "listening"
            ? "h-36 w-36 border-indigo-400/60 animate-pulse"
            : "h-32 w-32 border-zinc-700/40"
        }`}
      />

      {/* Core Orb Container */}
      <div
        className={`relative z-10 flex h-28 w-28 items-center justify-center rounded-full bg-gradient-to-br transition-all duration-500 shadow-2xl ${
          orbState === "speaking"
            ? "from-emerald-400 via-teal-500 to-cyan-600 shadow-emerald-500/50 scale-105"
            : orbState === "listening"
            ? "from-indigo-500 via-purple-600 to-violet-700 shadow-purple-500/50 scale-100"
            : "from-slate-800 via-zinc-900 to-black shadow-zinc-950 border border-zinc-700/50 scale-95"
        }`}
      >
        {/* Visualizer Icons / Waveforms */}
        {orbState === "speaking" && (
          <div className="flex items-center gap-1">
            <span className="h-6 w-1.5 rounded-full bg-white animate-[bounce_1s_infinite_100ms]" />
            <span className="h-10 w-1.5 rounded-full bg-white animate-[bounce_1s_infinite_300ms]" />
            <span className="h-7 w-1.5 rounded-full bg-white animate-[bounce_1s_infinite_200ms]" />
            <span className="h-4 w-1.5 rounded-full bg-white animate-[bounce_1s_infinite_400ms]" />
          </div>
        )}

        {orbState === "listening" && (
          <div className="flex items-center justify-center">
            <div className="h-4 w-4 rounded-full bg-white/90 animate-pulse shadow-md" />
          </div>
        )}

        {orbState === "idle" && (
          <div className="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-400/30">
            <div className="h-2.5 w-2.5 rounded-full bg-indigo-300 animate-pulse" />
          </div>
        )}
      </div>
    </div>
  );
}
