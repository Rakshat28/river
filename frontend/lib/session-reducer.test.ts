import { sessionReducer, initialExtendedState } from "./session-reducer";
import type { SessionState } from "./types";

function assert(condition: boolean, message: string) {
  if (!condition) {
    console.error("Assertion failed:", message);
    process.exit(1);
  }
}

// Test 1: Initial state application
const stateV7 = {
  room_name: "test-room",
  state_version: 7,
  income: [],
  expenses: [],
  debts: [],
  goals: [],
  conflicts: [],
  missing_fields: [],
  blocking_issues: [],
} as unknown as SessionState;

const appliedV7 = sessionReducer(initialExtendedState, { type: "SET_STATE", payload: stateV7 });
assert(appliedV7.state !== null && appliedV7.state.state_version === 7, "Failed to set initial state to v7");

// Test 2: Out of order message with lower version (v5) should be ignored
const stateV5 = {
  room_name: "test-room",
  state_version: 5,
  income: [{ id: "stale-entry" }],
  expenses: [],
  debts: [],
  goals: [],
  conflicts: [],
  missing_fields: [],
  blocking_issues: [],
} as unknown as SessionState;

const resultAfterV5 = sessionReducer(appliedV7, { type: "SET_STATE", payload: stateV5 });
assert(resultAfterV5 === appliedV7, "Reducer did not ignore out-of-order lower state_version (5 vs 7)");
assert(resultAfterV5.state?.state_version === 7, "State version changed after receiving lower version");

// Test 3: Equal version (v7) should also be ignored
const resultAfterSameV7 = sessionReducer(appliedV7, { type: "SET_STATE", payload: stateV7 });
assert(resultAfterSameV7 === appliedV7, "Reducer did not ignore equal state_version");

// Test 4: Higher version (v8) should overwrite
const stateV8 = {
  room_name: "test-room",
  state_version: 8,
  income: [],
  expenses: [],
  debts: [],
  goals: [],
  conflicts: [],
  missing_fields: [],
  blocking_issues: [],
} as unknown as SessionState;

const resultAfterV8 = sessionReducer(appliedV7, { type: "SET_STATE", payload: stateV8 });
assert(resultAfterV8.state !== null && resultAfterV8.state.state_version === 8, "Reducer failed to update to higher state_version 8");

// Test 5: HYDRATE establishing baseline from REST endpoint always applies regardless of version
const hydratedStateV3 = {
  room_name: "test-room",
  state_version: 3,
  income: [],
  expenses: [],
  debts: [],
  goals: [],
  conflicts: [],
  missing_fields: [],
  blocking_issues: [],
} as unknown as SessionState;

const resultAfterHydrate = sessionReducer(resultAfterV8, { type: "HYDRATE", payload: hydratedStateV3 });
assert(resultAfterHydrate.state !== null && resultAfterHydrate.state.state_version === 3, "HYDRATE failed to apply over existing state");

console.log("All sessionReducer out-of-order guard tests passed!");

