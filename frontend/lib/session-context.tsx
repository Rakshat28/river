"use client";

import React, {
  createContext,
  useContext,
  useReducer,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import { useDaily, useDailyEvent, useAppMessage } from "@daily-co/daily-react";
import { SessionState } from "./types";
import { sessionReducer, SessionAction } from "./session-reducer";

export { sessionReducer, type SessionAction };

interface SessionContextType {
  state: SessionState | null;
  dispatch: React.Dispatch<SessionAction>;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(sessionReducer, null);

  return (
    <SessionContext.Provider value={{ state, dispatch }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSessionState() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSessionState must be used within a SessionProvider");
  }
  return context;
}

export function SessionDailySubscriber({ roomName }: { roomName?: string }) {
  const { dispatch } = useSessionState();
  const callObject = useDaily();

  const hydrateState = useCallback(
    async (targetRoom: string) => {
      if (!targetRoom) return;
      const baseUrl =
        process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";
      try {
        const response = await fetch(`${baseUrl}/api/state/${targetRoom}`);
        if (response.ok) {
          const initialState = (await response.json()) as SessionState;
          dispatch({ type: "HYDRATE", payload: initialState });
        }
      } catch (err) {
        console.error("Failed to hydrate session state:", err);
      }
    },
    [dispatch]
  );

  useDailyEvent(
    "joined-meeting",
    useCallback(() => {
      const roomInfo = callObject?.room();
      const name =
        roomName ||
        (roomInfo && "name" in roomInfo
          ? (roomInfo as unknown as { name: string }).name
          : undefined);
      if (name) {
        void hydrateState(name);
      }
    }, [callObject, roomName, hydrateState])
  );

  useDailyEvent(
    "left-meeting",
    useCallback(() => {
      dispatch({ type: "RESET_STATE" });
    }, [dispatch])
  );

  useAppMessage({
    onAppMessage: useCallback(
      (event: { data?: unknown }) => {
        let payload = event?.data;
        if (typeof payload === "string") {
          try {
            payload = JSON.parse(payload);
          } catch {
            return;
          }
        }
        if (
          payload &&
          typeof payload === "object" &&
          (("state_version" in payload && payload.state_version !== undefined) ||
            ("stateVersion" in payload && payload.stateVersion !== undefined) ||
            ("room_name" in payload && payload.room_name !== undefined))
        ) {
          dispatch({ type: "SET_STATE", payload: payload as SessionState });
        }
      },
      [dispatch]
    ),
  });

  useEffect(() => {
    if (callObject?.meetingState() === "joined-meeting") {
      const roomInfo = callObject?.room();
      const name =
        roomName ||
        (roomInfo && "name" in roomInfo
          ? (roomInfo as unknown as { name: string }).name
          : undefined);
      if (name) {
        void hydrateState(name);
      }
    }
  }, [callObject, roomName, hydrateState]);

  return null;
}
