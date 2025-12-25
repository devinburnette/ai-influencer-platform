"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  Users,
  Heart,
  MessageCircle,
  FileText,
  ExternalLink,
} from "lucide-react";
import { api, DashboardStats, Persona, PlatformAccount } from "@/lib/api";
import { clsx } from "clsx";
import Link from "next/link";

// Platform icons
const InstagramIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
  </svg>
);

const TwitterIcon = () => (
  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
  </svg>
);

interface PersonaWithAccounts extends Persona {
  accounts?: PlatformAccount[];
}

function PersonaAnalyticsCard({ persona, accounts }: { persona: Persona; accounts: PlatformAccount[] }) {
  const instagramAccount = accounts.find(a => a.platform === "instagram" && a.is_connected);
  const twitterAccount = accounts.find(a => a.platform === "twitter" && a.is_connected);
  
  return (
    <div className="card animate-slide-up">
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center text-white font-bold text-lg">
            {persona.name.charAt(0)}
          </div>
          <div>
            <h3 className="font-display font-bold text-surface-900">{persona.name}</h3>
            <p className="text-sm text-surface-500">{persona.niche?.join(", ") || "General"}</p>
          </div>
        </div>
        <Link 
          href={`/personas/${persona.id}`}
          className="text-sm text-primary-600 hover:text-primary-700 font-medium flex items-center gap-1"
        >
          View Details
          <ExternalLink className="w-3 h-3" />
        </Link>
      </div>
      
      {/* Platform Stats */}
      <div className="space-y-4">
        {/* Instagram */}
        {instagramAccount ? (
          <div className="p-4 rounded-xl bg-gradient-to-r from-pink-50 to-purple-50 border border-pink-100">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-6 h-6 rounded-full bg-gradient-to-br from-pink-500 via-purple-500 to-orange-400 flex items-center justify-center text-white">
                <InstagramIcon />
              </div>
              <span className="font-semibold text-surface-700">Instagram</span>
              <span className="text-sm text-surface-500">@{instagramAccount.username}</span>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <p className="text-2xl font-bold text-surface-900">{(instagramAccount.follower_count ?? 0).toLocaleString()}</p>
                <p className="text-xs text-surface-500 font-medium">Followers</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-surface-900">{(instagramAccount.following_count ?? 0).toLocaleString()}</p>
                <p className="text-xs text-surface-500 font-medium">Following</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-surface-900">{instagramAccount.post_count ?? 0}</p>
                <p className="text-xs text-surface-500 font-medium">Posts</p>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-4 rounded-xl bg-surface-50 border border-surface-200 border-dashed">
            <div className="flex items-center gap-2 text-surface-400">
              <InstagramIcon />
              <span className="text-sm">Instagram not connected</span>
            </div>
          </div>
        )}
        
        {/* Twitter */}
        {twitterAccount ? (
          <div className="p-4 rounded-xl bg-surface-50 border border-surface-200">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-6 h-6 rounded-full bg-black flex items-center justify-center text-white">
                <TwitterIcon />
              </div>
              <span className="font-semibold text-surface-700">X (Twitter)</span>
              <span className="text-sm text-surface-500">@{twitterAccount.username}</span>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <p className="text-2xl font-bold text-surface-900">{(twitterAccount.follower_count ?? 0).toLocaleString()}</p>
                <p className="text-xs text-surface-500 font-medium">Followers</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-surface-900">{(twitterAccount.following_count ?? 0).toLocaleString()}</p>
                <p className="text-xs text-surface-500 font-medium">Following</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-surface-900">{twitterAccount.post_count ?? 0}</p>
                <p className="text-xs text-surface-500 font-medium">Posts</p>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-4 rounded-xl bg-surface-50 border border-surface-200 border-dashed">
            <div className="flex items-center gap-2 text-surface-400">
              <TwitterIcon />
              <span className="text-sm">X (Twitter) not connected</span>
            </div>
          </div>
        )}
      </div>
      
      {/* Engagement Activity Today */}
      <div className="mt-6 pt-6 border-t border-surface-100">
        <h4 className="text-sm font-semibold text-surface-700 mb-3">Today's Activity</h4>
        <div className="grid grid-cols-3 gap-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-pink-100 flex items-center justify-center">
              <Heart className="w-4 h-4 text-pink-600" />
            </div>
            <div>
              <p className="font-bold text-surface-900">{persona.likes_today}</p>
              <p className="text-xs text-surface-500">Likes</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
              <MessageCircle className="w-4 h-4 text-blue-600" />
            </div>
            <div>
              <p className="font-bold text-surface-900">{persona.comments_today}</p>
              <p className="text-xs text-surface-500">Comments</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center">
              <Users className="w-4 h-4 text-emerald-600" />
            </div>
            <div>
              <p className="font-bold text-surface-900">{persona.follows_today}</p>
              <p className="text-xs text-surface-500">Follows</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const { data: stats, isLoading: statsLoading } = useQuery<DashboardStats>({
    queryKey: ["dashboardStats"],
    queryFn: api.getDashboardStats,
  });

  const { data: personas, isLoading: personasLoading } = useQuery<Persona[]>({
    queryKey: ["personas"],
    queryFn: api.getPersonas,
  });

  // Fetch platform accounts for all personas
  const { data: allAccounts } = useQuery({
    queryKey: ["allPlatformAccounts", personas?.map(p => p.id)],
    queryFn: async () => {
      if (!personas) return {};
      const accountsMap: Record<string, PlatformAccount[]> = {};
      await Promise.all(
        personas.map(async (persona) => {
          try {
            accountsMap[persona.id] = await api.getPlatformAccounts(persona.id);
          } catch {
            accountsMap[persona.id] = [];
          }
        })
      );
      return accountsMap;
    },
    enabled: !!personas && personas.length > 0,
  });

  const isLoading = statsLoading || personasLoading;

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
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
          Track your AI influencers' performance by platform
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
        <div className="card animate-slide-up">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 rounded-2xl bg-primary-100 flex items-center justify-center">
              <Users className="w-6 h-6 text-primary-600" />
            </div>
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
            {isLoading ? "..." : (stats?.total_engagement_received?.toLocaleString() ?? "0")}
          </p>
          <p className="text-sm text-surface-500 font-medium mt-1">
            Engagement Received
          </p>
        </div>

        <div className="card animate-slide-up" style={{ animationDelay: "200ms" }}>
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 rounded-2xl bg-accent-100 flex items-center justify-center">
              <FileText className="w-6 h-6 text-accent-600" />
            </div>
          </div>
          <p className="text-3xl font-bold text-surface-900">
            {isLoading ? "..." : (stats?.total_posts?.toLocaleString() ?? "0")}
          </p>
          <p className="text-sm text-surface-500 font-medium mt-1">
            Posts Published
          </p>
        </div>

        <div className="card animate-slide-up" style={{ animationDelay: "300ms" }}>
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 rounded-2xl bg-amber-100 flex items-center justify-center">
              <BarChart3 className="w-6 h-6 text-amber-600" />
            </div>
          </div>
          <p className="text-3xl font-bold text-surface-900">
            {isLoading ? "..." : (stats?.engagements_today?.toLocaleString() ?? "0")}
          </p>
          <p className="text-sm text-surface-500 font-medium mt-1">
            Engagements Today
          </p>
        </div>
      </div>

      {/* Per-Persona Analytics */}
      <div>
        <h2 className="text-xl font-display font-bold text-surface-900 mb-4">
          Persona Performance
        </h2>
        {!personas || personas.length === 0 ? (
          <div className="card text-center py-12">
            <Users className="w-12 h-12 text-surface-300 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-surface-700 mb-2">No Personas Yet</h3>
            <p className="text-surface-500 mb-4">Create your first AI persona to see analytics.</p>
            <Link href="/personas/new" className="btn-primary">
              Create Persona
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {personas.map((persona) => (
              <PersonaAnalyticsCard
                key={persona.id}
                persona={persona}
                accounts={allAccounts?.[persona.id] || []}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
