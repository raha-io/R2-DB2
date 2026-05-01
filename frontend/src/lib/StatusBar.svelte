<script lang="ts">
  interface Props {
    conversationId: string;
    turns: number;
    busy: boolean;
  }

  const { conversationId, turns, busy }: Props = $props();

  const shortId = $derived(conversationId.replaceAll("-", "").slice(0, 8));
  const turnLabel = $derived(String(turns).padStart(3, "0"));
</script>

<header class="status">
  <div class="brand">
    <span class="led" class:live={!busy} class:proc={busy} aria-hidden="true"
    ></span>
    <span class="word">R2-DB2</span>
    <span class="slash">//</span>
    <span class="sub">Analyst</span>
  </div>

  <div class="meta">
    <span class="cell">
      <span class="lbl">thread</span>
      <span class="val">{shortId}</span>
    </span>
    <span class="cell">
      <span class="lbl">turn</span>
      <span class="val">{turnLabel}</span>
    </span>
    <span class="cell stat" class:proc={busy}>
      <span class="lbl">{busy ? "▸" : "●"}</span>
      <span class="val">{busy ? "PROC" : "IDLE"}</span>
    </span>
  </div>
</header>

<style>
  .status {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 24px 13px;
    border-bottom: 1px solid var(--rule);
    font-size: 11px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-dim);
    flex-shrink: 0;
    gap: 24px;
    background: linear-gradient(
      to bottom,
      rgba(20, 17, 13, 0.4),
      transparent
    );
    position: relative;
  }

  /* tiny corner brackets to evoke instrument framing */
  .status::before,
  .status::after {
    content: "";
    position: absolute;
    bottom: -1px;
    width: 8px;
    height: 1px;
    background: var(--amber);
    opacity: 0.6;
  }
  .status::before {
    left: 0;
  }
  .status::after {
    right: 0;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
  }

  .led {
    width: 6px;
    height: 6px;
    background: var(--text-faint);
    border-radius: 50%;
    flex-shrink: 0;
    transition: background 200ms ease;
  }
  .led.live {
    background: var(--ok);
    box-shadow:
      0 0 6px var(--ok),
      0 0 12px rgba(132, 160, 92, 0.4);
    animation: led-pulse 2.6s ease-in-out infinite;
  }
  .led.proc {
    background: var(--amber);
    box-shadow:
      0 0 6px var(--amber),
      0 0 14px rgba(245, 158, 11, 0.5);
    animation: led-pulse 0.8s ease-in-out infinite;
  }
  @keyframes led-pulse {
    0%,
    100% {
      transform: scale(1);
      opacity: 1;
    }
    50% {
      transform: scale(0.7);
      opacity: 0.55;
    }
  }

  .word {
    color: var(--text);
    font-weight: 600;
    font-size: 13px;
    letter-spacing: 0.06em;
  }

  .slash {
    color: var(--text-faint);
    font-weight: 300;
    margin: 0 -2px;
  }

  .sub {
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0.04em;
    font-style: italic;
  }

  .meta {
    display: flex;
    align-items: center;
    gap: 22px;
    overflow: hidden;
  }

  .cell {
    display: flex;
    align-items: baseline;
    gap: 7px;
    white-space: nowrap;
  }

  .lbl {
    color: var(--text-faint);
    font-size: 9px;
    letter-spacing: 0.12em;
  }

  .val {
    color: var(--text-dim);
    font-weight: 500;
    font-variant-numeric: tabular-nums;
  }

  .cell.stat .lbl {
    color: var(--ok);
    font-size: 11px;
  }
  .cell.stat .val {
    color: var(--ok);
    font-weight: 600;
  }
  .cell.stat.proc .lbl,
  .cell.stat.proc .val {
    color: var(--amber);
  }

  @media (max-width: 640px) {
    .status {
      padding: 12px 16px;
      gap: 12px;
    }
    .meta {
      gap: 14px;
    }
    .sub,
    .cell:first-child {
      display: none;
    }
  }
</style>
