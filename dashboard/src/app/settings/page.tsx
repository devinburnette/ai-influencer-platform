"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Settings,
  Key,
  Bell,
  Shield,
  Zap,
  Save,
  Check,
  ExternalLink,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  RefreshCw,
} from "lucide-react";
import { clsx } from "clsx";

interface SettingSection {
  id: string;
  title: string;
  description: string;
  icon: typeof Settings;
  color: string;
}

interface ApiKeysStatus {
  openai_configured: boolean;
  anthropic_configured: boolean;
  twitter_configured: boolean;
  meta_configured: boolean;
}

interface AutomationSettings {
  content_generation_hours: number;
  posting_queue_minutes: number;
  engagement_cycle_minutes: number;
  analytics_sync_hour: number;
  daily_reset_hour: number;
}

interface RateLimitsSettings {
  max_posts_per_day: number;
  max_likes_per_day: number;
  max_comments_per_day: number;
  max_follows_per_day: number;
  min_action_delay: number;
  max_action_delay: number;
}

const sections: SettingSection[] = [
  {
    id: "api-keys",
    title: "API Keys",
    description: "Configure AI and platform API credentials",
    icon: Key,
    color: "from-primary-500 to-primary-600",
  },
  {
    id: "automation",
    title: "Automation",
    description: "Schedule settings for content and engagement",
    icon: Clock,
    color: "from-blue-500 to-indigo-500",
  },
  {
    id: "notifications",
    title: "Notifications",
    description: "Manage alert preferences and thresholds",
    icon: Bell,
    color: "from-amber-500 to-orange-500",
  },
  {
    id: "safety",
    title: "Safety Rules",
    description: "Content filters and engagement limits",
    icon: Shield,
    color: "from-emerald-500 to-teal-500",
  },
];

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchApiKeysStatus(): Promise<ApiKeysStatus> {
  const response = await fetch(`${API_URL}/api/settings/api-keys/status`);
  if (!response.ok) {
    throw new Error("Failed to fetch API keys status");
  }
  return response.json();
}

async function fetchAutomationSettings(): Promise<AutomationSettings> {
  const response = await fetch(`${API_URL}/api/settings/automation`);
  if (!response.ok) {
    throw new Error("Failed to fetch automation settings");
  }
  return response.json();
}

async function updateAutomationSettings(settings: Partial<AutomationSettings>): Promise<AutomationSettings> {
  const response = await fetch(`${API_URL}/api/settings/automation`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (!response.ok) {
    throw new Error("Failed to update automation settings");
  }
  return response.json();
}

async function fetchRateLimitsSettings(): Promise<RateLimitsSettings> {
  const response = await fetch(`${API_URL}/api/settings/rate-limits`);
  if (!response.ok) {
    throw new Error("Failed to fetch rate limits settings");
  }
  return response.json();
}

async function updateRateLimitsSettings(settings: Partial<RateLimitsSettings>): Promise<RateLimitsSettings> {
  const response = await fetch(`${API_URL}/api/settings/rate-limits`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (!response.ok) {
    throw new Error("Failed to update rate limits settings");
  }
  return response.json();
}

function StatusBadge({ configured, label }: { configured: boolean; label?: string }) {
  if (configured) {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">
        <CheckCircle className="w-3.5 h-3.5" />
        {label || "Configured"}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-700">
      <AlertCircle className="w-3.5 h-3.5" />
      {label || "Not configured"}
    </span>
  );
}

export default function SettingsPage() {
  const [activeSection, setActiveSection] = useState("api-keys");
  const [saved, setSaved] = useState(false);
  const [automationForm, setAutomationForm] = useState<AutomationSettings | null>(null);
  const [rateLimitsForm, setRateLimitsForm] = useState<RateLimitsSettings | null>(null);
  const queryClient = useQueryClient();

  const { data: apiKeysStatus, isLoading: isLoadingApiKeys } = useQuery<ApiKeysStatus>({
    queryKey: ["api-keys-status"],
    queryFn: fetchApiKeysStatus,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const { data: automationSettings, isLoading: isLoadingAutomation } = useQuery<AutomationSettings>({
    queryKey: ["automation-settings"],
    queryFn: fetchAutomationSettings,
  });

  const { data: rateLimitsSettings, isLoading: isLoadingRateLimits } = useQuery<RateLimitsSettings>({
    queryKey: ["rate-limits-settings"],
    queryFn: fetchRateLimitsSettings,
  });

  // Initialize forms when data loads
  useEffect(() => {
    if (automationSettings && !automationForm) {
      setAutomationForm(automationSettings);
    }
  }, [automationSettings, automationForm]);

  useEffect(() => {
    if (rateLimitsSettings && !rateLimitsForm) {
      setRateLimitsForm(rateLimitsSettings);
    }
  }, [rateLimitsSettings, rateLimitsForm]);

  const updateAutomationMutation = useMutation({
    mutationFn: updateAutomationSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automation-settings"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const updateRateLimitsMutation = useMutation({
    mutationFn: updateRateLimitsSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rate-limits-settings"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const handleSave = () => {
    if (activeSection === "automation" && automationForm) {
      updateAutomationMutation.mutate(automationForm);
    } else if (activeSection === "safety" && rateLimitsForm) {
      updateRateLimitsMutation.mutate(rateLimitsForm);
    } else {
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-surface-600 to-surface-700 flex items-center justify-center">
              <Settings className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-3xl font-display font-bold text-surface-900">
              Settings
            </h1>
          </div>
          <p className="text-surface-500 font-medium">
            Configure platform settings and preferences
          </p>
        </div>
        <button
          onClick={handleSave}
          className={clsx(
            "flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold transition-all duration-300",
            saved
              ? "bg-emerald-500 text-white"
              : "btn-primary"
          )}
        >
          {saved ? (
            <>
              <Check className="w-4 h-4" />
              Saved
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              Save Changes
            </>
          )}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* Section Navigation */}
        <div className="lg:col-span-1 space-y-2">
          {sections.map((section) => {
            const Icon = section.icon;
            const isActive = activeSection === section.id;

            return (
              <button
                key={section.id}
                onClick={() => setActiveSection(section.id)}
                className={clsx(
                  "w-full flex items-center gap-3 p-4 rounded-xl text-left transition-all duration-300",
                  isActive
                    ? "bg-white shadow-md border border-surface-200"
                    : "hover:bg-surface-100"
                )}
              >
                <div
                  className={clsx(
                    "w-10 h-10 rounded-xl bg-gradient-to-br flex items-center justify-center",
                    section.color
                  )}
                >
                  <Icon className="w-5 h-5 text-white" />
                </div>
                <div>
                  <p
                    className={clsx(
                      "font-semibold",
                      isActive
                        ? "text-surface-900"
                        : "text-surface-600"
                    )}
                  >
                    {section.title}
                  </p>
                  <p className="text-xs text-surface-500 mt-0.5">
                    {section.description}
                  </p>
                </div>
              </button>
            );
          })}
        </div>

        {/* Settings Content */}
        <div className="lg:col-span-3">
          {activeSection === "api-keys" && (
            <div className="card animate-fade-in space-y-6">
              <div>
                <h3 className="text-lg font-display font-bold text-surface-900 mb-1">
                  Platform API Keys
                </h3>
                <p className="text-sm text-surface-500">
                  These are <strong>app-level</strong> credentials for your platform. Individual Twitter accounts 
                  are connected per-persona on each persona's page.
                </p>
              </div>
              
              <div className="p-4 rounded-xl bg-primary-50 border border-primary-200">
                <p className="text-sm text-primary-800">
                  <strong>How it works:</strong> App credentials here authenticate your platform. 
                  Each persona then connects their own Twitter account via OAuth on their profile page.
                </p>
              </div>

              {isLoadingApiKeys ? (
                <div className="space-y-4">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="h-24 bg-surface-100 rounded-xl animate-pulse" />
                  ))}
                </div>
              ) : (
                <div className="space-y-5">
                  {/* OpenAI */}
                  <div className="p-5 rounded-xl bg-surface-50 border border-surface-200">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
                          <Zap className="w-5 h-5 text-white" />
                        </div>
                        <div>
                          <p className="font-semibold text-surface-900">
                            OpenAI
                          </p>
                          <p className="text-xs text-surface-500">GPT-4 & DALL-E</p>
                        </div>
                      </div>
                      <StatusBadge configured={apiKeysStatus?.openai_configured ?? false} />
                    </div>
                    <p className="text-sm text-surface-600">
                      {apiKeysStatus?.openai_configured 
                        ? "OpenAI API key is configured and ready to use."
                        : "Set OPENAI_API_KEY in your .env file to enable."}
                    </p>
                    {!apiKeysStatus?.openai_configured && (
                      <a 
                        href="https://platform.openai.com/api-keys" 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 text-sm text-primary-500 hover:text-primary-600 font-medium mt-2"
                      >
                        Get API key <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>

                  {/* Anthropic */}
                  <div className="p-5 rounded-xl bg-surface-50 border border-surface-200">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center">
                          <Zap className="w-5 h-5 text-white" />
                        </div>
                        <div>
                          <p className="font-semibold text-surface-900">
                            Anthropic
                          </p>
                          <p className="text-xs text-surface-500">Claude Sonnet 4</p>
                        </div>
                      </div>
                      <StatusBadge configured={apiKeysStatus?.anthropic_configured ?? false} />
                    </div>
                    <p className="text-sm text-surface-600">
                      {apiKeysStatus?.anthropic_configured 
                        ? "Anthropic API key is configured and ready to use."
                        : "Set ANTHROPIC_API_KEY in your .env file to enable."}
                    </p>
                    {!apiKeysStatus?.anthropic_configured && (
                      <a 
                        href="https://console.anthropic.com/settings/keys" 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 text-sm text-primary-500 hover:text-primary-600 font-medium mt-2"
                      >
                        Get API key <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>

                  {/* Twitter/X */}
                  <div className="p-5 rounded-xl bg-surface-50 border border-surface-200">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-gray-800 to-black flex items-center justify-center">
                          <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                          </svg>
                        </div>
                        <div>
                          <p className="font-semibold text-surface-900">
                            Twitter / X App
                          </p>
                          <p className="text-xs text-surface-500">Developer App Credentials</p>
                        </div>
                      </div>
                      <StatusBadge configured={apiKeysStatus?.twitter_configured ?? false} />
                    </div>
                    <p className="text-sm text-surface-600 mb-3">
                      {apiKeysStatus?.twitter_configured 
                        ? "Your Twitter Developer App is configured. Personas can now connect their individual Twitter accounts."
                        : "Set up a Twitter Developer App to enable Twitter integration for your personas."}
                    </p>
                    <div className="text-xs text-surface-500 space-y-1 mb-3">
                      <p>Required in <code className="px-1 py-0.5 rounded bg-surface-200">.env</code>:</p>
                      <ul className="list-disc list-inside ml-2 space-y-0.5">
                        <li>TWITTER_API_KEY</li>
                        <li>TWITTER_API_SECRET</li>
                        <li>TWITTER_BEARER_TOKEN</li>
                      </ul>
                    </div>
                    <a 
                      href="https://developer.twitter.com/en/portal/dashboard" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-sm text-primary-500 hover:text-primary-600 font-medium"
                    >
                      Twitter Developer Portal <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>

                  {/* Instagram */}
                  <div className="p-5 rounded-xl bg-surface-50 border border-surface-200">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-pink-500 to-purple-500 flex items-center justify-center">
                          <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/>
                          </svg>
                        </div>
                        <div>
                          <p className="font-semibold text-surface-900">
                            Instagram
                          </p>
                          <p className="text-xs text-surface-500">Meta Graph API</p>
                        </div>
                      </div>
                      <StatusBadge 
                        configured={apiKeysStatus?.meta_configured ?? false}
                        label={!apiKeysStatus?.meta_configured ? "Requires approval" : undefined}
                      />
                    </div>
                    <p className="text-sm text-surface-600">
                      Meta API access requires business verification which can take weeks. 
                      We recommend using Twitter instead for faster setup.
                    </p>
                  </div>

                  {/* AI Provider Info */}
                  {apiKeysStatus && !apiKeysStatus.openai_configured && !apiKeysStatus.anthropic_configured && (
                    <div className="p-4 rounded-xl bg-amber-50 border border-amber-200">
                      <p className="text-sm text-amber-800">
                        <strong>No AI provider configured.</strong> You need at least one AI provider (OpenAI or Anthropic) to generate content.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {activeSection === "automation" && (
            <div className="card animate-fade-in space-y-6">
              <div>
                <h3 className="text-lg font-display font-bold text-surface-900 mb-1">
                  Automation Schedule
                </h3>
                <p className="text-sm text-surface-500">
                  Configure how often automated tasks run
                </p>
              </div>

              {isLoadingAutomation ? (
                <div className="flex items-center justify-center py-12">
                  <RefreshCw className="w-6 h-6 animate-spin text-surface-400" />
                </div>
              ) : automationForm ? (
                <div className="space-y-5">
                  {/* Content Generation */}
                  <div className="p-5 rounded-xl bg-surface-50 border border-surface-200">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                        <Zap className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <p className="font-semibold text-surface-900">Content Generation</p>
                        <p className="text-xs text-surface-500">How often to generate new content for active personas</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">Frequency</label>
                        <select 
                          className="w-full px-3 py-2 rounded-lg border border-surface-300 bg-white text-surface-900"
                          value={automationForm.content_generation_hours}
                          onChange={(e) => setAutomationForm({...automationForm, content_generation_hours: parseInt(e.target.value)})}
                        >
                          <option value={1}>Every hour</option>
                          <option value={2}>Every 2 hours</option>
                          <option value={4}>Every 4 hours</option>
                          <option value={6}>Every 6 hours</option>
                          <option value={12}>Every 12 hours</option>
                          <option value={24}>Once daily</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">Status</label>
                        <div className="flex items-center gap-2 h-[42px]">
                          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                          <span className="text-sm text-surface-600">Active</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Posting Queue */}
                  <div className="p-5 rounded-xl bg-surface-50 border border-surface-200">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
                        <RefreshCw className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <p className="font-semibold text-surface-900">Posting Queue</p>
                        <p className="text-xs text-surface-500">How often to check and post scheduled content</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">Frequency</label>
                        <select 
                          className="w-full px-3 py-2 rounded-lg border border-surface-300 bg-white text-surface-900"
                          value={automationForm.posting_queue_minutes}
                          onChange={(e) => setAutomationForm({...automationForm, posting_queue_minutes: parseInt(e.target.value)})}
                        >
                          <option value={5}>Every 5 minutes</option>
                          <option value={10}>Every 10 minutes</option>
                          <option value={15}>Every 15 minutes</option>
                          <option value={30}>Every 30 minutes</option>
                          <option value={60}>Every hour</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">Status</label>
                        <div className="flex items-center gap-2 h-[42px]">
                          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                          <span className="text-sm text-surface-600">Active</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Engagement Cycle */}
                  <div className="p-5 rounded-xl bg-surface-50 border border-surface-200">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-pink-500 to-rose-500 flex items-center justify-center">
                        <Bell className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <p className="font-semibold text-surface-900">Engagement Cycle</p>
                        <p className="text-xs text-surface-500">How often to run likes, comments, and follows</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">Frequency</label>
                        <select 
                          className="w-full px-3 py-2 rounded-lg border border-surface-300 bg-white text-surface-900"
                          value={automationForm.engagement_cycle_minutes}
                          onChange={(e) => setAutomationForm({...automationForm, engagement_cycle_minutes: parseInt(e.target.value)})}
                        >
                          <option value={15}>Every 15 minutes</option>
                          <option value={30}>Every 30 minutes</option>
                          <option value={45}>Every 45 minutes</option>
                          <option value={60}>Every hour</option>
                          <option value={120}>Every 2 hours</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">Status</label>
                        <div className="flex items-center gap-2 h-[42px]">
                          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                          <span className="text-sm text-surface-600">Active</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Analytics Sync */}
                  <div className="p-5 rounded-xl bg-surface-50 border border-surface-200">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
                        <Clock className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <p className="font-semibold text-surface-900">Analytics Sync</p>
                        <p className="text-xs text-surface-500">When to sync engagement analytics from platforms</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">Time (UTC)</label>
                        <select 
                          className="w-full px-3 py-2 rounded-lg border border-surface-300 bg-white text-surface-900"
                          value={automationForm.analytics_sync_hour}
                          onChange={(e) => setAutomationForm({...automationForm, analytics_sync_hour: parseInt(e.target.value)})}
                        >
                          <option value={0}>12:00 AM (Midnight)</option>
                          <option value={1}>1:00 AM</option>
                          <option value={2}>2:00 AM</option>
                          <option value={3}>3:00 AM</option>
                          <option value={4}>4:00 AM</option>
                          <option value={5}>5:00 AM</option>
                          <option value={6}>6:00 AM</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">Frequency</label>
                        <div className="flex items-center gap-2 h-[42px]">
                          <span className="text-sm text-surface-600">Daily</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Daily Limits Reset */}
                  <div className="p-5 rounded-xl bg-surface-50 border border-surface-200">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-amber-500 flex items-center justify-center">
                        <RefreshCw className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <p className="font-semibold text-surface-900">Daily Limits Reset</p>
                        <p className="text-xs text-surface-500">When to reset daily engagement limits</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">Time (UTC)</label>
                        <select 
                          className="w-full px-3 py-2 rounded-lg border border-surface-300 bg-white text-surface-900"
                          value={automationForm.daily_reset_hour}
                          onChange={(e) => setAutomationForm({...automationForm, daily_reset_hour: parseInt(e.target.value)})}
                        >
                          <option value={0}>12:00 AM (Midnight)</option>
                          <option value={1}>1:00 AM</option>
                          <option value={2}>2:00 AM</option>
                          <option value={3}>3:00 AM</option>
                          <option value={4}>4:00 AM</option>
                          <option value={5}>5:00 AM</option>
                          <option value={6}>6:00 AM</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">Frequency</label>
                        <div className="flex items-center gap-2 h-[42px]">
                          <span className="text-sm text-surface-600">Daily</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}

              <div className="p-4 rounded-xl bg-blue-50 border border-blue-200">
                <p className="text-sm text-blue-800">
                  <strong>How it works:</strong> Changes are saved to the database immediately. To apply changes, restart the celery-beat service:
                  <code className="ml-2 px-2 py-0.5 bg-blue-100 rounded text-xs">docker-compose restart celery-beat</code>
                </p>
              </div>
            </div>
          )}

          {activeSection === "notifications" && (
            <div className="card animate-fade-in space-y-6">
              <div>
                <h3 className="text-lg font-display font-bold text-surface-900 mb-1">
                  Notification Settings
                </h3>
                <p className="text-sm text-surface-500">
                  Configure how and when you receive alerts
                </p>
              </div>

              <div className="space-y-4">
                {[
                  { label: "Content posted", description: "Notify when content is published", enabled: true },
                  { label: "Content failed", description: "Notify when posting fails", enabled: true },
                  { label: "Daily summary", description: "Daily engagement summary", enabled: true },
                  { label: "Rate limit warnings", description: "When approaching API limits", enabled: false },
                  { label: "New follower milestones", description: "Celebrate growth achievements", enabled: true },
                ].map((setting) => (
                  <div
                    key={setting.label}
                    className="flex items-center justify-between p-4 rounded-xl bg-surface-50 border border-surface-200"
                  >
                    <div>
                      <p className="font-semibold text-surface-900">
                        {setting.label}
                      </p>
                      <p className="text-sm text-surface-500 mt-0.5">
                        {setting.description}
                      </p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        defaultChecked={setting.enabled}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-surface-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-500/20 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-surface-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-500"></div>
                    </label>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeSection === "safety" && (
            <div className="card animate-fade-in space-y-6">
              <div>
                <h3 className="text-lg font-display font-bold text-surface-900 mb-1">
                  Safety & Limits
                </h3>
                <p className="text-sm text-surface-500">
                  Configure engagement limits per persona per day
                </p>
              </div>

              {isLoadingRateLimits ? (
                <div className="flex items-center justify-center py-12">
                  <RefreshCw className="w-6 h-6 animate-spin text-surface-400" />
                </div>
              ) : rateLimitsForm ? (
                <div className="space-y-5">
                  {/* Posting Limits */}
                  <div className="p-5 rounded-xl bg-surface-50 border border-surface-200">
                    <h4 className="font-semibold text-surface-900 mb-4">Posting Limits</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">Max posts per day</label>
                        <input
                          type="number"
                          min={1}
                          max={100}
                          value={rateLimitsForm.max_posts_per_day}
                          onChange={(e) => setRateLimitsForm({...rateLimitsForm, max_posts_per_day: parseInt(e.target.value) || 1})}
                          className="w-full px-3 py-2 rounded-lg border border-surface-300 bg-white text-surface-900"
                        />
                        <p className="text-xs text-surface-500 mt-1">Maximum posts per persona per day</p>
                      </div>
                    </div>
                  </div>

                  {/* Engagement Limits */}
                  <div className="p-5 rounded-xl bg-surface-50 border border-surface-200">
                    <h4 className="font-semibold text-surface-900 mb-4">Engagement Limits</h4>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">Max likes per day</label>
                        <input
                          type="number"
                          min={1}
                          max={1000}
                          value={rateLimitsForm.max_likes_per_day}
                          onChange={(e) => setRateLimitsForm({...rateLimitsForm, max_likes_per_day: parseInt(e.target.value) || 1})}
                          className="w-full px-3 py-2 rounded-lg border border-surface-300 bg-white text-surface-900"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">Max comments per day</label>
                        <input
                          type="number"
                          min={1}
                          max={500}
                          value={rateLimitsForm.max_comments_per_day}
                          onChange={(e) => setRateLimitsForm({...rateLimitsForm, max_comments_per_day: parseInt(e.target.value) || 1})}
                          className="w-full px-3 py-2 rounded-lg border border-surface-300 bg-white text-surface-900"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">Max follows per day</label>
                        <input
                          type="number"
                          min={1}
                          max={200}
                          value={rateLimitsForm.max_follows_per_day}
                          onChange={(e) => setRateLimitsForm({...rateLimitsForm, max_follows_per_day: parseInt(e.target.value) || 1})}
                          className="w-full px-3 py-2 rounded-lg border border-surface-300 bg-white text-surface-900"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Action Delays */}
                  <div className="p-5 rounded-xl bg-surface-50 border border-surface-200">
                    <h4 className="font-semibold text-surface-900 mb-4">Action Delays</h4>
                    <p className="text-sm text-surface-500 mb-4">Random delay between automated actions (in seconds)</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">Minimum delay (seconds)</label>
                        <input
                          type="number"
                          min={1}
                          max={300}
                          value={rateLimitsForm.min_action_delay}
                          onChange={(e) => setRateLimitsForm({...rateLimitsForm, min_action_delay: parseInt(e.target.value) || 1})}
                          className="w-full px-3 py-2 rounded-lg border border-surface-300 bg-white text-surface-900"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">Maximum delay (seconds)</label>
                        <input
                          type="number"
                          min={5}
                          max={600}
                          value={rateLimitsForm.max_action_delay}
                          onChange={(e) => setRateLimitsForm({...rateLimitsForm, max_action_delay: parseInt(e.target.value) || 5})}
                          className="w-full px-3 py-2 rounded-lg border border-surface-300 bg-white text-surface-900"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}

              <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200">
                <p className="text-sm text-emerald-800">
                  <strong>Changes apply immediately.</strong> Rate limits are enforced on the next engagement or posting cycle.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
