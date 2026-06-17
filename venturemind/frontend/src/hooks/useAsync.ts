import { useEffect, useState } from "react";
import type { SectionStatus } from "../components/ui/SectionCard";

export interface AsyncResult<T> {
  status: SectionStatus;
  data: T | null;
  error?: string;
}

interface UseAsyncOptions {
  /** When false, the effect never runs and state stays "idle". */
  enabled?: boolean;
  /** Fallback message when the rejection isn't an Error instance. */
  errorMessage?: string;
}

/**
 * Run an async function whenever `deps` change and expose it as SectionCard's
 * status lifecycle (idle → loading → ready/error). Stale results are dropped
 * when deps change mid-flight.
 *
 * `fn` is intentionally excluded from the effect deps — pass the real
 * dependencies explicitly so a fresh closure on every render doesn't refire
 * the request.
 */
export function useAsync<T>(
  fn: () => Promise<T>,
  deps: unknown[],
  options: UseAsyncOptions = {},
): AsyncResult<T> {
  const { enabled = true, errorMessage = "Something went wrong." } = options;
  const [state, setState] = useState<AsyncResult<T>>({ status: "idle", data: null });

  useEffect(() => {
    if (!enabled) {
      setState({ status: "idle", data: null });
      return;
    }

    let cancelled = false;
    setState({ status: "loading", data: null });

    fn()
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch((err) => {
        if (!cancelled) {
          setState({
            status: "error",
            data: null,
            error: err instanceof Error ? err.message : errorMessage,
          });
        }
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, ...deps]);

  return state;
}
