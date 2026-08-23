"use client";

import { useState } from "react";
import type { ToolUsage } from "@/types/chat";

interface ToolIndicatorProps {
  tools: ToolUsage[];
}

const TOOL_LABELS: Record<string, string> = {
  search_documents: "Document search",
  query_structured_data: "Structured data",
  prepare_action: "Prepare action",
  confirm_action: "Confirm action",
  list_pending_actions: "Pending actions",
  detect_proactive_issues: "Proactive scan",
};

export default function ToolIndicator({ tools }: ToolIndicatorProps) {
  const [expanded, setExpanded] = useState(false);

  if (!tools || tools.length === 0) return null;

  return (
    <div className="ml-10 mt-1.5 mb-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="group flex items-center gap-2 text-ink-muted transition-colors hover:text-ink-soft"
      >
        <span className="font-mono text-[10px] uppercase tracking-[0.14em]">
          {tools.length} tool{tools.length !== 1 ? "s" : ""} invoked
        </span>
        <span className="flex gap-1">
          {tools.map((t, i) => (
            <span
              key={i}
              className="border border-paper-line bg-white px-1.5 py-0.5 font-mono text-[9px] text-ink-soft"
              title={TOOL_LABELS[t.tool] || t.tool}
            >
              {(TOOL_LABELS[t.tool] || t.tool).split(" ")[0]}
            </span>
          ))}
        </span>
        <span className="font-mono text-[10px] text-ink-muted group-hover:text-signal">
          {expanded ? "hide" : "detail"}
        </span>
      </button>

      {expanded && (
        <div className="animate-rise-in mt-2 space-y-2">
          {tools.map((tool, i) => (
            <div
              key={i}
              className="border border-paper-line border-l-2 border-l-signal bg-white p-3 text-xs"
            >
              <div className="font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-signal-deep">
                {TOOL_LABELS[tool.tool] || tool.tool}
              </div>
              <div className="mt-2 space-y-2 text-ink-soft">
                <div>
                  <span className="font-mono text-[10px] uppercase text-ink-muted">
                    Input
                  </span>
                  <p className="mt-0.5 font-mono text-[11px] leading-relaxed">
                    {tool.input.length > 160
                      ? tool.input.substring(0, 160) + "…"
                      : tool.input}
                  </p>
                </div>
                <div className="border border-paper-line bg-paper p-2">
                  <span className="font-mono text-[10px] uppercase text-ink-muted">
                    Output
                  </span>
                  <p className="mt-0.5 font-mono text-[11px] leading-relaxed text-ink-soft">
                    {tool.output.length > 260
                      ? tool.output.substring(0, 260) + "…"
                      : tool.output}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
