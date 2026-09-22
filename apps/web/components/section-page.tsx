import { ArrowRight, CircleDashed, Plus, Sparkles } from "lucide-react";
import Link from "next/link";

type SectionPageProps = {
  eyebrow: string;
  title: string;
  description: string;
  actionLabel: string;
  actionHref: string;
};

export function SectionPage({ eyebrow, title, description, actionLabel, actionHref }: SectionPageProps) {
  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <Link className="button button--primary" href={actionHref}>
          <Plus aria-hidden="true" size={17} />
          {actionLabel}
        </Link>
      </div>
      <section className="route-empty panel">
        <div className="route-empty-icon"><CircleDashed aria-hidden="true" size={29} /></div>
        <span className="eyebrow">Ready when you are</span>
        <h2>A calmer way to work with {title.toLowerCase()}</h2>
        <p>This workspace is connected to the TCSI platform foundation. The next workflow slice will appear here with live permissions, validation, and audit history.</p>
        <div className="inline-actions">
          <Link className="button button--primary" href={actionHref}>{actionLabel}</Link>
          <Link className="button button--quiet" href="/dashboard"><Sparkles aria-hidden="true" size={16} /> Back to overview <ArrowRight aria-hidden="true" size={15} /></Link>
        </div>
      </section>
    </div>
  );
}
