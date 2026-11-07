/**
 * SmoothStreamer — 60 FPS Fluid Token Dispatcher
 * Buffers incoming network token bursts from SSE and dispatches them at a
 * steady, buttery-smooth rate synchronized with requestAnimationFrame.
 */
export class SmoothStreamer {
  private targetText = '';
  private currentText = '';
  private rafId: number | null = null;
  private onUpdate: (text: string) => void;
  private isDone = false;
  private resolveDone?: () => void;

  constructor(onUpdate: (text: string) => void) {
    this.onUpdate = onUpdate;
  }

  append(fullAccumulated: string) {
    this.targetText = fullAccumulated;
    if (!this.rafId) {
      this.tick();
    }
  }

  private tick = () => {
    if (this.currentText.length < this.targetText.length) {
      const remaining = this.targetText.length - this.currentText.length;
      // Adaptive velocity:
      // Small buffer: 1-2 characters per frame (silky typing)
      // Large burst from LLM: smoothly accelerates so it never falls behind
      const step = Math.max(1, Math.min(remaining, Math.ceil(remaining / 3)));
      this.currentText = this.targetText.slice(0, this.currentText.length + step);
      this.onUpdate(this.currentText);
    }

    if (this.currentText.length < this.targetText.length) {
      this.rafId = requestAnimationFrame(this.tick);
    } else if (this.isDone) {
      this.rafId = null;
      if (this.resolveDone) {
        const resolve = this.resolveDone;
        this.resolveDone = undefined;
        resolve();
      }
    } else {
      this.rafId = null;
    }
  };

  async finish(): Promise<void> {
    this.isDone = true;
    if (this.currentText.length >= this.targetText.length) {
      if (this.rafId) {
        cancelAnimationFrame(this.rafId);
        this.rafId = null;
      }
      return;
    }
    return new Promise<void>((resolve) => {
      this.resolveDone = resolve;
      if (!this.rafId) this.tick();
    });
  }

  stop() {
    this.isDone = true;
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
  }
}
