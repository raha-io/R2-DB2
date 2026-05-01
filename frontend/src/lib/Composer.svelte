<script lang="ts">
  interface Props {
    value?: string;
    onSend: (text: string) => void;
    onStop: () => void;
    busy: boolean;
  }

  let {
    value = $bindable(""),
    onSend,
    onStop,
    busy,
  }: Props = $props();

  let ta = $state<HTMLTextAreaElement>();
  let focused = $state(false);

  function autoresize() {
    if (!ta) return;
    ta.style.height = "auto";
    const next = Math.min(ta.scrollHeight, 200);
    ta.style.height = `${next}px`;
  }

  $effect(() => {
    void value;
    if (ta) {
      queueMicrotask(autoresize);
    }
  });

  export function focus() {
    ta?.focus();
  }

  function submit() {
    const text = (value ?? "").trim();
    if (!text || busy) return;
    onSend(text);
    value = "";
    queueMicrotask(autoresize);
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }
</script>

<div class="composer-wrap">
  <div class="composer" class:focused class:busy>
    <span class="prompt" class:spinning={busy} aria-hidden="true">
      {busy ? "◐" : ">"}
    </span>
    <textarea
      bind:this={ta}
      bind:value
      rows="1"
      placeholder={busy ? "running query…" : "ask in plain english…"}
      disabled={busy}
      onfocus={() => (focused = true)}
      onblur={() => (focused = false)}
      onkeydown={onKeydown}
      oninput={autoresize}
      spellcheck="false"
      autocomplete="off"
    ></textarea>
    {#if busy}
      <button class="action stop" onclick={onStop} type="button">
        <span class="square" aria-hidden="true"></span>
        <span>stop</span>
      </button>
    {:else}
      <button
        class="action run"
        onclick={submit}
        disabled={!(value ?? "").trim()}
        type="button"
      >
        <span>run</span>
        <span class="kbd kbd-inline">↵</span>
      </button>
    {/if}
  </div>

  <div class="hints">
    <span class="hint">
      <span class="kbd">↵</span>
      <span>run</span>
    </span>
    <span class="sep">·</span>
    <span class="hint">
      <span class="kbd">⇧</span><span class="kbd">↵</span>
      <span>newline</span>
    </span>
    <span class="sep">·</span>
    <span class="hint">
      <span class="kbd">⌘</span><span class="kbd">K</span>
      <span>new chat</span>
    </span>
  </div>
</div>

<style>
  .composer-wrap {
    flex-shrink: 0;
    padding: 12px 24px 18px;
    border-top: 1px solid var(--rule);
    background: linear-gradient(
      to top,
      rgba(20, 17, 13, 0.6),
      transparent
    );
    position: relative;
  }

  .composer-wrap::before,
  .composer-wrap::after {
    content: "";
    position: absolute;
    top: -1px;
    width: 8px;
    height: 1px;
    background: var(--amber);
    opacity: 0.6;
  }
  .composer-wrap::before {
    left: 0;
  }
  .composer-wrap::after {
    right: 0;
  }

  .composer {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 10px 12px;
    background: var(--surface);
    border: 1px solid var(--rule);
    transition:
      border-color 160ms ease,
      box-shadow 160ms ease;
  }
  .composer.focused {
    border-color: var(--amber);
    box-shadow:
      0 0 0 1px rgba(245, 158, 11, 0.18),
      0 0 24px rgba(245, 158, 11, 0.06);
  }

  .prompt {
    color: var(--text-muted);
    font-weight: 700;
    font-size: 16px;
    line-height: 1.5;
    width: 14px;
    text-align: center;
    flex-shrink: 0;
    transition: color 160ms ease;
    user-select: none;
  }
  .composer.focused .prompt {
    color: var(--amber);
  }
  .prompt.spinning {
    color: var(--amber);
    animation: spin 1.1s linear infinite;
  }

  textarea {
    flex: 1;
    font-size: 14px;
    line-height: 1.5;
    padding: 0;
    margin: 0;
    height: 21px;
    min-height: 21px;
    max-height: 200px;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--rule) transparent;
  }

  .action {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 4px 10px;
    align-self: flex-end;
    margin-bottom: 1px;
  }
  .action.stop {
    color: var(--ember);
    border-color: rgba(234, 88, 12, 0.4);
  }
  .action.stop:hover {
    border-color: var(--ember);
    color: var(--ember);
    background: rgba(234, 88, 12, 0.06);
  }

  .square {
    display: inline-block;
    width: 8px;
    height: 8px;
    background: currentColor;
  }

  .kbd {
    display: inline-block;
    border: 1px solid var(--rule);
    padding: 0 4px;
    font-size: 10px;
    color: var(--text-dim);
    line-height: 1.4;
    min-width: 14px;
    text-align: center;
    border-radius: 0;
  }
  .kbd-inline {
    color: inherit;
    border-color: currentColor;
    opacity: 0.7;
  }

  .hints {
    margin-top: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    font-size: 10px;
    letter-spacing: 0.06em;
    color: var(--text-faint);
    padding: 0 2px;
  }

  .hint {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    text-transform: uppercase;
  }

  .sep {
    color: var(--text-faint);
    opacity: 0.5;
  }

  @media (max-width: 640px) {
    .composer-wrap {
      padding: 10px 16px 14px;
    }
  }
</style>
