import type { FocusTarget, SessionState } from "./types";

export interface ExtendedSessionState {
  state: SessionState | null;
  currentFocus: FocusTarget;
  agentUtterance: string | null;
  userUtterance: string | null;
}

export type SessionAction =
  | { type: "HYDRATE"; payload: SessionState }
  | { type: "SET_STATE"; payload: SessionState }
  | { type: "SET_FOCUS"; payload: FocusTarget }
  | { type: "SET_AGENT_UTTERANCE"; payload: string }
  | { type: "SET_USER_UTTERANCE"; payload: string }
  | { type: "RESET_STATE" };

export const initialExtendedState: ExtendedSessionState = {
  state: null,
  currentFocus: "idle",
  agentUtterance: null,
  userUtterance: null,
};

export function sessionReducer(
  extendedState: ExtendedSessionState = initialExtendedState,
  action: SessionAction
): ExtendedSessionState {
  switch (action.type) {
    case "HYDRATE":
      return {
        ...extendedState,
        state: action.payload,
      };

    case "SET_STATE": {
      const currentState = extendedState.state;
      if (!currentState) {
        return { ...extendedState, state: action.payload };
      }

      const currentVersion =
        currentState.state_version ??
        (currentState as unknown as { stateVersion?: number }).stateVersion ??
        0;
      const incomingVersion =
        action.payload.state_version ??
        (action.payload as unknown as { stateVersion?: number }).stateVersion ??
        0;

      // Guards against out-of-order broadcasts over WebRTC data channel
      if (incomingVersion <= currentVersion) {
        return extendedState;
      }

      return { ...extendedState, state: action.payload };
    }

    case "SET_FOCUS":
      return { ...extendedState, currentFocus: action.payload };

    case "SET_AGENT_UTTERANCE":
      return { ...extendedState, agentUtterance: action.payload };

    case "SET_USER_UTTERANCE":
      return { ...extendedState, userUtterance: action.payload };

    case "RESET_STATE":
      return initialExtendedState;

    default:
      return extendedState;
  }
}
