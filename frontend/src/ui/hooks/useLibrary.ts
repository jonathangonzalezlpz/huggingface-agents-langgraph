import { useCallback } from 'react';

import { loadLibrary } from '../../application/loadLibrary';
import { useServices } from '../services';
import { useAsyncData } from './useAsyncData';

/** Every stored architecture version with its validation, loaded once and reloadable. */
export function useLibrary() {
  const { architectures } = useServices();
  return useAsyncData(useCallback(() => loadLibrary(architectures), [architectures]));
}

export type Library = ReturnType<typeof useLibrary>;
