/** `unavailable`: the feature cannot run in this mode (for example validation in the demo). */
export type StudioErrorKind = 'network' | 'http' | 'contract' | 'unavailable' | 'aborted';

/** A failure talking to, or understanding, the backend. */
export class StudioError extends Error {
  readonly kind: StudioErrorKind;
  readonly status: number | undefined;

  constructor(kind: StudioErrorKind, message: string, status?: number) {
    super(message);
    this.name = 'StudioError';
    this.kind = kind;
    this.status = status;
  }
}
