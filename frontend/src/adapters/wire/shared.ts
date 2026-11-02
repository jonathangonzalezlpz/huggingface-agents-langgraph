import type { z } from 'zod';

/** The value a zod schema produces once a payload has been parsed. */
export type Wire<T extends z.ZodType> = z.output<T>;
