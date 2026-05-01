export type Role = "user" | "assistant" | "system";

export interface ChatMessage {
  role: Role;
  content: string;
  ts?: number;
  durationMs?: number;
}

interface StreamChunk {
  choices: Array<{
    delta?: { role?: Role; content?: string };
    finish_reason?: string | null;
  }>;
}

const MODEL_ID = "r2-db2-analyst";

/**
 * Stream a chat completion from the backend's OpenAI-compatible endpoint.
 *
 * Yields incremental text deltas as they arrive. Conversation continuity is
 * maintained via the optional `conversationId` (the backend uses it to map
 * to a LangGraph thread).
 */
export async function* streamChat(
  messages: ChatMessage[],
  conversationId: string,
  signal: AbortSignal,
): AsyncGenerator<string, void, void> {
  const wireMessages = messages.map(({ role, content }) => ({ role, content }));
  const response = await fetch("/v1/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: MODEL_ID,
      messages: wireMessages,
      stream: true,
      conversation_id: conversationId,
    }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });

    let separator = buffer.indexOf("\n\n");
    while (separator !== -1) {
      const event = buffer.slice(0, separator);
      buffer = buffer.slice(separator + 2);
      separator = buffer.indexOf("\n\n");

      for (const line of event.split("\n")) {
        if (!line.startsWith("data:")) {
          continue;
        }
        const payload = line.slice(5).trim();
        if (payload === "[DONE]") {
          return;
        }
        if (!payload) {
          continue;
        }
        try {
          const chunk: StreamChunk = JSON.parse(payload);
          const delta = chunk.choices[0]?.delta?.content;
          if (delta) {
            yield delta;
          }
        } catch {
          // skip malformed chunk; backend may emit keep-alive comments
        }
      }
    }
  }
}
