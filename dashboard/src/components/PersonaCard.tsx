"use client";

import Link from "next/link";
import { Users, Heart, Play, Pause, ChevronRight } from "lucide-react";
import { clsx } from "clsx";
import { Persona } from "@/lib/api";

interface PersonaCardProps {
  persona: Persona;
  style?: React.CSSProperties;
}

const avatarGradients = [
  "from-primary-500 to-accent-500",
  "from-pink-500 to-rose-500",
  "from-amber-500 to-orange-500",
  "from-emerald-500 to-teal-500",
  "from-blue-500 to-indigo-500",
];

export function PersonaCard({ persona, style }: PersonaCardProps) {
  // Deterministic gradient based on name
  const gradientIndex =
    persona.name.charCodeAt(0) % avatarGradients.length;
  const gradient = avatarGradients[gradientIndex];

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
