import nextVitals from "eslint-config-next/core-web-vitals";
import { globalIgnores } from "eslint/config";

export default [
  ...nextVitals,
  {
    rules: {
      "@next/next/no-html-link-for-pages": "off",
    },
  },
  globalIgnores([
    "**/.next/**",
    "**/dist/**",
    "**/node_modules/**",
    "**/coverage/**",
    "**/.turbo/**",
  ]),
];
