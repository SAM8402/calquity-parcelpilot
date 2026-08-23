"use client";

import ReactMarkdown from "react-markdown";
import type { Message } from "@/types/chat";

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="mr-2 mt-1 flex h-8 w-8 flex-shrink-0 items-center justify-center border border-signal/25 bg-signal-wash font-mono text-[9px] font-semibold tracking-wider text-signal-deep">
          AI
        </div>
      )}
      <div className="flex max-w-[82%] flex-col md:max-w-[75%]">
        <div
          className={`px-3.5 py-2.5 ${
            isUser
              ? "bg-ink text-paper-raised"
              : "border border-paper-line bg-white text-ink"
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap text-sm leading-relaxed">
              {message.content}
            </p>
          ) : (
            <div className="text-sm text-ink">
              <ReactMarkdown
                components={{
                  p: ({ children }) => (
                    <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>
                  ),
                  strong: ({ children }) => (
                    <strong className="font-semibold text-ink">{children}</strong>
                  ),
                  ul: ({ children }) => (
                    <ul className="mb-2 list-disc space-y-0.5 pl-4">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="mb-2 list-decimal space-y-0.5 pl-4">
                      {children}
                    </ol>
                  ),
                  li: ({ children }) => (
                    <li className="leading-relaxed">{children}</li>
                  ),
                  code: ({ children, className }) => {
                    const isInline = !className;
                    return isInline ? (
                      <code className="border border-paper-line bg-paper px-1 py-0.5 font-mono text-[11px] text-signal-deep">
                        {children}
                      </code>
                    ) : (
                      <code className="my-2 block overflow-x-auto border border-paper-line bg-paper p-3 font-mono text-[11px]">
                        {children}
                      </code>
                    );
                  },
                  a: ({ children, href }) => (
                    <a
                      href={href}
                      className="text-signal-deep underline decoration-signal/40 underline-offset-2"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {children}
                    </a>
                  ),
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}

          {message.requires_confirmation && (
            <div
              className={`mt-2 border-t pt-2 ${
                isUser ? "border-white/20" : "border-paper-line"
              }`}
            >
              <p className="font-mono text-[10px] font-medium uppercase tracking-wider text-warn">
                Awaiting confirmation
              </p>
            </div>
          )}
        </div>

        {message.timestamp && (
          <p
            className={`mt-1 font-mono text-[10px] text-ink-muted ${
              isUser ? "mr-0.5 text-right" : "ml-0.5"
            }`}
          >
            {message.timestamp}
          </p>
        )}
      </div>

      {isUser && (
        <div className="ml-2 mt-1 flex h-8 w-8 flex-shrink-0 items-center justify-center bg-ink font-mono text-[9px] font-semibold tracking-wider text-paper-raised">
          YOU
        </div>
      )}
    </div>
  );
}
