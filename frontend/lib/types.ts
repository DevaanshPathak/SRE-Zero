export type Difficulty = "easy" | "medium" | "hard";
export type ServiceName = "web_server" | "database" | "cache" | "message_queue" | "load_balancer";
export type ConfigValue = string | number | boolean;

export type ActionType =
  | "inspect_logs"
  | "inspect_metrics"
  | "check_status"
  | "inspect_config"
  | "restart_service"
  | "update_config"
  | "resolve_incident"
  | "escalate";

export interface Action {
  actionType: ActionType;
  service?: string;
  key?: string;
  value?: ConfigValue;
  rootCause?: string;
  fix?: string;
  reason?: string;
}

export interface ActionResult {
  summary: string;
  details: Record<string, unknown>;
  error?: string | null;
}

export interface Observation {
  incidentId: string;
  step: number;
  stepsRemaining: number;
  alert: string;
  lastAction?: string | null;
  lastResult: ActionResult;
  knownFindings: string[];
  availableTools: string[];
  done: boolean;
}

export interface EpisodeMetrics {
  totalSteps: number;
  invalidActions: number;
  repeatedActions: number;
  evidenceActions: number;
  remediationActions: number;
  wrongRemediations: number;
  distractorFailures: number;
  prematureResolutions: number;
  success: boolean;
  finalReward: number;
}

export interface RewardBreakdown {
  components: Record<string, number>;
  penalties: Record<string, number>;
  rawTotal: number;
  total: number;
}

export interface StepInfo {
  rewardComponents: RewardBreakdown;
  invalidAction: boolean;
  terminalReason?: string | null;
  metricsSoFar: EpisodeMetrics;
  evidenceCoverage: number;
}

export interface StepResult {
  observation: Observation;
  reward: number;
  done: boolean;
  info: StepInfo;
}

export interface TaskCatalogItem {
  taskId: string;
  difficulty: Difficulty;
  alert: string;
}

export interface TaskCatalogResponse {
  tasks: TaskCatalogItem[];
  splits: Record<Difficulty, string[]>;
}

export interface ResetResponse {
  sessionId: string;
  observation: Observation;
  info: {
    taskId: string;
    availableActions: string[];
  };
}

export interface TimelineItem {
  step: number;
  action: string;
  reward: number;
  summary: string;
  error?: string | null;
}

export interface ModelCatalogResponse {
  models: string[];
  currentModel: string | null;
  hasApiKey: boolean;
}

export interface ModelRunResult {
  model: string;
  success: boolean;
  finalReward: number;
  totalSteps: number;
  invalidActions: number;
  evidenceCoverage: number;
  terminalReason?: string | null;
  error?: string | null;
  trajectory: TimelineItem[];
}

export interface ModelCompareResponse {
  taskId: string;
  results: ModelRunResult[];
}
