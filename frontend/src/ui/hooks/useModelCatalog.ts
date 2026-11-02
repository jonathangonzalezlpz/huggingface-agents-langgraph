import { useCallback } from 'react';

import type { ModelCatalog } from '../../domain/run';
import { useServices } from '../services';
import { useAsyncData } from './useAsyncData';

const NONE: ModelCatalog = { models: [], visionModels: [] };

/** The models the server offers; empty until they load or when the request fails. */
export function useModelCatalog(): ModelCatalog {
  const { models } = useServices();
  const state = useAsyncData(useCallback(() => models.list(), [models]));
  return state.status === 'success' ? state.data : NONE;
}
