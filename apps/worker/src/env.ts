import { z } from "zod";

const workerEnvSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  WORKER_ENV: z.enum(["development", "test", "production"]).default("development"),
  WORKER_PORT: z.coerce.number().int().min(1).max(65535).default(3001),
  PORT: z.coerce.number().int().min(1).max(65535).optional(),
  WORKER_POLL_INTERVAL_MS: z.coerce.number().int().min(1000).max(86_400_000).default(60_000),
  SUPABASE_URL: z.union([z.string().url(), z.literal("")]).optional(),
  SUPABASE_SERVICE_ROLE_KEY: z.union([z.string().min(1), z.literal("")]).optional(),
});

export type WorkerEnv = z.infer<typeof workerEnvSchema> & {
  configured: boolean;
};

export function loadWorkerEnv(): WorkerEnv {
  const parsed = workerEnvSchema.parse({
    NODE_ENV: process.env.NODE_ENV,
    WORKER_ENV: process.env.WORKER_ENV,
    WORKER_PORT: process.env.WORKER_PORT,
    PORT: process.env.PORT,
    WORKER_POLL_INTERVAL_MS: process.env.WORKER_POLL_INTERVAL_MS,
    SUPABASE_URL: process.env.SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
  });

  const configured = Boolean(parsed.SUPABASE_URL && parsed.SUPABASE_SERVICE_ROLE_KEY);
  if (parsed.WORKER_ENV === "production" && !configured) {
    throw new Error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required in production");
  }

  return { ...parsed, configured };
}
