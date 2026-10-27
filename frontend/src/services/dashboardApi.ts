import { request } from "./api";

export interface RepoRef {
  repositoryId?: string;
  path?: string;
}

const post = <T>(url: string, body: unknown) =>
  request<T>(url, { method: "POST", body: JSON.stringify(body) });

export interface ArchitectureSummary {
  applicationName: string;
  summary: Record<string, number>;
  moduleMap: { nodes: { name: string; type: string; fileCount: number }[] };
  warnings: string[];
}

export interface FeatureResult {
  applicationName: string;
  summary: string;
  businessCapabilities: {
    name: string;
    description: string;
    confidence: number;
  }[];
  features: { name: string; summary: string; confidence: number }[];
  userWorkflows: { name: string; steps: string[] }[];
  overallConfidence: number;
  model: string;
  warnings: string[];
}

export interface CategoryComparison {
  base: number;
  enhancement: number;
  common: number;
  onlyInBase: { name: string }[];
  onlyInEnhancement: { name: string }[];
  modified: { name: string; conflicts: string[]; additions: string[] }[];
}

export interface ComparisonResult {
  baseApplication: string;
  enhancementApplication: string;
  modules: CategoryComparison;
  routes: CategoryComparison;
  apis: CategoryComparison;
  services: CategoryComparison;
  entities: CategoryComparison;
  integrationCandidates: {
    order: number;
    kind: string;
    name: string;
    action: string;
    risk: string;
  }[];
  warnings: string[];
}

export interface RecommendationResult {
  recommendations: {
    rank: number;
    filePath: string;
    action: string;
    reason: string;
    confidence: number;
    confidenceLabel: string;
  }[];
  warnings: string[];
}

export interface PlanResult {
  overallImpact: string;
  overallScore: number;
  summary: string;
  taskCount: number;
  phases: {
    number: number;
    name: string;
    tasks: {
      id: string;
      title: string;
      description: string;
      files: string[];
      dependsOn: string[];
      validation: string[];
      level: string;
      effort: string;
    }[];
  }[];
  warnings: string[];
}

export const dashboardApi = {
  architecture: (r: RepoRef) => post<ArchitectureSummary>("/architecture", r),
  features: (r: RepoRef) => post<FeatureResult>("/features", r),
  comparison: (base: RepoRef, enhancement: RepoRef) =>
    post<ComparisonResult>("/comparison", { base, enhancement }),
  recommendation: (base: RepoRef, enhancement: RepoRef) =>
    post<RecommendationResult>("/recommendation", { base, enhancement }),
  plan: (base: RepoRef, enhancement: RepoRef) =>
    post<PlanResult>("/plan", { base, enhancement, topN: null }),
};
