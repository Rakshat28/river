import type { SessionState } from "./types";

export type SessionAction =
  | { type: "HYDRATE"; payload: SessionState }
  | { type: "SET_STATE"; payload: SessionState }
  | { type: "RESET_STATE" };

export function sessionReducer(
  state: SessionState | null,
  action: SessionAction
): SessionState | null {
  switch (action.type) {
    case "HYDRATE":
      // Establishing baseline from REST snapshot endpoint on join — always applies regardless of version
      return action.payload;

    case "SET_STATE": {
      if (!state) {
        return action.payload;
      }

      const currentVersion =
        state.state_version ??
        (state as unknown as { stateVersion?: number }).stateVersion ??
        0;
      const incomingVersion =
        action.payload.state_version ??
        (action.payload as unknown as { stateVersion?: number }).stateVersion ??
        0;

      // Guards against the theoretical case of two broadcasts arriving out of order over the data channel:
      // if the incoming payload's stateVersion is less than or equal to the currently held version, ignore the update (no-op).
      if (incomingVersion <= currentVersion) {
        return state;
      }

      return action.payload;
    }

    case "RESET_STATE":
      return null;

    default:
      return state;
  }
}
