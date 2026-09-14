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
import { SessionState, FocusTarget, AppMessageEnvelope } from "./types";
import {
  sessionReducer,
  SessionAction,
  ExtendedSessionState,
  initialExtendedState,
} from "./session-reducer";

export { sessionReducer, type SessionAction, type ExtendedSessionState };

interface SessionContextType {
  extendedState: ExtendedSessionState;
  state: SessionState | null;
  currentFocus: FocusTarget;
  agentUtterance: string | null;
  userUtterance: string | null;
  dispatch: React.Dispatch<SessionAction>;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [extendedState, dispatch] = useReducer(
    sessionReducer,
    initialExtendedState
  );

  return (
    <SessionContext.Provider
      value={{
        extendedState,
        state: extendedState.state,
        currentFocus: extendedState.currentFocus,
        agentUtterance: extendedState.agentUtterance,
        userUtterance: extendedState.userUtterance,
        dispatch,
      }}
    >
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
        let raw = event?.data;
        if (typeof raw === "string") {
          try {
            raw = JSON.parse(raw);
          } catch {
            return;
          }
        }
        if (!raw || typeof raw !== "object") return;

        const payloadObj = raw as Record<string, unknown>;

        // Check envelope discriminant `type`
        if ("type" in payloadObj && typeof payloadObj.type === "string") {
          const env = raw as AppMessageEnvelope;
          switch (env.type) {
            case "state_update":
              dispatch({ type: "SET_STATE", payload: env.payload });
              break;
            case "focus_update": {
              const focusTarget =
                typeof env.payload === "string"
                  ? (env.payload as FocusTarget)
                  : env.payload.focus;
              dispatch({ type: "SET_FOCUS", payload: focusTarget });
              break;
            }
            case "agent_utterance": {
              const text =
                typeof env.payload === "string"
                  ? env.payload
                  : env.payload.text;
              dispatch({ type: "SET_AGENT_UTTERANCE", payload: text });
              break;
            }
            case "user_utterance": {
              const text =
                typeof env.payload === "string"
                  ? env.payload
                  : env.payload.text;
              dispatch({ type: "SET_USER_UTTERANCE", payload: text });
              break;
            }
          }
          return;
        }

        // Backward compatibility: raw SessionState broadcast
        if (
          ("state_version" in payloadObj && payloadObj.state_version !== undefined) ||
          ("stateVersion" in payloadObj && payloadObj.stateVersion !== undefined) ||
          ("room_name" in payloadObj && payloadObj.room_name !== undefined)
        ) {
          dispatch({ type: "SET_STATE", payload: raw as SessionState });
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

