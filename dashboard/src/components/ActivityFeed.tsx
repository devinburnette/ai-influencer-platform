"use client";

import { Heart, MessageCircle, UserPlus, Eye } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { clsx } from "clsx";
import { ActivityLogEntry } from "@/lib/api";

interface ActivityFeedProps {
  activities: ActivityLogEntry[];
}

const actionConfig: Record<
  string,
  { icon: typeof Heart; color: string; bgColor: string; label: string }
> = {
  like: {
    icon: Heart,
    color: "text-pink-600 dark:text-pink-400",
    bgColor: "bg-pink-100 dark:bg-pink-500/20",
    label: "Liked a post",
  },
  comment: {
    icon: MessageCircle,
    color: "text-primary-600 dark:text-primary-400",
    bgColor: "bg-primary-100 dark:bg-primary-500/20",
    label: "Commented on a post",
  },
  follow: {
    icon: UserPlus,
    color: "text-emerald-600 dark:text-emerald-400",
    bgColor: "bg-emerald-100 dark:bg-emerald-500/20",
    label: "Followed",
  },
  unfollow: {
    icon: UserPlus,
    color: "text-surface-500",
    bgColor: "bg-surface-100 dark:bg-surface-700",
    label: "Unfollowed",
  },
  story_view: {
    icon: Eye,
    color: "text-amber-600 dark:text-amber-400",
    bgColor: "bg-amber-100 dark:bg-amber-500/20",
    label: "Viewed story",
  },
  story_reaction: {
    icon: Heart,
    color: "text-amber-600 dark:text-amber-400",
    bgColor: "bg-amber-100 dark:bg-amber-500/20",
    label: "Reacted to story",
  },
};

export function ActivityFeed({ activities }: ActivityFeedProps) {
  if (activities.length === 0) {
    return (
      <div className="card text-center py-12">
        <p className="text-surface-500 dark:text-surface-400 font-medium">
          No recent activity
        </p>
      </div>
    );
  }

  return (
    <div className="card space-y-1 max-h-[500px] overflow-y-auto">
      {activities.map((activity, index) => {
        const config = actionConfig[activity.action_type] || actionConfig.like;
        const Icon = config.icon;

        return (
          <div
            key={activity.id}
            className="flex items-start gap-4 p-3 rounded-xl hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors animate-slide-up"
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <div
              className={clsx(
                "w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0",
                config.bgColor
              )}
            >
              <Icon className={clsx("w-5 h-5", config.color)} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-surface-700 dark:text-surface-200">
                <span className="font-semibold text-surface-900 dark:text-surface-100">
                  {activity.persona_name}
                </span>{" "}
                {config.label.toLowerCase()}
                {activity.details && (
                  <span className="text-surface-500 dark:text-surface-400">
                    : "{activity.details.slice(0, 40)}
                    {activity.details.length > 40 ? "..." : ""}"
                  </span>
                )}
              </p>
              <p className="text-xs text-surface-400 dark:text-surface-500 mt-1 font-medium">
                {formatDistanceToNow(new Date(activity.created_at), {
                  addSuffix: true,
                })}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
