// The Doom scene's pacing (P12, D-106; 10_UI §2.6.2): each beat shows after its own pause (the
// server's pause_ms: three seconds before the lights go out, a quarter of a second for the thing that
// takes Willis) plus time to read the beat before it. A click shows the next beat at once.
export const READ_MS_PER_CHAR = 35
export const READ_MS_MAX = 20000

export function beatDelay (prev, beat) {
  return beat.pause_ms + (prev ? Math.min(READ_MS_MAX, READ_MS_PER_CHAR * prev.text.length) : 0)
}
