"use client";

import Daily from "@daily-co/daily-js";
import {
  DailyAudio,
  DailyProvider,
  useDaily,
  useDailyEvent,
} from "@daily-co/daily-react";
import { useEffect, useState } from "react";

import { createDailySession, type DailySessionResponse } from "@/lib/daily-client";
import { SessionProvider, SessionDailySubscriber, useSessionState } from "@/lib/session-context";

import { AgentOrb, type OrbState } from "@/components/AgentOrb";
import { SubtitleText } from "@/components/SubtitleText";
import { FocusCard } from "@/components/FocusCard";
import { FullSummaryDrawer } from "@/components/FullSummaryDrawer";

function CallRoom({
  session,
  onEndCall,
}: {
  session: DailySessionResponse;
  onEndCall: () => void;
}) {
  const callObject = useDaily();
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const { state, currentFocus, agentUtterance, userUtterance } = useSessionState();

  useDailyEvent("joined-meeting", () => {
    setIsConnected(true);
    setError(null);
  });

  useDailyEvent("left-meeting", () => {
    setIsConnected(false);
    onEndCall();
  });

  useDailyEvent("error", (event) => {
    const errorMessage =
      event?.errorMsg || event?.error || "Meeting ended unexpectedly";
    setError(String(errorMessage));
    setIsConnected(false);
  });

  const handleLeave = async () => {
    if (!callObject) return;
    try {
      await callObject.leave();
      setIsConnected(false);
      onEndCall();
    } catch (err) {
      console.error("Error leaving call:", err);
      setError("Failed to leave call");
    }
  };

  useEffect(() => {
    if (!callObject) return;

    void callObject.join({
      url: session.room_url,
      token: session.token,
      startAudioOff: false,
      startVideoOff: true,
      subscribeToTracksAutomatically: true,
    });
  }, [callObject, session]);

  // Determine current Agent Orb state
  let orbState: OrbState = "idle";
  if (agentUtterance) {
    orbState = "speaking";
  } else if (userUtterance || isConnected) {
    orbState = "listening";
  }

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-zinc-950 px-6 text-zinc-50">
        <div className="rounded-lg border border-red-700 bg-red-950 px-6 py-4 text-center">
          <p className="text-sm font-medium text-red-200">Call Error</p>
          <p className="mt-2 text-sm text-red-100">{error}</p>
          <button
            type="button"
            onClick={onEndCall}
            className="mt-4 rounded-full bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-500"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full bg-zinc-950 text-zinc-50 flex flex-col justify-between p-3 sm:p-6 relative overflow-hidden">
      <DailyAudio />

      {/* Top Header Bar */}
      <header className="flex items-center justify-between gap-2 sm:gap-4 rounded-xl border border-zinc-800/80 bg-zinc-900/60 px-3.5 py-3 sm:px-6 sm:py-3.5 backdrop-blur-md z-10">
        <div className="flex items-center gap-2 sm:gap-2.5">
          <div className="h-7 w-7 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-xs sm:text-sm">
            R
          </div>
          <span className="text-sm sm:text-base font-bold tracking-tight text-zinc-100">
            Riverline
          </span>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <button
            type="button"
            onClick={() => setIsDrawerOpen(true)}
            className="rounded-full border border-zinc-700 bg-zinc-900 px-3 py-1.5 sm:px-4 sm:py-2 text-[11px] sm:text-xs font-semibold text-zinc-200 transition hover:bg-zinc-800 hover:border-zinc-600"
          >
            View everything so far
          </button>

          {isConnected && (
            <button
              type="button"
              onClick={handleLeave}
              className="rounded-full bg-red-600/90 px-3 py-1.5 sm:px-4 sm:py-2 text-[11px] sm:text-xs font-semibold text-white transition hover:bg-red-500 whitespace-nowrap"
            >
              End Call
            </button>
          )}
        </div>
      </header>

      {/* Center Voice-First Interface */}
      <main className="flex-1 flex flex-col items-center justify-center py-4 sm:py-8 space-y-6 sm:space-y-8 z-10 my-auto w-full">
        {/* Animated Agent Orb */}
        <AgentOrb orbState={orbState} />

        {/* Live Subtitles */}
        <SubtitleText
          agentUtterance={agentUtterance}
          userUtterance={userUtterance}
          isGeneratingPlan={currentFocus === "plan" && !state?.plan}
        />

        {/* Active Context Card Router */}
        <FocusCard currentFocus={currentFocus} state={state} />
      </main>

      {/* Opt-In Summary Drawer */}
      <FullSummaryDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        state={state}
      />
    </div>
  );
}

export default function Home() {
  const [session, setSession] = useState<DailySessionResponse | null>(null);
  const [dailyCall, setDailyCall] = useState<ReturnType<typeof Daily.createCallObject> | null>(null);
  const [isStarting, setIsStarting] = useState(false);

  const handleStartCall = async () => {
    setIsStarting(true);

    try {
      const existingCall = Daily.getCallInstance();
      if (existingCall) {
        await existingCall.destroy();
      }

      const createdSession = await createDailySession();
      const callObject = Daily.createCallObject({
        startAudioOff: false,
        startVideoOff: true,
      });

      setSession(createdSession);
      setDailyCall(callObject);
    } catch (error) {
      console.error("Unable to start Daily call:", error);
      setSession(null);
      setDailyCall(null);
    } finally {
      setIsStarting(false);
    }
  };

  const handleEndCall = () => {
    if (dailyCall) {
      dailyCall.leave().catch(() => {});
      dailyCall.destroy().catch(() => {});
    }
    setSession(null);
    setDailyCall(null);
  };

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-50">
      {!dailyCall || !session ? (
        <div className="flex min-h-screen flex-col items-center justify-center p-4 sm:p-6 text-center">
          <div className="max-w-md w-full space-y-5 px-2">
            <div className="flex justify-center mb-2">
              <AgentOrb orbState="idle" />
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-zinc-100">
              Riverline Finance Assistant
            </h1>
            <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
              Voice-first financial planning. Start a voice session to interact naturally with real-time financial cards.
            </p>
            <button
              type="button"
              onClick={handleStartCall}
              disabled={isStarting}
              className="w-full sm:w-auto rounded-full bg-emerald-500 px-6 sm:px-8 py-3.5 text-xs sm:text-sm font-bold text-zinc-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60 shadow-lg shadow-emerald-950/40"
            >
              {isStarting ? "Initializing Voice Session..." : "Start Financial Session"}
            </button>
          </div>
        </div>
      ) : (
        <SessionProvider>
          <DailyProvider callObject={dailyCall}>
            <SessionDailySubscriber roomName={session.room_url.split("/").pop()} />
            <CallRoom session={session} onEndCall={handleEndCall} />
          </DailyProvider>
        </SessionProvider>
      )}
    </main>
  );
}

