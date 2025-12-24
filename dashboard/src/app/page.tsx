"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Users,
  FileText,
  Heart,
  TrendingUp,
  Activity,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import { StatCard } from "@/components/StatCard";
import { PersonaCard } from "@/components/PersonaCard";
import { ActivityFeed } from "@/components/ActivityFeed";
import { api, DashboardStats, Persona, ActivityLogEntry } from "@/lib/api";
import Link from "next/link";

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useQuery<DashboardStats>({
    queryKey: ["dashboardStats"],
    queryFn: api.getDashboardStats,
  });

  const { data: personas, isLoading: personasLoading } = useQuery<Persona[]>({
    queryKey: ["personas"],
    queryFn: api.getPersonas,
  });

  const { data: activities, isLoading: activitiesLoading } = useQuery<
    ActivityLogEntry[]
  >({
    queryKey: ["activities"],
    queryFn: () => api.getActivityLog(10),
  });

  return (
    <div className="max-w-7xl mx-auto space-y-10">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-3xl font-display font-bold text-surface-900 dark:text-surface-100">
              Dashboard
            </h1>
          </div>
          <p className="text-surface-500 dark:text-surface-400 font-medium">
            Welcome back! Here's what your AI personas are up to.
          </p>
        </div>
        <Link href="/personas/new" className="btn-primary flex items-center gap-2">
          <Users className="w-4 h-4" />
          Create Persona
        </Link>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
        <StatCard
          label="Active Personas"
          value={stats?.active_personas ?? 0}
          total={stats?.total_personas ?? 0}
          icon={Users}
          color="primary"
          loading={statsLoading}
          href="/personas"
        />
        <StatCard
          label="Content Scheduled"
          value={stats?.scheduled_content ?? 0}
          icon={FileText}
          color="accent"
          loading={statsLoading}
          href="/content"
        />
        <StatCard
          label="Engagements Today"
          value={stats?.engagements_today ?? 0}
          icon={Heart}
          color="pink"
          loading={statsLoading}
        />
        <StatCard
          label="Weekly Growth"
          value={stats?.total_followers ?? 0}
          icon={TrendingUp}
          color="green"
          loading={statsLoading}
          href="/analytics"
        />
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        {/* Personas Section */}
        <div className="xl:col-span-2 space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary-100 dark:bg-primary-500/20 flex items-center justify-center">
                <Users className="w-5 h-5 text-primary-600 dark:text-primary-400" />
              </div>
              <h2 className="text-xl font-display font-bold text-surface-900 dark:text-surface-100">
                Your Personas
              </h2>
            </div>
            <Link
              href="/personas"
              className="text-sm font-semibold text-primary-600 dark:text-primary-400 hover:text-primary-500 flex items-center gap-1 transition-colors"
            >
              View all
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {personasLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="card h-32 animate-pulse bg-surface-100 dark:bg-surface-800"
                />
              ))}
            </div>
          ) : personas && personas.length > 0 ? (
            <div className="space-y-4">
              {personas.slice(0, 5).map((persona, index) => (
                <PersonaCard
                  key={persona.id}
                  persona={persona}
                  style={{ animationDelay: `${index * 100}ms` }}
                />
              ))}
            </div>
          ) : (
            <div className="card text-center py-16">
              <div className="w-16 h-16 rounded-2xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center mx-auto mb-4">
                <Users className="w-8 h-8 text-surface-400" />
              </div>
              <h3 className="font-semibold text-lg text-surface-900 dark:text-surface-100 mb-2">
                No personas yet
              </h3>
              <p className="text-surface-500 dark:text-surface-400 mb-6">
                Create your first AI influencer to get started
              </p>
              <Link href="/personas/new" className="btn-primary inline-flex items-center gap-2">
                <Users className="w-4 h-4" />
                Create Persona
              </Link>
            </div>
          )}
        </div>

        {/* Activity Feed */}
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-pink-100 dark:bg-pink-500/20 flex items-center justify-center">
              <Activity className="w-5 h-5 text-pink-600 dark:text-pink-400" />
            </div>
            <h2 className="text-xl font-display font-bold text-surface-900 dark:text-surface-100">
              Recent Activity
            </h2>
          </div>

          {activitiesLoading ? (
            <div className="card space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div
                  key={i}
                  className="h-16 bg-surface-100 dark:bg-surface-800 rounded-xl animate-pulse"
                />
              ))}
            </div>
          ) : (
            <ActivityFeed activities={activities || []} />
          )}
        </div>
      </div>
    </div>
  );
}
