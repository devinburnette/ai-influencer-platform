"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Heart,
  MessageCircle,
  UserPlus,
  UserMinus,
  Settings2,
  Play,
  Pause,
  RefreshCw,
  TrendingUp,
  Clock,
  Target,
  Zap,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Filter,
  ChevronDown,
  ExternalLink,
} from "lucide-react";
import { useState } from "react";
import { api, Persona, ActivityLogEntry } from "@/lib/api";
import { formatDistanceToNow, format } from "date-fns";
import { clsx } from "clsx";

// Engagement settings interface
interface EngagementSettings {
  persona_id: string;
  auto_like: boolean;
  auto_comment: boolean;
  auto_follow: boolean;
  daily_likes_limit: number;
  daily_comments_limit: number;
  daily_follows_limit: number;
  engagement_strategy: "balanced" | "aggressive" | "niche_expert";
  target_hashtags: string[];
}

// Engagement history item
interface EngagementActivity {
  id: string;
  persona_id: string;
  persona_name: string;
  engagement_type: "like" | "comment" | "follow" | "unfollow";
  target_username: string | null;
  target_url: string | null;
  comment_text: string | null;
  success: boolean;
  error_message: string | null;
  created_at: string;
}

const strategyInfo = {
  balanced: {
    name: "Balanced",
    description: "Steady, organic growth with moderate activity",
    icon: Target,
    color: "text-blue-600 dark:text-blue-400",
    bgColor: "bg-blue-100 dark:bg-blue-500/20",
  },
  aggressive: {
    name: "Aggressive",
    description: "Rapid growth with high activity (use carefully)",
    icon: Zap,
    color: "text-orange-600 dark:text-orange-400",
    bgColor: "bg-orange-100 dark:bg-orange-500/20",
  },
  niche_expert: {
    name: "Niche Expert",
    description: "Quality over quantity, focused on building authority",
    icon: TrendingUp,
    color: "text-purple-600 dark:text-purple-400",
    bgColor: "bg-purple-100 dark:bg-purple-500/20",
  },
};

const engagementTypeConfig = {
  like: {
    icon: Heart,
    label: "Like",
    color: "text-pink-500",
    bgColor: "bg-pink-100 dark:bg-pink-500/20",
  },
  comment: {
    icon: MessageCircle,
    label: "Comment",
    color: "text-blue-500",
    bgColor: "bg-blue-100 dark:bg-blue-500/20",
  },
  follow: {
    icon: UserPlus,
    label: "Follow",
    color: "text-emerald-500",
    bgColor: "bg-emerald-100 dark:bg-emerald-500/20",
  },
  unfollow: {
    icon: UserMinus,
    label: "Unfollow",
    color: "text-surface-500",
    bgColor: "bg-surface-100 dark:bg-surface-500/20",
  },
};

function EngagementCard({
  persona,
  onOpenSettings,
  onTriggerEngagement,
  isTriggering,
}: {
  persona: Persona;
  onOpenSettings: (persona: Persona) => void;
  onTriggerEngagement: (persona: Persona) => void;
  isTriggering: boolean;
}) {
  // Real stats from persona - would be extended with API data
  const stats = {
    likes_today: (persona as any).likes_today || 0,
    comments_today: (persona as any).comments_today || 0,
    follows_today: (persona as any).follows_today || 0,
    likes_limit: 100,
    comments_limit: 30,
    follows_limit: 20,
  };

  return (
    <div className="card p-6">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary-400 to-accent-400 flex items-center justify-center text-white font-bold text-lg shadow-lg">
            {persona.name.charAt(0)}
          </div>
          <div>
            <h3 className="font-semibold text-surface-900 dark:text-surface-100">
              {persona.name}
            </h3>
            <p className="text-sm text-surface-500 dark:text-surface-400">
              {persona.niche.slice(0, 2).join(", ")}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={clsx(
              "px-2.5 py-1 rounded-full text-xs font-semibold",
              persona.is_active
                ? "bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400"
                : "bg-surface-100 dark:bg-surface-700 text-surface-500"
            )}
          >
            {persona.is_active ? "Active" : "Paused"}
          </span>
          <button
            onClick={() => onTriggerEngagement(persona)}
            disabled={isTriggering || !persona.is_active}
            className={clsx(
              "p-2 rounded-lg transition-colors",
              isTriggering 
                ? "bg-primary-100 dark:bg-primary-500/20 text-primary-600 dark:text-primary-400"
                : persona.is_active
                  ? "hover:bg-primary-100 dark:hover:bg-primary-500/20 text-surface-400 hover:text-primary-600 dark:hover:text-primary-400"
                  : "text-surface-300 dark:text-surface-600 cursor-not-allowed"
            )}
            title={!persona.is_active ? "Activate persona first" : "Run engagement now"}
          >
            {isTriggering ? (
              <RefreshCw className="w-5 h-5 animate-spin" />
            ) : (
              <Play className="w-5 h-5" />
            )}
          </button>
          <button
            onClick={() => onOpenSettings(persona)}
            className="p-2 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors"
          >
            <Settings2 className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Daily Progress */}
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <Heart className="w-4 h-4 text-pink-500" />
          <div className="flex-1">
            <div className="flex justify-between text-sm mb-1">
              <span className="text-surface-600 dark:text-surface-400">Likes</span>
              <span className="font-medium text-surface-900 dark:text-surface-100">
                {stats.likes_today} / {stats.likes_limit}
              </span>
            </div>
            <div className="h-2 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-pink-400 to-pink-500 rounded-full transition-all"
                style={{ width: `${(stats.likes_today / stats.likes_limit) * 100}%` }}
              />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <MessageCircle className="w-4 h-4 text-blue-500" />
          <div className="flex-1">
            <div className="flex justify-between text-sm mb-1">
              <span className="text-surface-600 dark:text-surface-400">Comments</span>
              <span className="font-medium text-surface-900 dark:text-surface-100">
                {stats.comments_today} / {stats.comments_limit}
              </span>
            </div>
            <div className="h-2 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-blue-400 to-blue-500 rounded-full transition-all"
                style={{ width: `${(stats.comments_today / stats.comments_limit) * 100}%` }}
              />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <UserPlus className="w-4 h-4 text-emerald-500" />
          <div className="flex-1">
            <div className="flex justify-between text-sm mb-1">
              <span className="text-surface-600 dark:text-surface-400">Follows</span>
              <span className="font-medium text-surface-900 dark:text-surface-100">
                {stats.follows_today} / {stats.follows_limit}
              </span>
            </div>
            <div className="h-2 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-emerald-400 to-emerald-500 rounded-full transition-all"
                style={{ width: `${(stats.follows_today / stats.follows_limit) * 100}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Engagement Hours */}
      <div className="mt-4 pt-4 border-t border-surface-200 dark:border-surface-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-surface-500 dark:text-surface-400">
            <Clock className="w-4 h-4" />
            <span>
              Active hours: {persona.engagement_hours_start}:00 - {persona.engagement_hours_end}:00
            </span>
          </div>
          <span className="text-xs text-surface-400">
            Edit in persona settings
          </span>
        </div>
      </div>
    </div>
  );
}

function SettingsModal({
  persona,
  onClose,
  onSave,
}: {
  persona: Persona;
  onClose: () => void;
  onSave: (settings: Partial<EngagementSettings>) => void;
}) {
  const [settings, setSettings] = useState<Partial<EngagementSettings>>({
    auto_like: true,
    auto_comment: true,
    auto_follow: true,
    daily_likes_limit: 100,
    daily_comments_limit: 30,
    daily_follows_limit: 20,
    engagement_strategy: "balanced",
    target_hashtags: persona.niche,
  });

  const [newHashtag, setNewHashtag] = useState("");

  const addHashtag = () => {
    if (newHashtag.trim() && !settings.target_hashtags?.includes(newHashtag.trim())) {
      setSettings({
        ...settings,
        target_hashtags: [...(settings.target_hashtags || []), newHashtag.trim()],
      });
      setNewHashtag("");
    }
  };

  const removeHashtag = (tag: string) => {
    setSettings({
      ...settings,
      target_hashtags: settings.target_hashtags?.filter((t) => t !== tag),
    });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-surface-900 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-surface-200 dark:border-surface-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-400 to-accent-400 flex items-center justify-center text-white font-bold shadow-lg">
              {persona.name.charAt(0)}
            </div>
            <div>
              <h2 className="font-semibold text-surface-900 dark:text-surface-100">
                Engagement Settings
              </h2>
              <p className="text-sm text-surface-500">{persona.name}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl hover:bg-surface-100 dark:hover:bg-surface-800 text-surface-400 hover:text-surface-600 transition-colors"
          >
            <XCircle className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[60vh] space-y-6">
          {/* Auto-engagement toggles */}
          <div>
            <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 mb-3">
              Auto-Engagement Features
            </h3>
            <div className="space-y-3">
              <label className="flex items-center justify-between p-3 rounded-xl bg-surface-50 dark:bg-surface-800 cursor-pointer">
                <div className="flex items-center gap-3">
                  <Heart className="w-5 h-5 text-pink-500" />
                  <div>
                    <p className="font-medium text-surface-900 dark:text-surface-100">Auto-Like</p>
                    <p className="text-sm text-surface-500">Automatically like relevant posts</p>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={settings.auto_like}
                  onChange={(e) => setSettings({ ...settings, auto_like: e.target.checked })}
                  className="w-5 h-5 rounded text-primary-500 focus:ring-primary-500"
                />
              </label>

              <label className="flex items-center justify-between p-3 rounded-xl bg-surface-50 dark:bg-surface-800 cursor-pointer">
                <div className="flex items-center gap-3">
                  <MessageCircle className="w-5 h-5 text-blue-500" />
                  <div>
                    <p className="font-medium text-surface-900 dark:text-surface-100">Auto-Comment</p>
                    <p className="text-sm text-surface-500">Generate and post relevant comments</p>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={settings.auto_comment}
                  onChange={(e) => setSettings({ ...settings, auto_comment: e.target.checked })}
                  className="w-5 h-5 rounded text-primary-500 focus:ring-primary-500"
                />
              </label>

              <label className="flex items-center justify-between p-3 rounded-xl bg-surface-50 dark:bg-surface-800 cursor-pointer">
                <div className="flex items-center gap-3">
                  <UserPlus className="w-5 h-5 text-emerald-500" />
                  <div>
                    <p className="font-medium text-surface-900 dark:text-surface-100">Auto-Follow</p>
                    <p className="text-sm text-surface-500">Follow users in your niche</p>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={settings.auto_follow}
                  onChange={(e) => setSettings({ ...settings, auto_follow: e.target.checked })}
                  className="w-5 h-5 rounded text-primary-500 focus:ring-primary-500"
                />
              </label>
            </div>
          </div>

          {/* Daily Limits */}
          <div>
            <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 mb-3">
              Daily Limits
            </h3>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm text-surface-600 dark:text-surface-400 mb-1">
                  Likes
                </label>
                <input
                  type="number"
                  value={settings.daily_likes_limit}
                  onChange={(e) =>
                    setSettings({ ...settings, daily_likes_limit: parseInt(e.target.value) || 0 })
                  }
                  min={0}
                  max={200}
                  className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
                />
              </div>
              <div>
                <label className="block text-sm text-surface-600 dark:text-surface-400 mb-1">
                  Comments
                </label>
                <input
                  type="number"
                  value={settings.daily_comments_limit}
                  onChange={(e) =>
                    setSettings({ ...settings, daily_comments_limit: parseInt(e.target.value) || 0 })
                  }
                  min={0}
                  max={50}
                  className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
                />
              </div>
              <div>
                <label className="block text-sm text-surface-600 dark:text-surface-400 mb-1">
                  Follows
                </label>
                <input
                  type="number"
                  value={settings.daily_follows_limit}
                  onChange={(e) =>
                    setSettings({ ...settings, daily_follows_limit: parseInt(e.target.value) || 0 })
                  }
                  min={0}
                  max={50}
                  className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
                />
              </div>
            </div>
          </div>

          {/* Engagement Strategy */}
          <div>
            <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 mb-3">
              Engagement Strategy
            </h3>
            <div className="space-y-2">
              {Object.entries(strategyInfo).map(([key, info]) => {
                const StrategyIcon = info.icon;
                return (
                  <label
                    key={key}
                    className={clsx(
                      "flex items-center gap-3 p-3 rounded-xl cursor-pointer border-2 transition-all",
                      settings.engagement_strategy === key
                        ? "border-primary-500 bg-primary-50 dark:bg-primary-500/10"
                        : "border-transparent bg-surface-50 dark:bg-surface-800 hover:border-surface-300 dark:hover:border-surface-600"
                    )}
                  >
                    <input
                      type="radio"
                      name="strategy"
                      value={key}
                      checked={settings.engagement_strategy === key}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          engagement_strategy: e.target.value as EngagementSettings["engagement_strategy"],
                        })
                      }
                      className="sr-only"
                    />
                    <div className={clsx("p-2 rounded-lg", info.bgColor)}>
                      <StrategyIcon className={clsx("w-5 h-5", info.color)} />
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-surface-900 dark:text-surface-100">
                        {info.name}
                      </p>
                      <p className="text-sm text-surface-500">{info.description}</p>
                    </div>
                    {settings.engagement_strategy === key && (
                      <CheckCircle className="w-5 h-5 text-primary-500" />
                    )}
                  </label>
                );
              })}
            </div>
          </div>

          {/* Target Hashtags */}
          <div>
            <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 mb-3">
              Target Hashtags
            </h3>
            <div className="flex gap-2 mb-3">
              <input
                type="text"
                value={newHashtag}
                onChange={(e) => setNewHashtag(e.target.value.replace(/^#/, ""))}
                onKeyDown={(e) => e.key === "Enter" && addHashtag()}
                placeholder="Add a hashtag..."
                className="flex-1 px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
              />
              <button
                onClick={addHashtag}
                className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors"
              >
                Add
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {settings.target_hashtags?.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-primary-100 dark:bg-primary-500/20 text-primary-700 dark:text-primary-300 text-sm"
                >
                  #{tag}
                  <button
                    onClick={() => removeHashtag(tag)}
                    className="ml-1 hover:text-primary-900 dark:hover:text-primary-100"
                  >
                    <XCircle className="w-4 h-4" />
                  </button>
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-5 border-t border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-sm font-semibold text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              onSave(settings);
              onClose();
            }}
            className="btn-primary text-sm px-6"
          >
            Save Settings
          </button>
        </div>
      </div>
    </div>
  );
}

function ActivityItem({ activity }: { activity: EngagementActivity }) {
  const config = engagementTypeConfig[activity.engagement_type] || engagementTypeConfig.like;
  const Icon = config.icon;

  return (
    <div className="flex items-start gap-3 p-3 rounded-xl hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors">
      <div className={clsx("p-2 rounded-lg", config.bgColor)}>
        <Icon className={clsx("w-4 h-4", config.color)} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-surface-900 dark:text-surface-100">
            {activity.persona_name}
          </span>
          <span className="text-surface-500">
            {activity.engagement_type === "like" && "liked a post"}
            {activity.engagement_type === "comment" && "commented"}
            {activity.engagement_type === "follow" && "followed"}
            {activity.engagement_type === "unfollow" && "unfollowed"}
          </span>
          {activity.target_username && (
            <span className="text-primary-600 dark:text-primary-400">
              @{activity.target_username}
            </span>
          )}
        </div>
        {activity.comment_text && (
          <p className="text-sm text-surface-600 dark:text-surface-400 mt-1 truncate">
            "{activity.comment_text}"
          </p>
        )}
        <div className="flex items-center gap-2 mt-1">
          <span className="text-xs text-surface-400">
            {formatDistanceToNow(new Date(activity.created_at + (activity.created_at.endsWith('Z') ? '' : 'Z')), { addSuffix: true })}
          </span>
          {!activity.success && (
            <span className="inline-flex items-center gap-1 text-xs text-red-500">
              <XCircle className="w-3 h-3" />
              Failed
            </span>
          )}
          {activity.target_url && (
            <a
              href={activity.target_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-primary-500 hover:text-primary-600 flex items-center gap-1"
            >
              View <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

export default function EngagementPage() {
  const [settingsPersona, setSettingsPersona] = useState<Persona | null>(null);
  const [activityFilter, setActivityFilter] = useState<string>("all");
  const [triggeringPersonaId, setTriggeringPersonaId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: personas, isLoading: personasLoading } = useQuery({
    queryKey: ["personas"],
    queryFn: api.getPersonas,
  });

  // Fetch engagement activity log
  const { data: activityLog, isLoading: activityLoading } = useQuery({
    queryKey: ["activity-log"],
    queryFn: () => api.getActivityLog(100),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Mutation for triggering engagement
  const triggerEngagementMutation = useMutation({
    mutationFn: (personaId: string) => api.triggerEngagement(personaId),
    onMutate: (personaId) => {
      setTriggeringPersonaId(personaId);
    },
    onSuccess: (data) => {
      // Show success message (could be a toast)
      console.log("Engagement triggered:", data.message);
      // Refresh data after a delay to show updated counts
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ["personas"] });
        queryClient.invalidateQueries({ queryKey: ["activity-log"] });
      }, 5000);
    },
    onError: (error: any) => {
      console.error("Failed to trigger engagement:", error);
      alert(error.response?.data?.detail || "Failed to trigger engagement");
    },
    onSettled: () => {
      setTriggeringPersonaId(null);
    },
  });

  // Transform activity log to EngagementActivity format
  const activityData: EngagementActivity[] = (activityLog || []).map((entry: ActivityLogEntry) => ({
    id: entry.id,
    persona_id: entry.persona_id,
    persona_name: entry.persona_name,
    engagement_type: entry.action_type as EngagementActivity["engagement_type"],
    target_username: null,
    target_url: entry.target_url,
    comment_text: entry.details,
    success: true, // If it's in the log, it succeeded
    error_message: null,
    created_at: entry.created_at,
  }));

  const handleSaveSettings = (settings: Partial<EngagementSettings>) => {
    console.log("Saving settings:", settings);
    // TODO: Save via API
  };

  const handleTriggerEngagement = (persona: Persona) => {
    triggerEngagementMutation.mutate(persona.id);
  };

  // Calculate overall stats from personas
  const totalLikesToday = personas?.reduce((sum, p) => sum + ((p as any).likes_today || 0), 0) || 0;
  const totalCommentsToday = personas?.reduce((sum, p) => sum + ((p as any).comments_today || 0), 0) || 0;
  const totalFollowsToday = personas?.reduce((sum, p) => sum + ((p as any).follows_today || 0), 0) || 0;

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Settings Modal */}
      {settingsPersona && (
        <SettingsModal
          persona={settingsPersona}
          onClose={() => setSettingsPersona(null)}
          onSave={handleSaveSettings}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-surface-900 dark:text-surface-100">
            Engagement
          </h1>
          <p className="text-surface-500 dark:text-surface-400 mt-1">
            Manage auto-engagement settings for your personas
          </p>
        </div>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card p-6">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-pink-100 dark:bg-pink-500/20">
              <Heart className="w-6 h-6 text-pink-500" />
            </div>
            <div>
              <p className="text-sm text-surface-500 dark:text-surface-400">Likes Today</p>
              <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                {totalLikesToday}
              </p>
            </div>
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-blue-100 dark:bg-blue-500/20">
              <MessageCircle className="w-6 h-6 text-blue-500" />
            </div>
            <div>
              <p className="text-sm text-surface-500 dark:text-surface-400">Comments Today</p>
              <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                {totalCommentsToday}
              </p>
            </div>
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl bg-emerald-100 dark:bg-emerald-500/20">
              <UserPlus className="w-6 h-6 text-emerald-500" />
            </div>
            <div>
              <p className="text-sm text-surface-500 dark:text-surface-400">Follows Today</p>
              <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">
                {totalFollowsToday}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
        {/* Personas Section - Takes more space */}
        <div className="lg:col-span-3 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
              Personas
            </h2>
          </div>

          {personasLoading ? (
            <div className="space-y-4">
              {[...Array(2)].map((_, i) => (
                <div key={i} className="card p-6 animate-pulse">
                  <div className="h-12 bg-surface-200 dark:bg-surface-700 rounded-xl mb-4" />
                  <div className="space-y-3">
                    <div className="h-8 bg-surface-200 dark:bg-surface-700 rounded" />
                    <div className="h-8 bg-surface-200 dark:bg-surface-700 rounded" />
                    <div className="h-8 bg-surface-200 dark:bg-surface-700 rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : personas && personas.length > 0 ? (
            <div className="space-y-4">
              {personas.map((persona) => (
                <EngagementCard
                  key={persona.id}
                  persona={persona}
                  onOpenSettings={setSettingsPersona}
                  onTriggerEngagement={handleTriggerEngagement}
                  isTriggering={triggeringPersonaId === persona.id}
                />
              ))}
            </div>
          ) : (
            <div className="card p-12 text-center">
              <Heart className="w-12 h-12 text-surface-300 dark:text-surface-600 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-2">
                No Personas Yet
              </h3>
              <p className="text-surface-500 dark:text-surface-400">
                Create a persona to start configuring engagement settings.
              </p>
            </div>
          )}
        </div>

        {/* Activity Feed - Compact */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100">
              Recent Activity
            </h2>
            <select
              value={activityFilter}
              onChange={(e) => setActivityFilter(e.target.value)}
              className="text-sm px-3 py-1.5 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-700 dark:text-surface-300"
            >
              <option value="all">All</option>
              <option value="like">Likes</option>
              <option value="comment">Comments</option>
              <option value="follow">Follows</option>
            </select>
          </div>

          <div className="card divide-y divide-surface-200 dark:divide-surface-700 max-h-96 overflow-y-auto">
            {activityData.length > 0 ? (
              activityData
                .filter((a) => activityFilter === "all" || a.engagement_type === activityFilter)
                .slice(0, 10)
                .map((activity) => <ActivityItem key={activity.id} activity={activity} />)
            ) : (
              <div className="p-8 text-center">
                <Heart className="w-8 h-8 text-surface-300 dark:text-surface-600 mx-auto mb-3" />
                <p className="text-surface-500 dark:text-surface-400">No engagement activity yet</p>
                <p className="text-xs text-surface-400 mt-1">
                  Activity will appear here once auto-engagement is enabled
                </p>
              </div>
            )}
          </div>

          {/* Info Card */}
          <div className="card p-4 bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-500/10 dark:to-orange-500/10 border border-amber-200 dark:border-amber-500/20">
            <div className="flex gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="font-semibold text-amber-800 dark:text-amber-300 text-sm">
                  Rate Limit Protection
                </h4>
                <p className="text-sm text-amber-700 dark:text-amber-400 mt-1">
                  Actions are throttled to prevent restrictions.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

