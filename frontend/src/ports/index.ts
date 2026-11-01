/** Outbound ports: what the Studio needs from the outside world. */
import type { Architecture, ArchitectureSummary, Catalog, SystemStatus } from '../domain/types';

export interface CatalogPort {
  getCatalog(): Promise<Catalog>;
}

export interface ArchitecturePort {
  list(): Promise<ArchitectureSummary[]>;
  get(id: string): Promise<Architecture>;
}

export interface SystemPort {
  getStatus(): Promise<SystemStatus>;
}

export type StudioMode = 'live' | 'demo';

export interface StudioServices {
  mode: StudioMode;
  catalog: CatalogPort;
  architectures: ArchitecturePort;
  system: SystemPort;
}
