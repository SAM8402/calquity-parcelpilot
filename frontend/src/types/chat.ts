export interface ToolUsage {
  tool: string;
  input: string;
  output: string;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  tools_used?: ToolUsage[];
  requires_confirmation?: boolean;
  pending_action_id?: string;
  timestamp?: string;
}
