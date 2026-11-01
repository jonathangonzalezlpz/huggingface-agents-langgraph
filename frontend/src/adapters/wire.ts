/**
 * Wire format of the backend API and its translation into the domain model.
 * This is the only place that knows the backend's snake_case JSON.
 */
import { z } from 'zod';

import { isCategory } from '../domain/categories';
import type { GaiaQuestion, ModelOption, RunRecord } from '../domain/run';
import type {
  AgentDefinition,
  Architecture,
  ArchitectureSummary,
  Catalog,
  EdgeDefinition,
  LlmState,
  SystemStatus,
  ValidationReport,
} from '../domain/types';

const stringList = z.array(z.string());

export const validationSchema = z.object({
  is_valid: z.boolean(),
  counts: z.object({ error: z.number(), warning: z.number(), info: z.number() }),
  availability: z
    .record(
      z.string(),
      z.object({ guaranteed: z.array(z.string()), possible: z.array(z.string()) }),
    )
    .default({}),
  diagnostics: z.array(
    z.object({
      code: z.string(),
      severity: z.enum(['error', 'warning', 'info']),
      message: z.string(),
      node_id: z.string().optional(),
      edge_source: z.string().optional(),
      branch: z.string().optional(),
    }),
  ),
});

export const catalogSchema = z.object({
  categories: stringList,
  nodes: z.array(
    z.object({
      implementation_id: z.string(),
      description: z.string(),
      category: z.string(),
      recover_errors: z.boolean(),
      contract: z.object({
        required_inputs: stringList,
        optional_inputs: stringList,
        guaranteed_outputs: stringList,
        optional_outputs: stringList,
      }),
    }),
  ),
  routing_strategies: z.array(
    z.object({ identifier: z.string(), description: z.string(), outputs: stringList }),
  ),
  state: z.object({ types: stringList, fields: stringList, initial_fields: stringList }),
});

const edgeSchema = z.discriminatedUnion('edge_type', [
  z.object({ edge_type: z.literal('direct'), source: z.string(), target: z.string() }),
  z.object({
    edge_type: z.literal('conditional'),
    source: z.string(),
    routing_strategy: z.string(),
    conditional_targets: z.record(z.string(), z.string()),
  }),
]);

const definitionSchema = z.object({
  schema_version: z.string(),
  architecture_id: z.string(),
  state_type: z.string(),
  initial_node: z.string(),
  nodes: z.array(
    z.object({
      id: z.string(),
      implementation_id: z.string(),
      description: z.string().default(''),
    }),
  ),
  edges: z.array(edgeSchema),
});

const summarySchema = z.object({
  id: z.string(),
  architecture_id: z.string(),
  version: z.number().int().nullable(),
  parent_id: z.string().nullable(),
  content_sha256: z.string(),
  created_at: z.string().nullable(),
  read_only: z.boolean(),
});

export const architectureSchema = summarySchema.extend({
  definition: definitionSchema,
  validation: validationSchema,
});

export const layoutSchema = z.object({
  layout: z.object({
    nodes: z.record(z.string(), z.object({ x: z.number(), y: z.number() })),
  }),
});

/** What saving returns: the stored version, without its validation. */
export const savedRecordSchema = summarySchema.extend({ definition: definitionSchema });

export const architectureListSchema = z.object({ architectures: z.array(summarySchema) });

export const statusSchema = z.object({
  llm: z.object({ state: z.string(), name: z.string() }).optional(),
});

const LLM_STATES: readonly LlmState[] = ['ready', 'sleeping', 'loading', 'unavailable'];

type Wire<T extends z.ZodType> = z.output<T>;

export function toSummary(wire: Wire<typeof summarySchema>): ArchitectureSummary {
  return {
    id: wire.id,
    architectureId: wire.architecture_id,
    version: wire.version,
    parentId: wire.parent_id,
    contentSha256: wire.content_sha256,
    createdAt: wire.created_at,
    readOnly: wire.read_only,
  };
}

function toEdge(wire: Wire<typeof edgeSchema>): EdgeDefinition {
  return wire.edge_type === 'direct'
    ? { type: 'direct', source: wire.source, target: wire.target }
    : {
        type: 'conditional',
        source: wire.source,
        routingStrategy: wire.routing_strategy,
        branches: wire.conditional_targets,
      };
}

function toDefinition(wire: Wire<typeof definitionSchema>): AgentDefinition {
  return {
    schemaVersion: wire.schema_version,
    architectureId: wire.architecture_id,
    stateType: wire.state_type,
    initialNode: wire.initial_node,
    nodes: wire.nodes.map((node) => ({
      id: node.id,
      implementationId: node.implementation_id,
      description: node.description,
    })),
    edges: wire.edges.map(toEdge),
  };
}

export function toValidation(wire: Wire<typeof validationSchema>): ValidationReport {
  return {
    isValid: wire.is_valid,
    counts: wire.counts,
    availability: wire.availability,
    diagnostics: wire.diagnostics.map((item) => ({
      code: item.code,
      severity: item.severity,
      message: item.message,
      ...(item.node_id === undefined ? {} : { nodeId: item.node_id }),
      ...(item.edge_source === undefined ? {} : { edgeSource: item.edge_source }),
      ...(item.branch === undefined ? {} : { branch: item.branch }),
    })),
  };
}

export function toArchitecture(wire: Wire<typeof architectureSchema>): Architecture {
  return {
    ...toSummary(wire),
    definition: toDefinition(wire.definition),
    validation: toValidation(wire.validation),
  };
}

export function toCatalog(wire: Wire<typeof catalogSchema>): Catalog {
  return {
    categories: wire.categories.filter(isCategory),
    components: wire.nodes.map((node) => ({
      implementationId: node.implementation_id,
      description: node.description,
      category: isCategory(node.category) ? node.category : 'other',
      recoverErrors: node.recover_errors,
      contract: {
        requiredInputs: node.contract.required_inputs,
        optionalInputs: node.contract.optional_inputs,
        guaranteedOutputs: node.contract.guaranteed_outputs,
        optionalOutputs: node.contract.optional_outputs,
      },
    })),
    routingStrategies: wire.routing_strategies,
    state: {
      types: wire.state.types,
      fields: wire.state.fields,
      initialFields: wire.state.initial_fields,
    },
  };
}

export function toStatus(wire: Wire<typeof statusSchema>): SystemStatus {
  const reported = wire.llm?.state;
  return {
    backend: 'online',
    llm: wire.llm
      ? {
          state: LLM_STATES.find((known) => known === reported) ?? 'unavailable',
          name: wire.llm.name,
        }
      : null,
  };
}

/** Serialize a definition the way the backend expects it. */
export function definitionToWire(definition: AgentDefinition) {
  return {
    schema_version: definition.schemaVersion,
    architecture_id: definition.architectureId,
    state_type: definition.stateType,
    initial_node: definition.initialNode,
    nodes: definition.nodes.map((node) => ({
      id: node.id,
      implementation_id: node.implementationId,
      description: node.description,
    })),
    edges: definition.edges.map((edge) =>
      edge.type === 'direct'
        ? { source: edge.source, edge_type: 'direct', target: edge.target }
        : {
            source: edge.source,
            edge_type: 'conditional',
            routing_strategy: edge.routingStrategy,
            conditional_targets: edge.branches,
          },
    ),
  };
}

export const runRecordSchema = z.object({
  id: z.string(),
  status: z.string(),
  duration_seconds: z.number().default(0),
  steps: z
    .array(
      z.object({
        node: z.string(),
        duration_seconds: z.number().default(0),
        update: z.record(z.string(), z.unknown()).nullish(),
        error: z.string().nullish(),
      }),
    )
    .default([]),
  architecture: z
    .object({
      engine: z.string(),
      id: z.string().nullish(),
      version: z.number().nullish(),
      content_sha256: z.string().nullish(),
    })
    .nullish(),
  task: z
    .object({
      question: z.string().default(''),
      experiment: z.object({ model: z.object({ model_id: z.string() }).nullish() }).nullish(),
    })
    .nullish(),
  result: z
    .object({ submitted_answer: z.string().nullish(), route: z.string().nullish() })
    .nullish(),
  error: z.string().nullish(),
});

export const modelsSchema = z.object({
  models: z.array(z.object({ provider: z.string(), model_id: z.string() })),
});

export const questionsSchema = z.array(
  z.object({
    task_id: z.string(),
    question: z.string(),
    Level: z.union([z.string(), z.number()]).nullish(),
    file_name: z.string().nullish(),
  }),
);

export function toRunRecord(wire: z.output<typeof runRecordSchema>): RunRecord {
  const architecture = wire.architecture;
  return {
    id: wire.id,
    status: wire.status === 'completed' ? 'completed' : 'error',
    durationSeconds: wire.duration_seconds,
    steps: wire.steps.map((step) => ({
      node: step.node,
      durationSeconds: step.duration_seconds,
      error: step.error ?? null,
      updatedFields: Object.keys(step.update ?? {}),
    })),
    architecture: architecture
      ? {
          engine: architecture.engine,
          id: architecture.id ?? null,
          version: architecture.version ?? null,
          contentSha256: architecture.content_sha256 ?? null,
        }
      : null,
    question: wire.task?.question ?? '',
    answer: wire.result?.submitted_answer ?? null,
    route: wire.result?.route ?? null,
    error: wire.error ?? null,
    modelId: wire.task?.experiment?.model?.model_id ?? null,
  };
}

const MODEL_PROVIDERS: readonly ModelOption['provider'][] = ['configured', 'ollama'];

export function toModels(wire: z.output<typeof modelsSchema>): ModelOption[] {
  return wire.models.flatMap((model) => {
    const provider = MODEL_PROVIDERS.find((known) => known === model.provider);
    return provider ? [{ provider, modelId: model.model_id }] : [];
  });
}

export function toQuestions(wire: z.output<typeof questionsSchema>): GaiaQuestion[] {
  return wire.map((item) => ({
    taskId: item.task_id,
    question: item.question,
    fileName: item.file_name ?? '',
    level: String(item.Level ?? ''),
  }));
}
