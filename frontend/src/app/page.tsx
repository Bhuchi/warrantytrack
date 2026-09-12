"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { HealthResponse } from "@/types";

type ConnectionState =
  | { kind: "checking" }
  | { kind: "connected"; health: HealthResponse }
  | { kind: "failed"; message: string };

/**
 * Temporary landing page. It exists to prove the frontend can reach the
 * backend, so a new teammate knows their environment works before they
 * start building. Replace with the real landing page (Figma D01).
 */
export default function Home() {
  const [state, setState] = useState<ConnectionState>({ kind: "checking" });

  useEffect(() => {
    let cancelled = false;

    api
      .health()
      .then((health) => {
        if (!cancelled) setState({ kind: "connected", health });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const message =
          error instanceof Error ? error.message : "Unknown error";
        setState({ kind: "failed", message });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-8 px-6 py-16">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">WarrantyTrack</h1>
        <p className="mt-2 text-slate-600 dark:text-slate-400">
          Warranty management for individuals and organizations.
          <br />
          DES424 Cloud-based Application Development · Group 5
        </p>
      </div>

      <section className="rounded-lg border border-slate-200 p-5 dark:border-slate-800">
        <h2 className="text-sm font-medium text-slate-500 dark:text-slate-400">
          Backend connection
        </h2>

        {state.kind === "checking" && (
          <p className="mt-2 text-slate-500">Checking…</p>
        )}

        {state.kind === "connected" && (
          <div className="mt-2">
            <p className="font-medium text-green-700 dark:text-green-400">
              Connected
            </p>
            <p className="mt-1 text-sm text-slate-500">
              {state.health.service} v{state.health.version}
            </p>
          </div>
        )}

        {state.kind === "failed" && (
          <div className="mt-2">
            <p className="font-medium text-red-700 dark:text-red-400">
              Not reachable
            </p>
            <p className="mt-1 text-sm text-slate-500">{state.message}</p>
            <p className="mt-3 text-sm text-slate-500">
              Is the backend running? Try{" "}
              <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">
                docker compose up
              </code>{" "}
              from the repo root.
            </p>
          </div>
        )}
      </section>

      <p className="text-sm text-slate-500">
        New here? Read <code>README.md</code>, then{" "}
        <code>docs/CONTRIBUTING.md</code>.
      </p>
    </main>
  );
}
