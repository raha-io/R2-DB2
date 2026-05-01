<script lang="ts">
  import { marked } from "marked";
  import type { ChatMessage } from "./api";

  marked.setOptions({ breaks: true, gfm: true });

  interface Props {
    messages: ChatMessage[];
    busy: boolean;
    onPick: (text: string) => void;
  }

  const { messages, busy, onPick }: Props = $props();

  let viewport = $state<HTMLDivElement>();
  let booted = $state(sessionStorage.getItem("r2-db2-booted") === "1");

  $effect(() => {
    if (booted) return;
    const t = setTimeout(() => {
      booted = true;
      sessionStorage.setItem("r2-db2-booted", "1");
    }, 1300);
    return () => clearTimeout(t);
  });

  $effect(() => {
    void messages.length;
    void messages[messages.length - 1]?.content;
    if (!viewport) return;
    requestAnimationFrame(() => {
      if (viewport) viewport.scrollTop = viewport.scrollHeight;
    });
  });

  const EXAMPLES = [
    "How many active customers signed up last quarter?",
    "Top 10 products by revenue, by month, this year.",
    "Compare conversion rates across acquisition channels.",
    "Median order value by region, year over year.",
  ];

  function fmtTime(ts: number): string {
    const d = new Date(ts);
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    const ss = String(d.getSeconds()).padStart(2, "0");
    return `${hh}:${mm}:${ss}`;
  }

  function fmtDur(ms: number | undefined): string | null {
    if (!ms) return null;
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60_000) return `${(ms / 1000).toFixed(2)}s`;
    return `${Math.floor(ms / 60_000)}m${Math.floor((ms % 60_000) / 1000)}s`;
  }

  function render(content: string): string {
    return marked.parse(content) as string;
  }
</script>

<div class="viewport" bind:this={viewport}>
  {#if !booted}
    <div class="boot">
      <span class="boot-line" style="--d:0ms">
        <span class="boot-prefix">&gt;</span>
        <span class="boot-text">initializing r2-db2 analyst</span>
      </span>
      <span class="boot-line" style="--d:240ms">
        <span class="boot-prefix">&gt;</span>
        <span class="boot-text"
          >connecting to <em>clickhouse://analytics</em></span
        >
        <span class="boot-fill" aria-hidden="true"></span>
        <span class="boot-tag ok">[OK]</span>
      </span>
      <span class="boot-line" style="--d:560ms">
        <span class="boot-prefix">&gt;</span>
        <span class="boot-text">loading schema catalog</span>
        <span class="boot-fill" aria-hidden="true"></span>
        <span class="boot-tag ok">[OK]</span>
      </span>
      <span class="boot-line" style="--d:840ms">
        <span class="boot-prefix">&gt;</span>
        <span class="boot-text">warming up langgraph runtime</span>
        <span class="boot-fill" aria-hidden="true"></span>
        <span class="boot-tag ok">[OK]</span>
      </span>
      <span class="boot-line ready" style="--d:1100ms">
        <span class="boot-prefix">&gt;</span>
        <span class="boot-text">READY.</span>
      </span>
    </div>
  {:else if messages.length === 0}
    <div class="welcome">
      <div class="banner">
        <div class="logo">R2-DB2</div>
        <div class="logo-sub">
          <span class="slash">//</span>
          <span>ANALYST</span>
        </div>
        <div class="version">
          v0.1.0 — natural-language analytics over your warehouse
        </div>
      </div>

      <div class="prelude">
        <p>Ask a question of your data.</p>
        <p class="prelude-dim">
          Be specific. Include time ranges, dimensions, and grouping.
        </p>
      </div>

      <div class="examples">
        <div class="examples-head">
          <span class="bracket">─── </span>
          <span>example queries</span>
          <span class="examples-rule"></span>
        </div>
        {#each EXAMPLES as q, i (i)}
          <button
            class="example"
            type="button"
            onclick={() => onPick(q)}
            style="--i:{i}"
          >
            <span class="num">[{String(i + 1).padStart(2, "0")}]</span>
            <span class="q">{q}</span>
            <span class="arrow" aria-hidden="true">↳</span>
          </button>
        {/each}
      </div>
    </div>
  {:else}
    {#each messages as m, i (i)}
      <article class="entry {m.role}">
        <header class="head">
          <span class="who">{m.role === "user" ? "USER" : "R2-DB2"}</span>
          <span class="dot">·</span>
          <span class="time">{fmtTime(m.ts ?? Date.now())}</span>
          {#if fmtDur(m.durationMs)}
            <span class="dot">·</span>
            <span class="dur">{fmtDur(m.durationMs)}</span>
          {/if}
          <span class="rule"></span>
        </header>
        <div class="body">
          <!-- biome-ignore lint/security/noDangerouslySetInnerHtml: trusted backend -->
          <div class="md">{@html render(m.content)}</div>
          {#if busy && i === messages.length - 1 && m.role === "assistant"}
            <span class="cursor cursor-blink" aria-hidden="true">▊</span>
          {/if}
        </div>
      </article>
    {/each}
  {/if}
</div>

<style>
  .viewport {
    flex: 1;
    overflow-y: auto;
    padding: 24px 0 16px;
    scrollbar-width: thin;
    scrollbar-color: var(--rule) transparent;
  }
  .viewport::-webkit-scrollbar {
    width: 8px;
  }
  .viewport::-webkit-scrollbar-thumb {
    background: var(--rule);
  }
  .viewport::-webkit-scrollbar-thumb:hover {
    background: var(--text-faint);
  }
  .viewport::-webkit-scrollbar-track {
    background: transparent;
  }

  /* ────── boot sequence ────── */

  .boot {
    padding: 32px 24px 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 13px;
    color: var(--text-dim);
  }
  .boot-line {
    opacity: 0;
    animation: fade-in 280ms ease forwards;
    animation-delay: var(--d);
    display: flex;
    align-items: baseline;
    gap: 8px;
    max-width: 560px;
  }
  .boot-prefix {
    color: var(--amber);
    flex-shrink: 0;
    font-weight: 600;
  }
  .boot-text em {
    color: var(--teal);
    font-style: normal;
  }
  .boot-fill {
    flex: 1;
    border-bottom: 1px dotted var(--text-faint);
    margin: 0 4px;
    transform: translateY(-3px);
    opacity: 0.6;
  }
  .boot-tag {
    flex-shrink: 0;
    font-size: 11px;
    letter-spacing: 0.08em;
  }
  .boot-tag.ok {
    color: var(--ok);
    font-weight: 600;
  }
  .boot-line.ready .boot-text {
    color: var(--amber);
    letter-spacing: 0.16em;
    font-weight: 600;
  }

  /* ────── welcome / empty state ────── */

  .welcome {
    padding: 32px 24px 24px;
    animation: fade-in 480ms ease forwards;
    max-width: 720px;
  }
  .banner {
    display: flex;
    flex-direction: column;
    gap: 0;
    margin-bottom: 36px;
  }
  .logo {
    font-size: 64px;
    font-weight: 700;
    line-height: 1;
    letter-spacing: -0.03em;
    color: var(--amber);
    text-shadow:
      0 0 18px rgba(245, 158, 11, 0.28),
      0 0 1px var(--ember);
    user-select: none;
  }
  .logo-sub {
    font-size: 15px;
    margin-top: 8px;
    color: var(--text-dim);
    letter-spacing: 0.18em;
    font-weight: 500;
    display: flex;
    align-items: baseline;
    gap: 8px;
  }
  .logo-sub .slash {
    color: var(--text-faint);
    font-weight: 300;
    font-size: 18px;
    letter-spacing: -0.05em;
  }
  .version {
    margin-top: 14px;
    font-size: 12px;
    color: var(--text-muted);
    letter-spacing: 0.02em;
  }

  .prelude {
    margin-bottom: 32px;
    color: var(--text);
    font-size: 14px;
    line-height: 1.7;
  }
  .prelude p {
    margin: 0;
  }
  .prelude-dim {
    color: var(--text-muted);
  }

  .examples {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }
  .examples-head {
    color: var(--text-faint);
    font-size: 10px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .examples-head .bracket {
    color: var(--amber);
    opacity: 0.7;
  }
  .examples-rule {
    flex: 1;
    height: 1px;
    background: linear-gradient(
      to right,
      var(--rule),
      transparent
    );
    margin-left: 6px;
  }

  .example {
    background: transparent;
    border: 0;
    border-left: 2px solid transparent;
    text-transform: none;
    letter-spacing: normal;
    text-align: left;
    padding: 10px 12px;
    font-size: 13.5px;
    color: var(--text-dim);
    display: flex;
    gap: 14px;
    align-items: baseline;
    transition: all 180ms ease;
    width: 100%;
    opacity: 0;
    animation: fade-in 360ms ease forwards;
    animation-delay: calc(var(--i) * 80ms + 200ms);
    cursor: pointer;
  }
  .example:hover:not(:disabled) {
    color: var(--text);
    border-left-color: var(--amber);
    background: rgba(245, 158, 11, 0.04);
    padding-left: 16px;
  }
  .example:hover .arrow {
    opacity: 1;
    transform: translateX(0);
  }
  .example .num {
    color: var(--amber);
    font-size: 11px;
    font-weight: 600;
    flex-shrink: 0;
  }
  .example .q {
    flex: 1;
  }
  .example .arrow {
    color: var(--amber);
    opacity: 0;
    transform: translateX(-4px);
    transition:
      opacity 180ms ease,
      transform 180ms ease;
    flex-shrink: 0;
  }

  /* ────── transcript entries ────── */

  .entry {
    padding: 0 24px 12px;
    margin-bottom: 14px;
    animation: fade-in 220ms ease forwards;
  }

  .head {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 0 4px;
    font-size: 10px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--text-muted);
    font-weight: 500;
  }
  .head .who {
    font-weight: 600;
  }
  .entry.user .head .who {
    color: var(--teal);
  }
  .entry.assistant .head .who {
    color: var(--amber);
  }
  .head .dot {
    color: var(--text-faint);
    opacity: 0.7;
  }
  .head .time,
  .head .dur {
    color: var(--text-faint);
    font-weight: 400;
    font-variant-numeric: tabular-nums;
  }
  .head .rule {
    flex: 1;
    height: 1px;
    background: linear-gradient(to right, var(--rule), transparent);
    margin-left: 6px;
  }

  .body {
    padding-left: 0;
    font-size: 13.5px;
    line-height: 1.65;
    word-wrap: break-word;
    overflow-wrap: anywhere;
  }
  .entry.user .body {
    color: var(--text-dim);
  }
  .entry.user .body .md :global(p) {
    margin: 0;
  }

  .cursor {
    display: inline-block;
    color: var(--amber);
    font-weight: 700;
    margin-left: 1px;
    text-shadow: 0 0 6px rgba(245, 158, 11, 0.5);
  }

  @media (max-width: 640px) {
    .entry {
      padding: 0 16px 10px;
    }
    .welcome,
    .boot {
      padding-left: 16px;
      padding-right: 16px;
    }
    .logo {
      font-size: 48px;
    }
  }
</style>
