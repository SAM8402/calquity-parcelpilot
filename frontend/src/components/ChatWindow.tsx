"use client";

import { useState, useRef, useEffect } from "react";
import MessageBubble from "./MessageBubble";
import ToolIndicator from "./ToolIndicator";
import ConfirmationDialog from "./ConfirmationDialog";

interface ToolUsage {
  tool: string;
  input: string;
  output: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  tools_used?: ToolUsage[];
  requires_confirmation?: boolean;
  pending_action_id?: string;
  timestamp?: string;
}

interface ChatWindowProps {
  userId: string;
}

const SUGGESTED_QUERIES = [
  {
    q: "Can Northstar cancel ORD-1001 without a fee?",
    hint: "Multi-step · agreement vs SOP",
  },
  {
    q: "Show me all open tickets",
    hint: "Structured data lookup",
  },
  {
    q: "A pickup is 3 hours late due to carrier fault. Credit?",
    hint: "SOP + contract override",
  },
  {
    q: "What issues are affecting multiple customers?",
    hint: "Ops · proactive scan",
  },
];

export default function ChatWindow({ userId }: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const [confirmAction, setConfirmAction] = useState<{
    actionId: string;
    message: string;
  } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    setMessages([]);
    setConfirmAction(null);
    setSessionId(crypto.randomUUID());
  }, [userId]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 120) + "px";
    }
  }, [input]);

  const sendMessage = async (text?: string) => {
    const userMessage = (text || input).trim();
    if (!userMessage || isLoading) return;

    setInput("");
    const now = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
    setMessages((prev) => [
      ...prev,
      { role: "user", content: userMessage, timestamp: now },
    ]);
    setIsLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          session_id: sessionId,
          user_id: userId,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP error ${res.status}`);
      }

      const data = await res.json();

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.response,
          tools_used: data.tools_used,
          requires_confirmation: data.requires_confirmation,
          pending_action_id: data.pending_action_id,
          timestamp: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        },
      ]);

      if (data.requires_confirmation && data.pending_action_id) {
        setConfirmAction({
          actionId: data.pending_action_id,
          message: data.response,
        });
      }
    } catch (error: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Error: ${error.message || "Something went wrong. Please try again."}`,
          timestamp: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirm = async (actionId: string) => {
    setIsLoading(true);
    try {
      const res = await fetch("/api/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action_id: actionId,
          session_id: sessionId,
          user_id: userId,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Confirm failed");
      }
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.response,
          timestamp: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        },
      ]);
    } catch (error: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Failed to confirm action: ${error.message || "Please try again."}`,
        },
      ]);
    } finally {
      setIsLoading(false);
      setConfirmAction(null);
    }
  };

  const handleCancel = () => {
    setConfirmAction(null);
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: "Action cancelled. Ask another question whenever you are ready.",
      },
    ]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex flex-1 flex-col overflow-hidden border border-paper-line bg-paper-raised shadow-desk">
      {/* Desk header strip */}
      <div className="flex items-center justify-between border-b border-paper-line bg-white/70 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-pulse-dot rounded-full bg-signal opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-signal" />
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-muted">
            Agent channel
          </span>
        </div>
        <span className="font-mono text-[10px] text-ink-muted">
          session {sessionId.slice(0, 8)}
        </span>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4 scrollbar-thin md:p-5">
        {messages.length === 0 && (
          <div className="flex h-full flex-col justify-center py-6">
            <p className="animate-rise-in font-mono text-[10px] uppercase tracking-[0.2em] text-ink-muted">
              Start with a probe
            </p>
            <h2 className="animate-rise-in stagger-1 mt-2 max-w-md font-display text-2xl font-semibold tracking-tight text-ink md:text-3xl">
              Ask what a dispatch desk would need to know.
            </h2>
            <p className="animate-rise-in stagger-2 mt-3 max-w-lg text-sm leading-relaxed text-ink-soft">
              Orders, cancellations, service credits, ticket patterns — answers
              cite policy vs agreement, and actions wait for your confirm.
            </p>

            <div className="mt-8 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {SUGGESTED_QUERIES.map((item, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(item.q)}
                  className={`animate-rise-in group border border-paper-line bg-white px-3.5 py-3 text-left transition-colors hover:border-signal/40 hover:bg-signal-wash/40 stagger-${i + 1}`}
                >
                  <span className="block text-sm font-medium text-ink group-hover:text-signal-deep">
                    {item.q}
                  </span>
                  <span className="mt-1 block font-mono text-[10px] uppercase tracking-wider text-ink-muted">
                    {item.hint}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className="animate-rise-in">
            <MessageBubble message={msg} />
            {msg.tools_used && msg.tools_used.length > 0 && (
              <ToolIndicator tools={msg.tools_used} />
            )}
          </div>
        ))}

        {isLoading && (
          <div className="animate-fade-in flex items-center gap-3 pl-1">
            <div className="flex items-center gap-2 border border-paper-line bg-white px-3 py-2">
              <span className="flex gap-1">
                <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-signal" />
                <span
                  className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-signal"
                  style={{ animationDelay: "0.15s" }}
                />
                <span
                  className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-signal"
                  style={{ animationDelay: "0.3s" }}
                />
              </span>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-muted">
                Reasoning across tools
              </span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-paper-line bg-white px-3 py-3 md:px-4">
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about ORD-1001, credits, tickets, escalations…"
            className="min-h-[48px] max-h-[120px] flex-1 resize-none border border-paper-line bg-paper-raised px-3 py-3 text-sm text-ink placeholder:text-ink-muted focus:border-signal focus:outline-none"
            rows={1}
            disabled={isLoading}
          />
          <button
            onClick={() => sendMessage()}
            disabled={isLoading || !input.trim()}
            className="bg-ink px-4 py-3 text-sm font-semibold tracking-wide text-paper-raised transition-colors hover:bg-signal-deep disabled:cursor-not-allowed disabled:opacity-35"
          >
            Send
          </button>
        </div>
        <p className="mt-2 text-center font-mono text-[10px] text-ink-muted">
          Citations over confidence · confirm before any state change
        </p>
      </div>

      {confirmAction && (
        <ConfirmationDialog
          actionId={confirmAction.actionId}
          message={confirmAction.message}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
        />
      )}
    </div>
  );
}
