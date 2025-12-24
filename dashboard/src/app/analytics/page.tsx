"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  TrendingUp,
  Users,
  Heart,
  MessageCircle,
  UserPlus,
  Inbox,
} from "lucide-react";
import { useState } from "react";
import { api, DashboardStats, Persona } from "@/lib/api";
import { clsx } from "clsx";
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  Legend,
} from "recharts";

export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState<"7d" | "30d" | "90d">("7d");

  const { data: stats, isLoading: statsLoading } = useQuery<DashboardStats>({
    queryKey: ["dashboardStats"],
    queryFn: api.getDashboardStats,
  });

  const { data: personas, isLoading: personasLoading } = useQuery<Persona[]>({
    queryKey: ["personas"],
    queryFn: api.getPersonas,
  });

  const isLoading = statsLoading || personasLoading;
  const hasData = stats && (stats.total_followers > 0 || stats.engagements_today > 0 || stats.posts_today > 0);

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
              <BarChart3 className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-3xl font-display font-bold text-surface-900">
              Analytics
            </h1>
          </div>
          <p className="text-surface-500 font-medium">
            Track your AI influencers' performance
          </p>
        </div>

        {/* Time Range Selector */}
        <div className="flex items-center gap-1 p-1 bg-surface-100 rounded-xl">
          {(["7d", "30d", "90d"] as const).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={clsx(
                "px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-300",
                timeRange === range
                  ? "bg-white text-surface-900 shadow-sm"
                  : "text-surface-500 hover:text-surface-700"
              )}
            >
              {range === "7d" ? "7 Days" : range === "30d" ? "30 Days" : "90 Days"}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
        <div className="card animate-slide-up">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 rounded-2xl bg-primary-100 flex items-center justify-center">
              <Users className="w-6 h-6 text-primary-600" />
            </div>
            {stats?.total_followers && stats.total_followers > 0 && (
              <div className="flex items-center gap-1 text-emerald-600 text-sm font-semibold">
                <TrendingUp className="w-4 h-4" />
                --
              </div>
            )}
          </div>
          <p className="text-3xl font-bold text-surface-900">
            {isLoading ? "..." : (stats?.total_followers?.toLocaleString() ?? "0")}
          </p>
          <p className="text-sm text-surface-500 font-medium mt-1">
            Total Followers
          </p>
        </div>

        <div className="card animate-slide-up" style={{ animationDelay: "100ms" }}>
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 rounded-2xl bg-pink-100 flex items-center justify-center">
              <Heart className="w-6 h-6 text-pink-600" />
            </div>
          </div>
          <p className="text-3xl font-bold text-surface-900">
            {isLoading ? "..." : (stats?.engagements_today?.toLocaleString() ?? "0")}
          </p>
          <p className="text-sm text-surface-500 font-medium mt-1">
            Engagements Today
          </p>
        </div>

        <div className="card animate-slide-up" style={{ animationDelay: "200ms" }}>
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 rounded-2xl bg-accent-100 flex items-center justify-center">
              <MessageCircle className="w-6 h-6 text-accent-600" />
            </div>
          </div>
          <p className="text-3xl font-bold text-surface-900">
            {isLoading ? "..." : "0"}
          </p>
          <p className="text-sm text-surface-500 font-medium mt-1">
            Comments Made
          </p>
        </div>

        <div className="card animate-slide-up" style={{ animationDelay: "300ms" }}>
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 rounded-2xl bg-emerald-100 flex items-center justify-center">
              <UserPlus className="w-6 h-6 text-emerald-600" />
            </div>
          </div>
          <p className="text-3xl font-bold text-surface-900">
            {isLoading ? "..." : "0"}
          </p>
          <p className="text-sm text-surface-500 font-medium mt-1">
            New Follows Given
          </p>
        </div>
      </div>

      {/* Charts or Empty State */}
      {!hasData && !isLoading ? (
        <div className="card animate-slide-up text-center py-16">
          <div className="w-16 h-16 rounded-2xl bg-surface-100 flex items-center justify-center mx-auto mb-4">
            <Inbox className="w-8 h-8 text-surface-400" />
          </div>
          <h3 className="text-lg font-display font-bold text-surface-900 mb-2">
            No Analytics Data Yet
          </h3>
          <p className="text-surface-500 max-w-md mx-auto">
            Analytics will appear here once your personas start posting content and engaging with followers.
            Create a persona and generate some content to get started!
          </p>
        </div>
      ) : (
        <>
          {/* Charts */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
            {/* Engagement Chart */}
            <div className="card animate-slide-up" style={{ animationDelay: "400ms" }}>
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-lg font-display font-bold text-surface-900">
                    Daily Engagement
                  </h3>
                  <p className="text-sm text-surface-500 font-medium mt-0.5">
                    Likes, comments, and follows by day
                  </p>
                </div>
              </div>
              <div className="h-72 flex items-center justify-center">
                <p className="text-surface-400">No engagement data available</p>
              </div>
            </div>

            {/* Growth Chart */}
            <div className="card animate-slide-up" style={{ animationDelay: "500ms" }}>
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-lg font-display font-bold text-surface-900">
                    Follower Growth
                  </h3>
                  <p className="text-sm text-surface-500 font-medium mt-0.5">
                    Total followers over time
                  </p>
                </div>
              </div>
              <div className="h-72 flex items-center justify-center">
                <p className="text-surface-400">No growth data available</p>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Top Performing Personas */}
      <div className="card animate-slide-up" style={{ animationDelay: "600ms" }}>
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-display font-bold text-surface-900">
              Your Personas
            </h3>
            <p className="text-sm text-surface-500 font-medium mt-0.5">
              {personas && personas.length > 0 ? "Overview of your AI personas" : "No personas created yet"}
            </p>
          </div>
        </div>
        {personas && personas.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-200">
                  <th className="text-left py-3 px-4 text-xs font-semibold text-surface-500 uppercase tracking-wider">
                    Persona
                  </th>
                  <th className="text-left py-3 px-4 text-xs font-semibold text-surface-500 uppercase tracking-wider">
                    Niche
                  </th>
                  <th className="text-right py-3 px-4 text-xs font-semibold text-surface-500 uppercase tracking-wider">
                    Followers
                  </th>
                  <th className="text-right py-3 px-4 text-xs font-semibold text-surface-500 uppercase tracking-wider">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {personas.map((persona, index) => (
                  <tr
                    key={persona.id}
                    className="border-b border-surface-100 hover:bg-surface-50 transition-colors"
                  >
                    <td className="py-4 px-4">
                      <div className="flex items-center gap-3">
                        <div
                          className={clsx(
                            "w-10 h-10 rounded-xl bg-gradient-to-br flex items-center justify-center text-white font-bold",
                            index === 0
                              ? "from-primary-500 to-accent-500"
                              : index === 1
                              ? "from-pink-500 to-rose-500"
                              : "from-amber-500 to-orange-500"
                          )}
                        >
                          {persona.name.charAt(0)}
                        </div>
                        <span className="font-semibold text-surface-900">
                          {persona.name}
                        </span>
                      </div>
                    </td>
                    <td className="py-4 px-4 text-surface-600">
                      {persona.niche || "General"}
                    </td>
                    <td className="py-4 px-4 text-right font-medium text-surface-700">
                      0
                    </td>
                    <td className="py-4 px-4 text-right">
                      <span className={clsx(
                        "inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-sm font-semibold",
                        persona.is_active 
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-surface-100 text-surface-500"
                      )}>
                        {persona.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-surface-400">
              Create your first persona to see analytics here.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
