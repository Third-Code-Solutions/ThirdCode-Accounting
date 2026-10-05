import type { MetadataRoute } from "next";

import { siteOrigin } from "../lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/platform", "/controls", "/pilot", "/contact", "/updates"],
        disallow: [
          "/api/",
          "/owner",
          "/auth/",
          "/dashboard",
          "/customers",
          "/invoices",
          "/reports",
          "/settings",
          "/transactions",
          "/web/",
          "/workspace",
          "/odoo",
        ],
      },
    ],
    sitemap: `${siteOrigin()}/sitemap.xml`,
  };
}
