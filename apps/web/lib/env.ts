import { z } from "zod";

const optionalUrl = z.union([z.string().url(), z.literal("")]).optional();
const optionalSecret = z.union([z.string().min(1), z.literal("")]).optional();

const publicEnvSchema = z.object({
  NEXT_PUBLIC_APP_ENV: z.string().default("local"),
  NEXT_PUBLIC_APP_URL: optionalUrl,
  NEXT_PUBLIC_SUPABASE_URL: optionalUrl,
  NEXT_PUBLIC_SUPABASE_ANON_KEY: optionalSecret,
});

export type PublicEnv = z.infer<typeof publicEnvSchema> & {
  supabaseConfigured: boolean;
};

let cachedPublicEnv: PublicEnv | undefined;

export function getPublicEnv(): PublicEnv {
  if (cachedPublicEnv) {
    return cachedPublicEnv;
  }

  const parsed = publicEnvSchema.parse({
    NEXT_PUBLIC_APP_ENV: process.env.NEXT_PUBLIC_APP_ENV,
    NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  });

  cachedPublicEnv = {
    ...parsed,
    supabaseConfigured: Boolean(
      parsed.NEXT_PUBLIC_SUPABASE_URL && parsed.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    ),
  };

  return cachedPublicEnv;
}
