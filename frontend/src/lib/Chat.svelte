<script lang="ts">
  import { type ChatMessage, streamChat } from "./api";
  import Composer from "./Composer.svelte";
  import StatusBar from "./StatusBar.svelte";
  import Transcript from "./Transcript.svelte";

  const STORAGE_KEY = "r2-db2-chat-history-v1";
  const CONVERSATION_KEY = "r2-db2-conversation-id-v1";

  let messages = $state<ChatMessage[]>(loadHistory());
  let conversationId = $state(loadConversationId());
  let composerValue = $state("");
  let busy = $state(false);
  let error = $state<string | null>(null);
  let abort: AbortController | null = null;
  let composerRef = $state<{ focus: () => void }>();

  function loadHistory(): ChatMessage[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }

  function loadConversationId(): string {
    let id = localStorage.getItem(CONVERSATION_KEY);
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem(CONVERSATION_KEY, id);
    }
    return id;
  }

  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch {
      // localStorage full or disabled — non-fatal
    }
  }

  const turnCount = $derived(messages.filter((m) => m.role === "user").length);

  async function send(text: string) {
    if (!text || busy) return;
    error = null;
    busy = true;

    const startedAt = Date.now();
    const userMessage: ChatMessage = {
      role: "user",
      content: text,
      ts: startedAt,
    };
    const assistantMessage: ChatMessage = {
      role: "assistant",
      content: "",
      ts: startedAt,
    };
    messages = [...messages, userMessage, assistantMessage];
    persist();

    abort = new AbortController();
    try {
      const history = messages.slice(0, -1);
      for await (const delta of streamChat(
        history,
        conversationId,
        abort.signal,
      )) {
        assistantMessage.content += delta;
        messages = [...messages.slice(0, -1), assistantMessage];
      }
      assistantMessage.durationMs = Date.now() - startedAt;
      messages = [...messages.slice(0, -1), assistantMessage];
      persist();
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        const msg = (err as Error).message;
        error = msg;
        assistantMessage.content =
          assistantMessage.content || `Error: ${msg}`;
        assistantMessage.durationMs = Date.now() - startedAt;
        messages = [...messages.slice(0, -1), assistantMessage];
        persist();
      }
    } finally {
      busy = false;
      abort = null;
    }
  }

  function stop() {
    abort?.abort();
  }

  function reset() {
    if (busy) stop();
    messages = [];
    conversationId = crypto.randomUUID();
    localStorage.setItem(CONVERSATION_KEY, conversationId);
    localStorage.removeItem(STORAGE_KEY);
    error = null;
    composerValue = "";
  }

  function pickExample(text: string) {
    composerValue = text;
    queueMicrotask(() => composerRef?.focus());
  }

  function onWindowKeydown(event: KeyboardEvent) {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      reset();
    }
  }
</script>

<svelte:window onkeydown={onWindowKeydown} />

<div class="shell">
  <StatusBar {conversationId} turns={turnCount} {busy} />

  <Transcript {messages} {busy} onPick={pickExample} />

  {#if error}
    <div class="error" role="alert">
      <span class="error-tag">[err]</span>
      <span class="error-text">{error}</span>
      <button
        type="button"
        class="error-dismiss"
        onclick={() => (error = null)}
      >
        dismiss
      </button>
    </div>
  {/if}

  <Composer
    bind:this={composerRef}
    bind:value={composerValue}
    onSend={send}
    onStop={stop}
    {busy}
  />
</div>

<style>
  .shell {
    display: flex;
    flex-direction: column;
    height: 100vh;
    height: 100dvh;
    max-width: 1000px;
    margin: 0 auto;
    padding: 0;
    border-left: 1px solid var(--rule-soft);
    border-right: 1px solid var(--rule-soft);
  }

  .error {
    margin: 0 24px 8px;
    padding: 8px 12px;
    color: var(--err);
    border: 1px solid rgba(200, 72, 58, 0.4);
    border-left: 2px solid var(--err);
    background: rgba(200, 72, 58, 0.04);
    font-size: 12px;
    display: flex;
    align-items: center;
    gap: 10px;
    animation: fade-in 200ms ease forwards;
  }
  .error-tag {
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 10px;
    color: var(--err);
    flex-shrink: 0;
  }
  .error-text {
    flex: 1;
    color: var(--text);
    font-size: 12.5px;
  }
  .error-dismiss {
    flex-shrink: 0;
    border-color: rgba(200, 72, 58, 0.4);
    color: var(--err);
    padding: 2px 8px;
    font-size: 10px;
  }
  .error-dismiss:hover {
    border-color: var(--err);
    color: var(--err);
    background: rgba(200, 72, 58, 0.08);
  }

  @media (max-width: 640px) {
    .shell {
      border-left: none;
      border-right: none;
    }
    .error {
      margin: 0 16px 6px;
    }
  }
</style>
