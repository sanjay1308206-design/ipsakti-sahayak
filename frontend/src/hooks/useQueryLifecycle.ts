/**
 * Explicit request-lifecycle state (docs/PHASE_18_FRONTEND_PRODUCTIZATION.md
 * Section "State Management"). Plain React hooks only - no external
 * state-management library, per explicit instruction ("prefer simple
 * React state/hooks initially... do not introduce a state-management
 * library unless there is a demonstrated need" - none is demonstrated by
 * a single-screen application).
 */

import { useCallback, useState } from "react";
import { ApiError, postQuery } from "../api/client";
import { classifyOutcome } from "../api/outcome";
import type { QueryRequest, QueryResponse } from "../api/types";

export type QueryLifecycleStatus = "IDLE" | "LOADING" | "SUCCESS" | "ABSTAINED" | "ESCALATED" | "ERROR";

export interface QueryLifecycleState {
  status: QueryLifecycleStatus;
  response: QueryResponse | null;
  error: ApiError | null;
}

const IDLE_STATE: QueryLifecycleState = { status: "IDLE", response: null, error: null };

export function useQueryLifecycle() {
  const [state, setState] = useState<QueryLifecycleState>(IDLE_STATE);

  const submit = useCallback(async (payload: QueryRequest) => {
    setState({ status: "LOADING", response: null, error: null });
    try {
      const response = await postQuery(payload);
      const outcome = classifyOutcome(response);
      setState({ status: outcome, response, error: null });
    } catch (error) {
      const apiError = error instanceof ApiError ? error : new ApiError({ kind: "network_error", message: "unexpected client error" });
      setState({ status: "ERROR", response: null, error: apiError });
    }
  }, []);

  const reset = useCallback(() => {
    setState(IDLE_STATE);
  }, []);

  return { ...state, submit, reset };
}
