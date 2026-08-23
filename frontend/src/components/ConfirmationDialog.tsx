"use client";

interface ConfirmationDialogProps {
  actionId: string;
  message: string;
  onConfirm: (actionId: string) => void;
  onCancel: () => void;
}

export default function ConfirmationDialog({
  actionId,
  message,
  onConfirm,
  onCancel,
}: ConfirmationDialogProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/45 p-4 animate-fade-in">
      <div className="w-full max-w-md overflow-hidden border border-paper-line bg-paper-raised shadow-desk animate-rise-in">
        <div className="border-b border-paper-line px-5 py-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-warn">
            Confirmation required
          </p>
          <h3 className="mt-1 font-display text-xl font-semibold text-ink">
            Execute prepared action?
          </h3>
          <p className="mt-1 font-mono text-xs text-ink-muted">{actionId}</p>
        </div>

        <div className="px-5 py-4">
          <div className="max-h-52 overflow-y-auto border border-paper-line bg-paper p-3 text-sm leading-relaxed text-ink-soft scrollbar-thin">
            {message.split("\n").map((line, i) => (
              <p key={i} className={line.trim() === "" ? "mb-2" : "mb-0.5"}>
                {line}
              </p>
            ))}
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t border-paper-line px-5 py-4">
          <button
            onClick={onCancel}
            className="border border-paper-line bg-white px-4 py-2 text-sm font-medium text-ink-soft hover:bg-paper"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(actionId)}
            className="bg-signal px-4 py-2 text-sm font-semibold text-white hover:bg-signal-deep"
          >
            Confirm & execute
          </button>
        </div>
      </div>
    </div>
  );
}
