"use client";

import {
  BarChart3,
  BookOpen,
  Building2,
  ChevronDown,
  CircleHelp,
  FileText,
  LayoutDashboard,
  Menu,
  Receipt,
  Search,
  Settings2,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

type NavigationItem = {
  label: string;
  href: string;
  icon: typeof LayoutDashboard;
};

const primaryNavigation: NavigationItem[] = [
  { label: "Overview", href: "/dashboard", icon: LayoutDashboard },
  { label: "Transactions", href: "/transactions", icon: BookOpen },
  { label: "Invoices", href: "/invoices", icon: Receipt },
  { label: "Customers", href: "/customers", icon: Users },
  { label: "Reports", href: "/reports", icon: BarChart3 },
];

const adminNavigation: NavigationItem[] = [
  { label: "Workspace settings", href: "/settings", icon: Settings2 },
];

function Brand() {
  return (
    <Link className="brand" href="/dashboard" aria-label="TCSI Accounting home">
      <span className="brand-mark">T</span>
      <span className="brand-copy">
        <strong>TCSI</strong>
        <span>Accounting</span>
      </span>
    </Link>
  );
}

function Navigation({ onNavigate }: { onNavigate: () => void }) {
  const pathname = usePathname();

  const renderItems = (items: NavigationItem[]) =>
    items.map(({ label, href, icon: Icon }) => {
      const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`));
      return (
        <Link
          className={`nav-item${active ? " nav-item--active" : ""}`}
          href={href}
          key={href}
          onClick={onNavigate}
          aria-current={active ? "page" : undefined}
        >
          <Icon aria-hidden="true" size={17} strokeWidth={1.8} />
          <span>{label}</span>
        </Link>
      );
    });

  return (
    <nav className="sidebar-nav" aria-label="Workspace navigation">
      <div className="nav-section">
        <span className="nav-section-label">Workspace</span>
        {renderItems(primaryNavigation)}
      </div>
      <div className="nav-section">
        <span className="nav-section-label">Manage</span>
        {renderItems(adminNavigation)}
      </div>
      <div className="sidebar-support">
        <ShieldCheck aria-hidden="true" size={16} />
        <div>
          <strong>Workspace protected</strong>
          <span>Access follows your role.</span>
        </div>
      </div>
    </nav>
  );
}

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="app-shell">
      <aside className={`sidebar${mobileOpen ? " sidebar--open" : ""}`}>
        <div className="sidebar-header">
          <Brand />
          <button
            aria-label="Close navigation"
            className="icon-button sidebar-close"
            type="button"
            onClick={() => setMobileOpen(false)}
          >
            <X aria-hidden="true" size={18} />
          </button>
        </div>
        <div className="workspace-switcher">
          <span className="workspace-icon"><Building2 aria-hidden="true" size={16} /></span>
          <span className="workspace-switcher-copy">
            <small>Current workspace</small>
            <strong>Third Code Solutions</strong>
          </span>
          <ChevronDown aria-hidden="true" size={15} />
        </div>
        <div className="sidebar-search">
          <Search aria-hidden="true" size={16} />
          <span>Quick search</span>
          <kbd>⌘ K</kbd>
        </div>
        <Navigation onNavigate={() => setMobileOpen(false)} />
        <div className="sidebar-footer">
          <span className="status-dot" aria-hidden="true" />
          <span>All systems operational</span>
        </div>
      </aside>

      {mobileOpen && (
        <button
          className="sidebar-backdrop"
          aria-label="Close navigation"
          type="button"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <div className="app-content">
        <header className="topbar">
          <button
            aria-label="Open navigation"
            className="icon-button mobile-menu"
            type="button"
            onClick={() => setMobileOpen(true)}
          >
            <Menu aria-hidden="true" size={20} />
          </button>
          <div className="breadcrumbs">
            <span>TCSI WORKSPACE</span>
            <strong>Command center</strong>
          </div>
          <div className="topbar-actions">
            <Link className="topbar-link" href="/settings">
              <CircleHelp aria-hidden="true" size={16} />
              <span>Help center</span>
            </Link>
            <span className="topbar-divider" aria-hidden="true" />
            <span className="user-name">Third Code Solutions Inc.</span>
            <span className="avatar" aria-label="TCSI account">TC</span>
          </div>
        </header>
        <main className="main-content">{children}</main>
      </div>
    </div>
  );
}
