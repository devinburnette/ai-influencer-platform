"use client";

import Link from "next/link";
import { Users, Heart, MessageCircle, UserPlus, FileText, ChevronRight, TrendingUp } from "lucide-react";
import { clsx } from "clsx";
import { Persona } from "@/lib/api";

interface PersonaCardProps {
  persona: Persona;
  style?: React.CSSProperties;
  expanded?: boolean;
}

const avatarGradients = [
  "from-primary-500 to-accent-500",
  "from-pink-500 to-rose-500",
  "from-amber-500 to-orange-500",
  "from-emerald-500 to-teal-500",
  "from-blue-500 to-indigo-500",
];

export function PersonaCard({ persona, style, expanded = false }: PersonaCardProps) {
  // Deterministic gradient based on name
  const gradientIndex =
    persona.name.charCodeAt(0) % avatarGradients.length;
  const gradient = avatarGradients[gradientIndex];

  const todayTotal = persona.likes_today + persona.comments_today + persona.follows_today;

  if (expanded) {
    return (
      <Link
        href={`/personas/${persona.id}`}
        className="card-hover animate-slide-up group block overflow-hidden"
        style={style}
      >
        <div className="flex items-start gap-6">
          {/* Avatar */}
          <div
            className={clsx(
              "w-16 h-16 rounded-2xl bg-gradient-to-br flex items-center justify-center text-white font-bold text-xl flex-shrink-0 shadow-lg",
              gradient
            )}
          >
            {persona.name.charAt(0).toUpperCase()}
          </div>

          {/* Main Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-1">
              <h3 className="font-display font-bold text-xl text-surface-900 dark:text-surface-100 truncate">
                {persona.name}
              </h3>
              <span
                className={clsx(
                  "badge",
                  persona.is_active ? "badge-success" : "badge-danger"
                )}
              >
                {persona.is_active ? "Active" : "Paused"}
              </span>
            </div>
            <p className="text-sm text-surface-500 dark:text-surface-400 mb-3">
              {persona.bio}
            </p>
            
            {/* Niche tags */}
            <div className="flex flex-wrap gap-2">
              {persona.niche.map((tag) => (
                <span
                  key={tag}
                  className="px-3 py-1 rounded-lg bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400 text-xs font-semibold"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>

          {/* Performance Stats */}
          <div className="hidden lg:grid grid-cols-4 gap-4 flex-shrink-0">
            {/* Posts */}
            <div className="text-center p-3 rounded-xl bg-surface-50 dark:bg-surface-800/50">
              <div className="flex items-center justify-center gap-1.5 text-primary-500 mb-1">
                <FileText className="w-4 h-4" />
              </div>
              <div className="text-lg font-bold text-surface-900 dark:text-surface-100">
                {persona.post_count}
              </div>
              <div className="text-xs text-surface-500">Posts</div>
            </div>
            
            {/* Likes Today */}
            <div className="text-center p-3 rounded-xl bg-surface-50 dark:bg-surface-800/50">
              <div className="flex items-center justify-center gap-1.5 text-pink-500 mb-1">
                <Heart className="w-4 h-4" />
              </div>
              <div className="text-lg font-bold text-surface-900 dark:text-surface-100">
                {persona.likes_today}
              </div>
              <div className="text-xs text-surface-500">Likes Today</div>
            </div>
            
            {/* Comments Today */}
            <div className="text-center p-3 rounded-xl bg-surface-50 dark:bg-surface-800/50">
              <div className="flex items-center justify-center gap-1.5 text-blue-500 mb-1">
                <MessageCircle className="w-4 h-4" />
              </div>
              <div className="text-lg font-bold text-surface-900 dark:text-surface-100">
                {persona.comments_today}
              </div>
              <div className="text-xs text-surface-500">Comments</div>
            </div>
            
            {/* Follows Today */}
            <div className="text-center p-3 rounded-xl bg-surface-50 dark:bg-surface-800/50">
              <div className="flex items-center justify-center gap-1.5 text-green-500 mb-1">
                <UserPlus className="w-4 h-4" />
              </div>
              <div className="text-lg font-bold text-surface-900 dark:text-surface-100">
                {persona.follows_today}
              </div>
              <div className="text-xs text-surface-500">Follows</div>
            </div>
          </div>

          {/* Today's Activity Summary (mobile) */}
          <div className="lg:hidden flex items-center gap-3 flex-shrink-0">
            <div className="text-center">
              <div className="flex items-center gap-1 text-pink-500">
                <TrendingUp className="w-4 h-4" />
                <span className="font-bold text-surface-900 dark:text-surface-100">{todayTotal}</span>
              </div>
              <div className="text-xs text-surface-500">Today</div>
            </div>
          </div>

          {/* Arrow */}
          <div className="flex-shrink-0 text-surface-400 group-hover:text-primary-500 transition-colors self-center">
            <ChevronRight className="w-5 h-5" />
          </div>
        </div>
      </Link>
    );
  }

  // Compact version (original)
  return (
    <Link
      href={`/personas/${persona.id}`}
      className="card-hover flex items-center gap-6 animate-slide-up group"
      style={style}
    >
      {/* Avatar */}
      <div
        className={clsx(
          "w-16 h-16 rounded-2xl bg-gradient-to-br flex items-center justify-center text-white font-bold text-xl flex-shrink-0 shadow-lg",
          gradient
        )}
      >
        {persona.name.charAt(0).toUpperCase()}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 mb-1.5">
          <h3 className="font-display font-bold text-lg text-surface-900 dark:text-surface-100 truncate">
            {persona.name}
          </h3>
          <span
            className={clsx(
              "badge",
              persona.is_active ? "badge-success" : "badge-danger"
            )}
          >
            {persona.is_active ? "Active" : "Paused"}
          </span>
        </div>
        <p className="text-sm text-surface-500 dark:text-surface-400 truncate mb-2.5">
          {persona.bio}
        </p>
        <div className="flex items-center gap-5 text-sm">
          <span className="flex items-center gap-1.5 text-surface-600 dark:text-surface-400 font-medium">
            <Users className="w-4 h-4" />
            {persona.follower_count.toLocaleString()} followers
          </span>
          <span className="flex items-center gap-1.5 text-surface-600 dark:text-surface-400 font-medium">
            <Heart className="w-4 h-4" />
            {persona.post_count} posts
          </span>
        </div>
      </div>

      {/* Niche tags */}
      <div className="hidden md:flex flex-wrap gap-2 max-w-48">
        {persona.niche.slice(0, 3).map((tag) => (
          <span
            key={tag}
            className="px-3 py-1.5 rounded-lg bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400 text-xs font-semibold"
          >
            {tag}
          </span>
        ))}
        {persona.niche.length > 3 && (
          <span className="px-3 py-1.5 rounded-lg bg-surface-100 dark:bg-surface-800 text-surface-500 text-xs font-semibold">
            +{persona.niche.length - 3}
          </span>
        )}
      </div>

      {/* Arrow */}
      <div className="flex-shrink-0 text-surface-400 group-hover:text-primary-500 transition-colors">
        <ChevronRight className="w-5 h-5" />
      </div>
    </Link>
  );
}
