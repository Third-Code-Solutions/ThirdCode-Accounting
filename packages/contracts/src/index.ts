import { z } from "zod";

export const productName = "TCSI Accounting" as const;

export const dashboardStateSchema = z.enum([
  "ready",
  "configuration_required",
  "signed_out",
  "no_access",
  "unavailable",
]);

export const dashboardMetricSchema = z.object({
  label: z.string(),
  value: z.string(),
  helper: z.string(),
  tone: z.enum(["neutral", "positive", "attention", "accent"]),
});

export const dashboardActivitySchema = z.object({
  id: z.string(),
  title: z.string(),
  detail: z.string(),
  timestamp: z.string(),
  tone: z.enum(["neutral", "positive", "attention", "accent"]),
});

export const dashboardSummarySchema = z.object({
  state: dashboardStateSchema,
  workspaceName: z.string().nullable(),
  workspaceSlug: z.string().nullable(),
  metrics: z.array(dashboardMetricSchema),
  activity: z.array(dashboardActivitySchema),
  message: z.string(),
});

export type DashboardSummary = z.infer<typeof dashboardSummarySchema>;

export const workerJobSchema = z.object({
  jobName: z.string().min(1).max(120),
  runKey: z.string().min(1).max(240),
  workspaceId: z.string().uuid().nullable().optional(),
});

export type WorkerJob = z.infer<typeof workerJobSchema>;

export const createWorkspaceSchema = z.object({
  name: z.string().trim().min(2).max(160),
  slug: z.string().trim().toLowerCase().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/).max(80),
});

export type CreateWorkspace = z.infer<typeof createWorkspaceSchema>;

export const apiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
  }),
});

export const apiSuccessSchema = <T extends z.ZodType>(data: T) =>
  z.object({ data });
