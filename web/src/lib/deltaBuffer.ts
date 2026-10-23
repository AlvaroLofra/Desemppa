/**
 * Acumula los deltas de texto que llegan por SSE y los vuelca a React como mucho una vez por frame
 * (requestAnimationFrame), para que la interfaz no se congele con miles de tokens (dossier §2.5).
 */
export type Scheduler = (cb: () => void) => void;

export function createDeltaBuffer(
  onFlush: (chunks: Record<string, string>) => void,
  schedule: Scheduler = (cb) => requestAnimationFrame(cb),
) {
  let pending: Record<string, string> = {};
  let scheduled = false;
  return {
    push(key: string, text: string) {
      pending[key] = (pending[key] ?? "") + text;
      if (!scheduled) {
        scheduled = true;
        schedule(() => {
          scheduled = false;
          const out = pending;
          pending = {};
          onFlush(out);
        });
      }
    },
  };
}
