"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  FileText,
  BarChart3,
  Settings,
  Sparkles,
  Zap,
  Heart,
} from "lucide-react";
import { clsx } from "clsx";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Personas", href: "/personas", icon: Users },
  { name: "Content", href: "/content", icon: FileText },
  { name: "Engagement", href: "/engagement", icon: Heart },
  { name: "Analytics", href: "/analytics", icon: BarChart3 },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 w-72 bg-white/70 dark:bg-surface-900/80 backdrop-blur-2xl border-r border-surface-200 dark:border-surface-800 flex flex-col">
      {/* Logo */}
      <div className="h-20 flex items-center gap-4 px-6 border-b border-surface-200 dark:border-surface-800">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary-500 via-primary-600 to-accent-500 flex items-center justify-center shadow-lg shadow-primary-500/30">
          <Sparkles className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="font-display font-bold text-lg text-surface-900 dark:text-surface-100">
            AI Influencer
          </h1>
          <p className="text-xs text-surface-500 dark:text-surface-400 font-medium">
            Platform
          </p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-2">
        {navigation.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href));

          return (
            <Link
              key={item.name}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 px-4 py-3.5 rounded-xl font-semibold transition-all duration-300",
                isActive
                  ? "bg-gradient-to-r from-primary-500 to-primary-600 text-white shadow-md shadow-primary-500/25"
                  : "text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-100 hover:bg-surface-100 dark:hover:bg-surface-800"
              )}
            >
              <item.icon className="w-5 h-5" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-surface-200 dark:border-surface-800">
        <div className="px-4 py-4 rounded-xl bg-gradient-to-r from-primary-50 to-accent-50 dark:from-primary-500/10 dark:to-accent-500/10 border border-primary-100 dark:border-primary-500/20">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-4 h-4 text-primary-500" />
            <p className="text-xs font-semibold text-primary-700 dark:text-primary-400">
              System Status
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse-soft" />
            <span className="text-sm font-medium text-surface-700 dark:text-surface-300">
              All systems operational
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
}
