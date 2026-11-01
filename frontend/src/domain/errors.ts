export type StudioErrorKind = 'network' | 'http' | 'contract';

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
