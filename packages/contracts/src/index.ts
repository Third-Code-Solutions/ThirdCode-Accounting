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

export const demoRequestSchema = z.object({
  companyName: z.string().trim().min(2).max(160),
  contactName: z.string().trim().min(2).max(120),
  email: z.string().trim().email().max(254),
  phone: z.string().trim().max(40).optional().default(""),
  teamSize: z.enum(["1-5", "6-20", "21-50", "51-200", "201+"]),
  accountingStack: z.string().trim().max(160).optional().default(""),
  message: z.string().trim().min(10).max(2000),
  website: z.string().max(128).optional().default(""),
});

export type DemoRequest = z.infer<typeof demoRequestSchema>;

export const platformWorkspaceSummarySchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  slug: z.string(),
  member_count: z.number().int().nonnegative(),
  invoice_count: z.number().int().nonnegative(),
  posted_entry_count: z.number().int().nonnegative(),
  created_at: z.string(),
});

export const platformDemoRequestSummarySchema = z.object({
  id: z.string().uuid(),
  company_name: z.string(),
  contact_name: z.string(),
  email: z.string().email(),
  team_size: z.string(),
  status: z.string(),
  created_at: z.string(),
});

export const platformAnalyticsSchema = z.object({
  workspace_count: z.number().int().nonnegative(),
  membership_count: z.number().int().nonnegative(),
  invoice_count: z.number().int().nonnegative(),
  journal_entry_count: z.number().int().nonnegative(),
  receivables_due: z.number().nonnegative(),
  demo_request_count: z.number().int().nonnegative(),
  open_demo_request_count: z.number().int().nonnegative(),
  workspaces: z.array(platformWorkspaceSummarySchema),
  recent_demo_requests: z.array(platformDemoRequestSummarySchema),
});

export type PlatformAnalytics = z.infer<typeof platformAnalyticsSchema>;

export const apiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
  }),
});

export const apiSuccessSchema = <T extends z.ZodType>(data: T) =>
  z.object({ data });
