"use client";

import Link from "next/link";
import { LucideIcon } from "lucide-react";
import { clsx } from "clsx";

interface StatCardProps {
  label: string;
  value: number;
  total?: number;
  icon: LucideIcon;
  color: "primary" | "accent" | "pink" | "amber" | "green";
  loading?: boolean;
  href?: string;
}

const colorClasses = {
  primary: {
    bg: "bg-primary-50 dark:bg-primary-500/10",
    border: "border-primary-100 dark:border-primary-500/20",
    iconBg: "bg-primary-100 dark:bg-primary-500/20",
    icon: "text-primary-600 dark:text-primary-400",
    value: "text-primary-600 dark:text-primary-400",
  },
  accent: {
    bg: "bg-accent-50 dark:bg-accent-500/10",
    border: "border-accent-100 dark:border-accent-500/20",
    iconBg: "bg-accent-100 dark:bg-accent-500/20",
    icon: "text-accent-600 dark:text-accent-400",
    value: "text-accent-600 dark:text-accent-400",
  },
  pink: {
    bg: "bg-pink-50 dark:bg-pink-500/10",
    border: "border-pink-100 dark:border-pink-500/20",
    iconBg: "bg-pink-100 dark:bg-pink-500/20",
    icon: "text-pink-600 dark:text-pink-400",
    value: "text-pink-600 dark:text-pink-400",
  },
  amber: {
    bg: "bg-amber-50 dark:bg-amber-500/10",
    border: "border-amber-100 dark:border-amber-500/20",
    iconBg: "bg-amber-100 dark:bg-amber-500/20",
    icon: "text-amber-600 dark:text-amber-400",
    value: "text-amber-600 dark:text-amber-400",
  },
  green: {
    bg: "bg-emerald-50 dark:bg-emerald-500/10",
    border: "border-emerald-100 dark:border-emerald-500/20",
    iconBg: "bg-emerald-100 dark:bg-emerald-500/20",
    icon: "text-emerald-600 dark:text-emerald-400",
    value: "text-emerald-600 dark:text-emerald-400",
  },
};

export function StatCard({
  label,
  value,
  total,
  icon: Icon,
  color,
  loading,
  href,
}: StatCardProps) {
  const colors = colorClasses[color];

  const content = (
    <div
      className={clsx(
        "card-hover animate-slide-up border-2",
        colors.bg,
        colors.border,
        href && "cursor-pointer"
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          {loading ? (
            <div className="h-10 w-24 bg-surface-200 dark:bg-surface-700 rounded-lg animate-pulse" />
          ) : (
            <p className={clsx("text-4xl font-bold", colors.value)}>
              {value.toLocaleString()}
              {total !== undefined && (
                <span className="text-xl text-surface-400 dark:text-surface-500 font-semibold">
                  /{total}
                </span>
              )}
            </p>
          )}
          <p className="text-sm font-semibold text-surface-600 dark:text-surface-400 mt-2">
            {label}
          </p>
        </div>
        <div
          className={clsx(
            "w-14 h-14 rounded-2xl flex items-center justify-center",
            colors.iconBg
          )}
        >
          <Icon className={clsx("w-7 h-7", colors.icon)} />
        </div>
      </div>
    </div>
  );

  if (href) {
    return <Link href={href}>{content}</Link>;
  }

  return content;
}
