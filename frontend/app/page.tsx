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
import { SessionProvider, SessionDailySubscriber } from "@/lib/session-context";

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
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-zinc-950 px-6 text-zinc-50">
      <DailyAudio />
      <div className="rounded-full border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm font-medium text-zinc-200">
        {isConnected ? "Connected" : "Connecting..."}
      </div>
      {isConnected && (
        <button
          type="button"
          onClick={handleLeave}
          className="rounded-full bg-red-600 px-6 py-3 text-base font-semibold text-white transition hover:bg-red-500"
        >
          End Call
        </button>
      )}
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
    <main className="flex min-h-screen items-center justify-center bg-zinc-950 p-6">
      {!dailyCall || !session ? (
        <button
          type="button"
          onClick={handleStartCall}
          disabled={isStarting}
          className="rounded-full bg-emerald-500 px-6 py-3 text-base font-semibold text-zinc-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isStarting ? "Starting..." : "Start Call"}
        </button>
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
