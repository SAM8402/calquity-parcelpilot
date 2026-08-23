"use client";

import { useState } from "react";
import ChatWindow from "@/components/ChatWindow";
import UserSwitcher from "@/components/UserSwitcher";

const ROLE_META: Record<
  string,
  { label: string; scope: string; badge: string }
> = {
  northstar_user: {
    label: "Customer desk",
    scope: "ACCT-001 · Northstar Logistics only",
    badge: "CUSTOMER",
  },
  lumenworks_user: {
    label: "Customer desk",
    scope: "ACCT-002 · LumenWorks only",
    badge: "CUSTOMER",
  },
  support_agent: {
    label: "Support console",
    scope: "All accounts · escalate with confirmation",
    badge: "SUPPORT",
  },
  ops_manager: {
    label: "Ops console",
    scope: "Full access · proactive issue scan",
    badge: "OPS",
  },
};

export default function Home() {
  const [selectedUser, setSelectedUser] = useState<string>("support_agent");
  const meta = ROLE_META[selectedUser] || ROLE_META.support_agent;

  return (
    <main className="app-shell min-h-screen">
      <div className="app-content mx-auto max-w-6xl px-4 py-6 md:px-6 md:py-8">
        <div className="grid gap-6 lg:grid-cols-[240px_minmax(0,1fr)] lg:gap-8">
          {/* Brand / context rail */}
          <aside className="animate-rise-in flex flex-col justify-between lg:min-h-[calc(100vh-4rem)]">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-ink-muted">
                CalQuity assessment · ParcelPilot
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold leading-[1.05] tracking-tight text-ink md:text-[2.75rem]">
                Parcel
                <span className="text-signal">Pilot</span>
              </h1>
              <div className="brand-rule mt-4 h-[2px] w-16 bg-signal" />
              <p className="mt-4 max-w-[220px] text-sm leading-relaxed text-ink-soft">
                Support desk for policies, customer agreements, and live
                shipment data — with source authority built in.
              </p>

              <div className="mt-8 space-y-3 border-t border-paper-line pt-6">
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-muted">
                    Active context
                  </p>
                  <p className="mt-1 font-display text-lg font-medium text-ink">
                    {meta.label}
                  </p>
                  <p className="mt-0.5 text-xs text-ink-muted">{meta.scope}</p>
                </div>
                <span className="inline-flex items-center border border-signal/30 bg-signal-wash px-2 py-0.5 font-mono text-[10px] font-medium tracking-wider text-signal-deep">
                  {meta.badge}
                </span>
              </div>

              <div className="mt-8 hidden space-y-3 border-t border-paper-line pt-6 text-xs text-ink-muted lg:block">
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.18em]">
                    Dataset snapshot
                  </p>
                  <p className="mt-1 font-mono text-[11px] text-ink-soft">
                    2026-08-16 11:00 Asia/Kolkata
                  </p>
                </div>
                <ul className="space-y-1.5 leading-relaxed text-ink-soft">
                  <li className="flex gap-2">
                    <span className="mt-1.5 h-1 w-1 flex-shrink-0 bg-signal" />
                    Agreements beat current SOP
                  </li>
                  <li className="flex gap-2">
                    <span className="mt-1.5 h-1 w-1 flex-shrink-0 bg-signal" />
                    Deprecated PDFs = context only
                  </li>
                  <li className="flex gap-2">
                    <span className="mt-1.5 h-1 w-1 flex-shrink-0 bg-signal" />
                    Mutations need human confirm
                  </li>
                </ul>
              </div>
            </div>

            <p className="mt-10 hidden font-mono text-[10px] leading-relaxed text-ink-muted lg:block">
              CalQuity AI Engineer assessment · dual-context agent · tool-layer
              ACL
            </p>
          </aside>

          {/* Interaction surface */}
          <section className="animate-rise-in stagger-2 flex min-h-[calc(100vh-4rem)] flex-col">
            <header className="mb-3 flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-ink-muted">
                  Live session
                </p>
                <p className="mt-0.5 text-sm text-ink-soft">
                  Switch persona to test customer vs internal access.
                </p>
              </div>
              <UserSwitcher
                selectedUser={selectedUser}
                onUserChange={setSelectedUser}
              />
            </header>

            <ChatWindow userId={selectedUser} />
          </section>
        </div>
      </div>
    </main>
  );
}
