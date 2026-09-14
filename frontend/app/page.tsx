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

import { IncomeCard } from "@/components/cards/IncomeCard";
import { EssentialExpensesCard } from "@/components/cards/EssentialExpensesCard";
import { DebtsCard } from "@/components/cards/DebtsCard";
import { MissingInformationCard } from "@/components/cards/MissingInformationCard";
import { CashPositionCard } from "@/components/cards/CashPositionCard";
import { ShortfallSurplusCard } from "@/components/cards/ShortfallSurplusCard";

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
  const { state } = useSessionState();

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
    if (!callObject) {
      return;
    }

    void callObject.join({
      url: session.room_url,
      token: session.token,
      startAudioOff: false,
      startVideoOff: true,
      subscribeToTracksAutomatically: true,
    });
  }, [callObject, session]);

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
    <div className="min-h-screen w-full bg-zinc-950 text-zinc-50 p-6">
      <DailyAudio />

      {/* Top Navigation / Controls Bar */}
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-zinc-800 bg-zinc-900/80 px-6 py-4 shadow-md backdrop-blur">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-zinc-100">
            Riverline Finance Assistant
          </h1>
          <p className="text-xs text-zinc-400">
            Room: {session.room_url.split("/").pop()}
            {state?.state_version !== undefined && (
              <span className="ml-2 font-mono text-zinc-500">
                (State v{state.state_version})
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 rounded-full border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-xs font-medium text-zinc-200">
            <span
              className={`h-2 w-2 rounded-full ${
                isConnected ? "bg-emerald-400 animate-pulse" : "bg-amber-400"
              }`}
            />
            {isConnected ? "Connected (Live Voice)" : "Connecting..."}
          </div>
          {isConnected && (
            <button
              type="button"
              onClick={handleLeave}
              className="rounded-full bg-red-600 px-5 py-2 text-xs font-semibold text-white transition hover:bg-red-500"
            >
              End Call
            </button>
          )}
        </div>
      </header>

      {/* Dashboard Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Top Summary Row */}
        <CashPositionCard cashPositionPaise={state?.cash_position_paise ?? 0} />
        <ShortfallSurplusCard cashPositionPaise={state?.cash_position_paise ?? 0} />
        <MissingInformationCard missingFields={state?.missing_fields ?? []} />

        {/* Detailed Item Lists Grid */}
        <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-3 gap-6">
          <IncomeCard income={state?.income ?? []} />
          <EssentialExpensesCard
            essentialExpenses={state?.essential_expenses ?? []}
          />
          <DebtsCard debts={state?.debts ?? []} />
        </div>
      </div>
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
    setSession(null);
    setDailyCall(null);
  };

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-50">
      {!dailyCall || !session ? (
        <div className="flex min-h-screen flex-col items-center justify-center p-6 text-center">
          <div className="max-w-md space-y-4">
            <h1 className="text-3xl font-extrabold tracking-tight text-zinc-100">
              Riverline Assistant
            </h1>
            <p className="text-sm text-zinc-400">
              Voice-first financial planning assistant. Start a call to begin discussing your income, expenses, and debts.
            </p>
            <button
              type="button"
              onClick={handleStartCall}
              disabled={isStarting}
              className="rounded-full bg-emerald-500 px-8 py-3.5 text-sm font-bold text-zinc-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60 shadow-lg shadow-emerald-950/40"
            >
              {isStarting ? "Initializing Session..." : "Start Financial Session"}
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
