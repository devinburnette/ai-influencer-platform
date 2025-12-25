"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Play,
  Pause,
  Trash2,
  Settings,
  FileText,
  Heart,
  MessageCircle,
  Users,
  TrendingUp,
  Calendar,
  Sparkles,
  Clock,
  Link2,
  Unlink,
  ExternalLink,
  Plus,
  X,
  CheckCircle,
  AlertCircle,
  Edit3,
  Save,
  Mic,
  RefreshCw,
} from "lucide-react";
import { useState } from "react";
import { api, PlatformAccount } from "@/lib/api";
import { StatCard } from "@/components/StatCard";
import { clsx } from "clsx";
import { formatDistanceToNow } from "date-fns";

const avatarGradients = [
  "from-primary-500 to-accent-500",
  "from-pink-500 to-rose-500",
  "from-amber-500 to-orange-500",
  "from-emerald-500 to-teal-500",
  "from-blue-500 to-indigo-500",
];

interface PersonaData {
  name: string;
  bio: string;
  niche: string[];
  voice: {
    tone: string;
    vocabulary_level: string;
    emoji_usage: string;
    hashtag_style: string;
    signature_phrases: string[];
  };
  ai_provider: string;
  posting_schedule: string;
  engagement_hours_start: number;
  engagement_hours_end: number;
  timezone: string;
  auto_approve_content: boolean;
  higgsfield_character_id?: string | null;
}

function EditPersonaModal({
  persona,
  onClose,
  onSave,
  isSaving,
}: {
  persona: PersonaData;
  onClose: () => void;
  onSave: (updates: Partial<PersonaData>) => void;
  isSaving: boolean;
}) {
  const [formData, setFormData] = useState({
    name: persona.name,
    bio: persona.bio,
    niche: persona.niche,
    nicheInput: "",
    voice: persona.voice,
    ai_provider: persona.ai_provider,
    posting_schedule: persona.posting_schedule,
    engagement_hours_start: persona.engagement_hours_start,
    engagement_hours_end: persona.engagement_hours_end,
    timezone: persona.timezone,
    auto_approve_content: persona.auto_approve_content,
    higgsfield_character_id: persona.higgsfield_character_id || "",
  });

  const addNiche = () => {
    if (formData.nicheInput.trim() && !formData.niche.includes(formData.nicheInput.trim())) {
      setFormData({
        ...formData,
        niche: [...formData.niche, formData.nicheInput.trim()],
        nicheInput: "",
      });
    }
  };

  const removeNiche = (tag: string) => {
    setFormData({
      ...formData,
      niche: formData.niche.filter((t) => t !== tag),
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const { nicheInput, ...updates } = formData;
    onSave(updates);
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
                Edit Persona
              </h2>
              <p className="text-sm text-surface-500">{persona.name}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl hover:bg-surface-100 dark:hover:bg-surface-800 text-surface-400 hover:text-surface-600 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit}>
          <div className="p-6 overflow-y-auto max-h-[60vh] space-y-6">
            {/* Identity Section */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-surface-900 dark:text-surface-100">
                <Sparkles className="w-4 h-4 text-primary-500" />
                Identity
              </div>

              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  Name
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  Bio
                </label>
                <textarea
                  value={formData.bio}
                  onChange={(e) => setFormData({ ...formData, bio: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 min-h-20 resize-none"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  Niche / Topics
                </label>
                <div className="flex gap-2 mb-2">
                  <input
                    type="text"
                    value={formData.nicheInput}
                    onChange={(e) => setFormData({ ...formData, nicheInput: e.target.value })}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addNiche();
                      }
                    }}
                    placeholder="Add a topic..."
                    className="flex-1 px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
                  />
                  <button
                    type="button"
                    onClick={addNiche}
                    className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors"
                  >
                    Add
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {formData.niche.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-primary-100 dark:bg-primary-500/20 text-primary-700 dark:text-primary-300 text-sm"
                    >
                      {tag}
                      <button
                        type="button"
                        onClick={() => removeNiche(tag)}
                        className="ml-1 hover:text-primary-900 dark:hover:text-primary-100"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Voice Section */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-surface-900 dark:text-surface-100">
                <Mic className="w-4 h-4 text-accent-500" />
                Voice & Style
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                    Tone
                  </label>
                  <select
                    value={formData.voice.tone}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        voice: { ...formData.voice, tone: e.target.value },
                      })
                    }
                    className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
                  >
                    <option value="friendly">Friendly</option>
                    <option value="professional">Professional</option>
                    <option value="casual">Casual</option>
                    <option value="witty">Witty</option>
                    <option value="inspirational">Inspirational</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                    Vocabulary
                  </label>
                  <select
                    value={formData.voice.vocabulary_level}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        voice: { ...formData.voice, vocabulary_level: e.target.value },
                      })
                    }
                    className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
                  >
                    <option value="simple">Simple</option>
                    <option value="casual">Casual</option>
                    <option value="professional">Professional</option>
                    <option value="technical">Technical</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                    Emoji Usage
                  </label>
                  <select
                    value={formData.voice.emoji_usage}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        voice: { ...formData.voice, emoji_usage: e.target.value },
                      })
                    }
                    className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
                  >
                    <option value="none">None</option>
                    <option value="minimal">Minimal</option>
                    <option value="moderate">Moderate</option>
                    <option value="heavy">Heavy</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                    Hashtag Style
                  </label>
                  <select
                    value={formData.voice.hashtag_style}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        voice: { ...formData.voice, hashtag_style: e.target.value },
                      })
                    }
                    className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
                  >
                    <option value="none">None</option>
                    <option value="minimal">Minimal</option>
                    <option value="relevant">Relevant</option>
                    <option value="trending">Trending</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Schedule Section */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-surface-900 dark:text-surface-100">
                <Clock className="w-4 h-4 text-blue-500" />
                Schedule & Engagement
              </div>

              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  Active Hours (for engagement)
                </label>
                <div className="flex items-center gap-4">
                  <div className="flex-1">
                    <select
                      value={formData.engagement_hours_start}
                      onChange={(e) =>
                        setFormData({ ...formData, engagement_hours_start: parseInt(e.target.value) })
                      }
                      className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
                    >
                      {Array.from({ length: 24 }, (_, i) => (
                        <option key={i} value={i}>
                          {i.toString().padStart(2, "0")}:00
                        </option>
                      ))}
                    </select>
                  </div>
                  <span className="text-surface-400">to</span>
                  <div className="flex-1">
                    <select
                      value={formData.engagement_hours_end}
                      onChange={(e) =>
                        setFormData({ ...formData, engagement_hours_end: parseInt(e.target.value) })
                      }
                      className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
                    >
                      {Array.from({ length: 25 }, (_, i) => (
                        <option key={i} value={i}>
                          {i === 24 ? "24:00 (End of day)" : `${i.toString().padStart(2, "0")}:00`}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <p className="text-xs text-surface-400 mt-1">
                  The time window when this persona will perform automated engagement actions
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  AI Provider
                </label>
                <select
                  value={formData.ai_provider}
                  onChange={(e) => setFormData({ ...formData, ai_provider: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100"
                >
                  <option value="openai">OpenAI (GPT-4)</option>
                  <option value="anthropic">Anthropic (Claude)</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                  Higgsfield Character ID
                </label>
                <input
                  type="text"
                  value={formData.higgsfield_character_id}
                  onChange={(e) => setFormData({ ...formData, higgsfield_character_id: e.target.value })}
                  placeholder="e.g., 641f8358-1600-46c3-9902-21720323fb3d"
                  className="w-full px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 font-mono text-sm"
                />
                <p className="text-xs text-surface-400 mt-1">
                  Custom reference ID for AI image generation with the Soul model.
                  Get this from your Higgsfield dashboard.
                </p>
              </div>

              <label className="flex items-center gap-3 p-3 rounded-xl bg-surface-50 dark:bg-surface-800 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.auto_approve_content}
                  onChange={(e) =>
                    setFormData({ ...formData, auto_approve_content: e.target.checked })
                  }
                  className="w-5 h-5 rounded text-primary-500 focus:ring-primary-500"
                />
                <div>
                  <p className="font-medium text-surface-900 dark:text-surface-100">
                    Auto-approve content
                  </p>
                  <p className="text-sm text-surface-500">
                    Automatically approve AI-generated content for posting
                  </p>
                </div>
              </label>
            </div>
          </div>

          {/* Footer */}
          <div className="p-5 border-t border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-sm font-semibold text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="btn-primary text-sm px-6 flex items-center gap-2 disabled:opacity-50"
            >
              {isSaving ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  Save Changes
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function PersonaDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const personaId = params.id as string;

  const { data: persona, isLoading } = useQuery({
    queryKey: ["persona", personaId],
    queryFn: () => api.getPersona(personaId),
  });

  const { data: stats } = useQuery({
    queryKey: ["persona-stats", personaId],
    queryFn: () => api.getPersonaStats(personaId),
  });

  const { data: contentQueue } = useQuery({
    queryKey: ["content-queue", personaId],
    queryFn: () => api.getContentQueue(personaId),
  });

  const { data: platformAccounts } = useQuery<PlatformAccount[]>({
    queryKey: ["platform-accounts", personaId],
    queryFn: () => api.getPlatformAccounts(personaId),
  });

  const [showConnectModal, setShowConnectModal] = useState(false);
  const [showInstagramModal, setShowInstagramModal] = useState(false);
  const [igAccessToken, setIgAccessToken] = useState("");
  const [igAccountId, setIgAccountId] = useState("");
  const [igUsername, setIgUsername] = useState("");
  const [showEditModal, setShowEditModal] = useState(false);
  const [oauthStep, setOauthStep] = useState<"start" | "pin">("start");
  const [oauthToken, setOauthToken] = useState("");
  const [pin, setPin] = useState("");
  
  // Browser login for engagement (bypasses API limits)
  const [showBrowserLoginModal, setShowBrowserLoginModal] = useState(false);
  const [browserLoginUsername, setBrowserLoginUsername] = useState("");
  const [browserLoginPassword, setBrowserLoginPassword] = useState("");
  const [browserLoginResult, setBrowserLoginResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [loginMethod, setLoginMethod] = useState<"auto" | "manual">("manual"); // Default to manual
  const [manualCookies, setManualCookies] = useState("");

  const toggleActiveMutation = useMutation({
    mutationFn: () =>
      persona?.is_active
        ? api.pausePersona(personaId)
        : api.resumePersona(personaId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["persona", personaId] });
      queryClient.invalidateQueries({ queryKey: ["personas"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deletePersona(personaId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["personas"] });
      router.push("/personas");
    },
  });

  const updatePersonaMutation = useMutation({
    mutationFn: (updates: Partial<typeof persona>) => api.updatePersona(personaId, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["persona", personaId] });
      queryClient.invalidateQueries({ queryKey: ["personas"] });
      setShowEditModal(false);
    },
  });

  const approveContentMutation = useMutation({
    mutationFn: (contentId: string) => api.approveContent(contentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content-queue", personaId] });
      queryClient.invalidateQueries({ queryKey: ["content"] });
    },
  });

  const rejectContentMutation = useMutation({
    mutationFn: (contentId: string) => api.rejectContent(contentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content-queue", personaId] });
      queryClient.invalidateQueries({ queryKey: ["content"] });
    },
  });

  const startOAuthMutation = useMutation({
    mutationFn: () => api.startTwitterOAuth(personaId),
    onSuccess: (data) => {
      setOauthToken(data.oauth_token);
      setOauthStep("pin");
      // Open Twitter authorization in a new tab
      window.open(data.authorization_url, "_blank");
    },
  });

  const completeOAuthMutation = useMutation({
    mutationFn: (pinCode: string) => 
      api.completeTwitterOAuth(personaId, { oauth_token: oauthToken, pin: pinCode }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platform-accounts", personaId] });
      setShowConnectModal(false);
      setOauthStep("start");
      setOauthToken("");
      setPin("");
    },
  });

  const disconnectAccountMutation = useMutation({
    mutationFn: (accountId: string) => api.disconnectPlatformAccount(personaId, accountId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platform-accounts", personaId] });
    },
  });

  const browserLoginMutation = useMutation({
    mutationFn: () => api.twitterBrowserLogin(personaId, browserLoginUsername, browserLoginPassword),
    onSuccess: (data) => {
      setBrowserLoginResult(data);
      if (data.success) {
        queryClient.invalidateQueries({ queryKey: ["platform-accounts", personaId] });
        // Clear password from memory
        setBrowserLoginPassword("");
      }
    },
    onError: (error: any) => {
      setBrowserLoginResult({
        success: false,
        message: error.response?.data?.detail || "Browser login failed",
      });
    },
  });

  const setCookiesMutation = useMutation({
    mutationFn: () => api.setTwitterCookies(personaId, manualCookies),
    onSuccess: (data) => {
      setBrowserLoginResult(data);
      if (data.success) {
        queryClient.invalidateQueries({ queryKey: ["platform-accounts", personaId] });
        setManualCookies("");
      }
    },
    onError: (error: any) => {
      setBrowserLoginResult({
        success: false,
        message: error.response?.data?.detail || "Failed to save cookies",
      });
    },
  });

  // Deterministic gradient based on name
  const gradientIndex = persona
    ? persona.name.charCodeAt(0) % avatarGradients.length
    : 0;
  const gradient = avatarGradients[gradientIndex];

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto animate-pulse space-y-8">
        <div className="h-32 bg-surface-100 dark:bg-surface-800 rounded-2xl" />
        <div className="grid grid-cols-4 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-32 bg-surface-100 dark:bg-surface-800 rounded-2xl"
            />
          ))}
        </div>
      </div>
    );
  }

  if (!persona) {
    return (
      <div className="max-w-7xl mx-auto text-center py-16">
        <div className="w-16 h-16 rounded-2xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center mx-auto mb-4">
          <Users className="w-8 h-8 text-surface-400" />
        </div>
        <h2 className="text-xl font-semibold text-surface-900 dark:text-surface-100 mb-2">
          Persona not found
        </h2>
        <p className="text-surface-500 dark:text-surface-400 mb-6">
          This persona may have been deleted
        </p>
        <button onClick={() => router.push("/personas")} className="btn-primary">
          Back to Personas
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-start gap-6">
        <button
          onClick={() => router.back()}
          className="w-10 h-10 rounded-xl bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 flex items-center justify-center hover:bg-surface-50 dark:hover:bg-surface-700 transition-colors mt-1 shadow-sm"
        >
          <ArrowLeft className="w-5 h-5 text-surface-500 dark:text-surface-400" />
        </button>

        <div
          className={clsx(
            "w-20 h-20 rounded-2xl bg-gradient-to-br flex items-center justify-center text-white font-bold text-2xl flex-shrink-0 shadow-lg",
            gradient
          )}
        >
          {persona.name.charAt(0).toUpperCase()}
        </div>

        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-display font-bold text-surface-900 dark:text-surface-100">
              {persona.name}
            </h1>
            <span
              className={clsx(
                "badge",
                persona.is_active ? "badge-success" : "badge-danger"
              )}
            >
              {persona.is_active ? "Active" : "Paused"}
            </span>
          </div>
          <p className="text-surface-600 dark:text-surface-400 mb-3">
            {persona.bio}
          </p>
          <div className="flex flex-wrap gap-2">
            {persona.niche.map((tag) => (
              <span
                key={tag}
                className="px-3 py-1.5 rounded-lg bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400 text-sm font-medium border border-surface-200 dark:border-surface-700"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowEditModal(true)}
            className="btn-secondary flex items-center gap-2"
          >
            <Edit3 className="w-4 h-4" />
            Edit
          </button>
          <button
            onClick={() => toggleActiveMutation.mutate()}
            className={clsx(
              "btn-secondary flex items-center gap-2",
              persona.is_active
                ? "hover:bg-amber-50 dark:hover:bg-amber-500/10 hover:text-amber-600 dark:hover:text-amber-400 hover:border-amber-200 dark:hover:border-amber-500/30"
                : "hover:bg-emerald-50 dark:hover:bg-emerald-500/10 hover:text-emerald-600 dark:hover:text-emerald-400 hover:border-emerald-200 dark:hover:border-emerald-500/30"
            )}
          >
            {persona.is_active ? (
              <>
                <Pause className="w-4 h-4" />
                Pause
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Resume
              </>
            )}
          </button>
          <button
            onClick={() => {
              if (confirm("Are you sure you want to delete this persona?")) {
                deleteMutation.mutate();
              }
            }}
            className="btn-danger flex items-center gap-2"
          >
            <Trash2 className="w-4 h-4" />
            Delete
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          label="Followers"
          value={persona.follower_count}
          icon={Users}
          color="primary"
        />
        <StatCard
          label="Posts"
          value={persona.post_count}
          icon={FileText}
          color="accent"
        />
        <StatCard
          label="Likes Given"
          value={stats?.total_likes_given ?? 0}
          icon={Heart}
          color="pink"
        />
        <StatCard
          label="Comments Given"
          value={stats?.total_comments_given ?? 0}
          icon={MessageCircle}
          color="green"
        />
      </div>

      {/* Connected Accounts */}
      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
              <Link2 className="w-5 h-5 text-surface-500 dark:text-surface-400" />
            </div>
            <div>
              <h3 className="font-display font-bold text-lg text-surface-900 dark:text-surface-100">
                Connected Accounts
              </h3>
              <p className="text-sm text-surface-500">
                Social media accounts linked to this persona
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Connect Twitter button - show if no Twitter account */}
            {(!platformAccounts || !platformAccounts.some(a => a.platform === "twitter")) && (
              <button
                onClick={() => setShowConnectModal(true)}
                className="btn-secondary flex items-center gap-2 text-sm"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                </svg>
                Twitter
              </button>
            )}
            {/* Connect Instagram button - show if no Instagram account */}
            {(!platformAccounts || !platformAccounts.some(a => a.platform === "instagram")) && (
              <button
                onClick={() => setShowInstagramModal(true)}
                className="btn-secondary flex items-center gap-2 text-sm"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                </svg>
                Instagram
              </button>
            )}
          </div>
        </div>

        {platformAccounts && platformAccounts.length > 0 ? (
          <div className="space-y-3">
            {platformAccounts.map((account) => (
              <div
                key={account.id}
                className="flex items-center justify-between p-4 rounded-xl bg-surface-50 dark:bg-surface-800/50 border border-surface-200 dark:border-surface-700"
              >
                <div className="flex items-center gap-4">
                  <div className={clsx(
                    "w-12 h-12 rounded-xl flex items-center justify-center",
                    account.platform === "instagram" 
                      ? "bg-gradient-to-br from-purple-600 via-pink-500 to-orange-400" 
                      : "bg-black"
                  )}>
                    {account.platform === "instagram" ? (
                      <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                      </svg>
                    ) : (
                      <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                      </svg>
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-semibold text-surface-900 dark:text-surface-100">
                        @{account.username}
                      </p>
                      {account.is_connected ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
                          <CheckCircle className="w-3 h-3" />
                          Connected
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                          <AlertCircle className="w-3 h-3" />
                          Disconnected
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-surface-500 capitalize">
                      {account.platform}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {/* Browser login button for Twitter - enables engagement without API limits */}
                  {account.platform === "twitter" && account.is_connected && (
                    account.engagement_enabled ? (
                      <div className="flex items-center gap-2">
                        <span 
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300"
                          title="Browser session active - likes and follows will work"
                        >
                          <CheckCircle className="w-3 h-3" />
                          Engagement Active
                        </span>
                        <button
                          onClick={() => {
                            setBrowserLoginUsername(account.username);
                            setBrowserLoginResult(null);
                            setShowBrowserLoginModal(true);
                          }}
                          className="p-1.5 rounded-lg text-xs font-medium text-surface-400 hover:text-surface-600 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
                          title="Refresh session cookies if engagement stops working"
                        >
                          <RefreshCw className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => {
                          setBrowserLoginUsername(account.username);
                          setBrowserLoginResult(null);
                          setShowBrowserLoginModal(true);
                        }}
                        className="px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300 hover:bg-amber-200 dark:hover:bg-amber-500/30 transition-colors"
                        title="Login via browser to enable likes/follows (bypasses API limits)"
                      >
                        Enable Engagement
                      </button>
                    )
                  )}
                  {account.profile_url && (
                    <a
                      href={account.profile_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700 text-surface-400 hover:text-surface-600 transition-colors"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  )}
                  <button
                    onClick={() => {
                      if (confirm("Are you sure you want to disconnect this account?")) {
                        disconnectAccountMutation.mutate(account.id);
                      }
                    }}
                    className="p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-500/10 text-surface-400 hover:text-red-500 transition-colors"
                  >
                    <Unlink className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <div className="w-12 h-12 rounded-xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center mx-auto mb-3">
              <Link2 className="w-6 h-6 text-surface-400" />
            </div>
            <p className="text-surface-500 dark:text-surface-400 mb-1">
              No accounts connected
            </p>
            <p className="text-sm text-surface-400">
              Connect a social media account to enable posting for this persona
            </p>
          </div>
        )}
      </div>

      {/* Edit Persona Modal */}
      {showEditModal && persona && (
        <EditPersonaModal
          persona={persona}
          onClose={() => setShowEditModal(false)}
          onSave={(updates) => updatePersonaMutation.mutate(updates)}
          isSaving={updatePersonaMutation.isPending}
        />
      )}

      {/* Connect Twitter Modal */}
      {showConnectModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in"
          onClick={() => {
            setShowConnectModal(false);
            setOauthStep("start");
            setPin("");
          }}
        >
          <div
            className="bg-white dark:bg-surface-900 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden animate-scale-in"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-5 border-b border-surface-200 dark:border-surface-700">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-black flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                  </svg>
                </div>
                <div>
                  <h2 className="text-lg font-display font-bold text-surface-900 dark:text-surface-100">
                    Connect Twitter Account
                  </h2>
                  <p className="text-sm text-surface-500">
                    Link a Twitter account to {persona.name}
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  setShowConnectModal(false);
                  setOauthStep("start");
                  setPin("");
                }}
                className="p-2 rounded-xl hover:bg-surface-100 dark:hover:bg-surface-800 text-surface-400 hover:text-surface-600 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              {oauthStep === "start" ? (
                <>
                  {/* Step 1: Start OAuth */}
                  <div className="text-center py-4">
                    <div className="w-16 h-16 rounded-2xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center mx-auto mb-4">
                      <svg className="w-8 h-8 text-surface-600" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                      </svg>
                    </div>
                    <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-2">
                      Authorize with Twitter
                    </h3>
                    <p className="text-sm text-surface-500 mb-4">
                      Click the button below to open Twitter and authorize access. 
                      You'll receive a PIN code to enter here.
                    </p>
                  </div>

                  <div className="p-4 rounded-xl bg-primary-50 border border-primary-200">
                    <p className="text-sm text-primary-800">
                      <strong>How it works:</strong>
                    </p>
                    <ol className="text-sm text-primary-700 mt-2 space-y-1 list-decimal list-inside">
                      <li>Click "Connect with Twitter" below</li>
                      <li>Log in to Twitter and authorize the app</li>
                      <li>Copy the PIN code shown</li>
                      <li>Paste the PIN here to complete</li>
                    </ol>
                  </div>
                </>
              ) : (
                <>
                  {/* Step 2: Enter PIN */}
                  <div className="text-center py-2">
                    <div className="w-12 h-12 rounded-xl bg-emerald-100 flex items-center justify-center mx-auto mb-3">
                      <CheckCircle className="w-6 h-6 text-emerald-600" />
                    </div>
                    <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100 mb-1">
                      Enter the PIN
                    </h3>
                    <p className="text-sm text-surface-500">
                      Twitter should have opened in a new tab. Enter the PIN code shown there.
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-surface-700 dark:text-surface-300 mb-2 text-center">
                      PIN Code
                    </label>
                    <input
                      type="text"
                      value={pin}
                      onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
                      placeholder="Enter PIN from Twitter"
                      className="input text-center text-2xl font-mono tracking-widest"
                      maxLength={10}
                      autoFocus
                    />
                  </div>

                  <div className="p-4 rounded-xl bg-amber-50 border border-amber-200">
                    <p className="text-sm text-amber-800">
                      <strong>Didn't see the PIN?</strong> Make sure pop-ups are allowed, 
                      or{" "}
                      <button
                        onClick={() => startOAuthMutation.mutate()}
                        className="text-amber-900 underline font-medium"
                      >
                        try again
                      </button>
                    </p>
                  </div>
                </>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 p-5 border-t border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
              <button
                onClick={() => {
                  setShowConnectModal(false);
                  setOauthStep("start");
                  setPin("");
                }}
                className="px-4 py-2 rounded-xl text-sm font-semibold bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-300 hover:bg-surface-200 transition-colors"
              >
                Cancel
              </button>
              
              {oauthStep === "start" ? (
                <button
                  onClick={() => startOAuthMutation.mutate()}
                  disabled={startOAuthMutation.isPending}
                  className="btn-primary text-sm px-4 py-2 flex items-center gap-2 disabled:opacity-50"
                >
                  {startOAuthMutation.isPending ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Opening Twitter...
                    </>
                  ) : (
                    <>
                      <ExternalLink className="w-4 h-4" />
                      Connect with Twitter
                    </>
                  )}
                </button>
              ) : (
                <button
                  onClick={() => completeOAuthMutation.mutate(pin)}
                  disabled={!pin || completeOAuthMutation.isPending}
                  className="btn-primary text-sm px-4 py-2 flex items-center gap-2 disabled:opacity-50"
                >
                  {completeOAuthMutation.isPending ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Connecting...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-4 h-4" />
                      Complete Connection
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Connect Instagram Modal */}
      {showInstagramModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in"
          onClick={() => {
            setShowInstagramModal(false);
            setIgAccessToken("");
            setIgAccountId("");
            setIgUsername("");
          }}
        >
          <div
            className="bg-white dark:bg-surface-900 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden animate-scale-in"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-5 border-b border-surface-200 dark:border-surface-700">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-600 via-pink-500 to-orange-400 flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                  </svg>
                </div>
                <div>
                  <h2 className="text-lg font-display font-bold text-surface-900 dark:text-surface-100">
                    Connect Instagram Account
                  </h2>
                  <p className="text-sm text-surface-500">
                    Link an Instagram Business account to {persona?.name}
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  setShowInstagramModal(false);
                  setIgAccessToken("");
                  setIgAccountId("");
                  setIgUsername("");
                }}
                className="p-2 rounded-xl hover:bg-surface-100 dark:hover:bg-surface-800 text-surface-400 hover:text-surface-600 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              <div className="p-4 rounded-xl bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/20">
                <p className="text-sm text-blue-800 dark:text-blue-300">
                  <strong>Requires:</strong> An Instagram Business or Creator account connected to a Facebook Page.
                  You'll need a System User access token from Meta Business Suite.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                  Instagram Username
                </label>
                <input
                  type="text"
                  value={igUsername}
                  onChange={(e) => setIgUsername(e.target.value)}
                  placeholder="your_instagram_handle"
                  className="w-full px-4 py-3 rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 placeholder:text-surface-400"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                  Instagram Business Account ID
                </label>
                <input
                  type="text"
                  value={igAccountId}
                  onChange={(e) => setIgAccountId(e.target.value)}
                  placeholder="17841479690090947"
                  className="w-full px-4 py-3 rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 placeholder:text-surface-400"
                />
                <p className="text-xs text-surface-500 mt-1">
                  Found via Graph API: GET /PAGE_ID?fields=instagram_business_account
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
                  Access Token
                </label>
                <input
                  type="password"
                  value={igAccessToken}
                  onChange={(e) => setIgAccessToken(e.target.value)}
                  placeholder="System User access token from Meta Business Suite"
                  className="w-full px-4 py-3 rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 placeholder:text-surface-400"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 p-5 border-t border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
              <button
                onClick={() => {
                  setShowInstagramModal(false);
                  setIgAccessToken("");
                  setIgAccountId("");
                  setIgUsername("");
                }}
                className="px-4 py-2 rounded-xl text-sm font-semibold bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-300 hover:bg-surface-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  try {
                    await api.connectInstagram(personaId, {
                      username: igUsername,
                      instagram_account_id: igAccountId,
                      access_token: igAccessToken.trim(),
                    });
                    setShowInstagramModal(false);
                    setIgAccessToken("");
                    setIgAccountId("");
                    setIgUsername("");
                    queryClient.invalidateQueries({ queryKey: ["platform-accounts", personaId] });
                  } catch (error: any) {
                    console.error("Instagram connection error:", error);
                    const message = error?.response?.data?.detail || "Failed to connect Instagram account. Please check your credentials.";
                    alert(message);
                  }
                }}
                disabled={!igUsername || !igAccountId || !igAccessToken}
                className="btn-primary text-sm px-4 py-2 flex items-center gap-2 disabled:opacity-50"
              >
                <CheckCircle className="w-4 h-4" />
                Connect Account
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Browser Login Modal for Twitter Engagement */}
      {showBrowserLoginModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in"
          onClick={() => {
            setShowBrowserLoginModal(false);
            setBrowserLoginPassword("");
            setBrowserLoginResult(null);
          }}
        >
          <div
            className="bg-white dark:bg-surface-900 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden animate-scale-in"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-5 border-b border-surface-200 dark:border-surface-700">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-black flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                  </svg>
                </div>
                <div>
                  <h2 className="text-lg font-display font-bold text-surface-900 dark:text-surface-100">
                    Enable Engagement
                  </h2>
                  <p className="text-sm text-surface-500">
                    Login to enable likes & follows
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  setShowBrowserLoginModal(false);
                  setBrowserLoginPassword("");
                  setBrowserLoginResult(null);
                }}
                className="p-2 rounded-xl hover:bg-surface-100 dark:hover:bg-surface-800 text-surface-400 hover:text-surface-600 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              <div className="p-4 rounded-xl bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/20">
                <div className="flex gap-3">
                  <AlertCircle className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-blue-800 dark:text-blue-200">
                    <p className="font-semibold mb-1">Why is this needed?</p>
                    <p>Twitter's free API tier doesn't support likes and follows. Session cookies enable browser automation for these features.</p>
                  </div>
                </div>
              </div>

              {/* Method Tabs */}
              <div className="flex rounded-xl bg-surface-100 dark:bg-surface-800 p-1">
                <button
                  onClick={() => setLoginMethod("manual")}
                  className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    loginMethod === "manual"
                      ? "bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 shadow-sm"
                      : "text-surface-500 hover:text-surface-700 dark:hover:text-surface-300"
                  }`}
                >
                  Copy Cookies (Recommended)
                </button>
                <button
                  onClick={() => setLoginMethod("auto")}
                  className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    loginMethod === "auto"
                      ? "bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 shadow-sm"
                      : "text-surface-500 hover:text-surface-700 dark:hover:text-surface-300"
                  }`}
                >
                  Auto Login
                </button>
              </div>

              {loginMethod === "manual" ? (
                <>
                  <div className="p-4 rounded-xl bg-surface-50 dark:bg-surface-800/50 border border-surface-200 dark:border-surface-700">
                    <p className="text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">How to get your cookies:</p>
                    <ol className="text-sm text-surface-600 dark:text-surface-400 space-y-1 list-decimal list-inside">
                      <li>Open Twitter/X in Chrome and log in</li>
                      <li>Press F12 to open Developer Tools</li>
                      <li>Go to Application → Cookies → twitter.com</li>
                      <li>Find <code className="bg-surface-200 dark:bg-surface-700 px-1 rounded">auth_token</code> and <code className="bg-surface-200 dark:bg-surface-700 px-1 rounded">ct0</code></li>
                      <li>Copy their values below</li>
                    </ol>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Session Cookies
                    </label>
                    <textarea
                      value={manualCookies}
                      onChange={(e) => setManualCookies(e.target.value)}
                      className="w-full px-4 py-2 rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 font-mono text-sm"
                      placeholder='{"auth_token": "xxx...", "ct0": "xxx..."}'
                      rows={3}
                    />
                    <p className="text-xs text-surface-500 mt-1">
                      Format: JSON object or "auth_token=xxx; ct0=xxx"
                    </p>
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Twitter Username
                    </label>
                    <input
                      type="text"
                      value={browserLoginUsername}
                      onChange={(e) => setBrowserLoginUsername(e.target.value)}
                      className="w-full px-4 py-2 rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      placeholder="@username"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Twitter Password
                    </label>
                    <input
                      type="password"
                      value={browserLoginPassword}
                      onChange={(e) => setBrowserLoginPassword(e.target.value)}
                      className="w-full px-4 py-2 rounded-xl border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-surface-900 dark:text-surface-100 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      placeholder="Enter password"
                    />
                    <p className="text-xs text-surface-500 mt-1">
                      Your password is used only once to create a session and is not stored.
                    </p>
                  </div>

                  <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20">
                    <div className="flex gap-3">
                      <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                      <div className="text-sm text-amber-800 dark:text-amber-200">
                        <p className="font-semibold mb-1">Note</p>
                        <p>Twitter often blocks automated logins. If this fails, use the "Copy Cookies" method instead.</p>
                      </div>
                    </div>
                  </div>
                </>
              )}

              {browserLoginResult && (
                <div className={`p-4 rounded-xl border ${
                  browserLoginResult.success 
                    ? "bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20" 
                    : "bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/20"
                }`}>
                  <div className="flex gap-3">
                    {browserLoginResult.success ? (
                      <CheckCircle className="w-5 h-5 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
                    ) : (
                      <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0" />
                    )}
                    <p className={`text-sm ${
                      browserLoginResult.success 
                        ? "text-emerald-800 dark:text-emerald-200" 
                        : "text-red-800 dark:text-red-200"
                    }`}>
                      {browserLoginResult.message}
                    </p>
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 p-5 border-t border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
              <button
                onClick={() => {
                  setShowBrowserLoginModal(false);
                  setBrowserLoginPassword("");
                  setManualCookies("");
                  setBrowserLoginResult(null);
                }}
                className="px-4 py-2 rounded-xl text-sm font-semibold bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-300 hover:bg-surface-200 transition-colors"
              >
                Cancel
              </button>
              {loginMethod === "manual" ? (
                <button
                  onClick={() => setCookiesMutation.mutate()}
                  disabled={!manualCookies || setCookiesMutation.isPending}
                  className="btn-primary text-sm px-4 py-2 flex items-center gap-2 disabled:opacity-50"
                >
                  {setCookiesMutation.isPending ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-4 h-4" />
                      Save Cookies
                    </>
                  )}
                </button>
              ) : (
                <button
                  onClick={() => browserLoginMutation.mutate()}
                  disabled={!browserLoginUsername || !browserLoginPassword || browserLoginMutation.isPending}
                  className="btn-primary text-sm px-4 py-2 flex items-center gap-2 disabled:opacity-50"
                >
                  {browserLoginMutation.isPending ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Logging in...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-4 h-4" />
                      Auto Login
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Content Queue */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Pending Review */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-display font-bold text-surface-900 dark:text-surface-100">
              Pending Review
            </h3>
            <span className="badge-warning">
              {contentQueue?.pending_review.length ?? 0}
            </span>
          </div>
          <div className="space-y-3">
            {contentQueue?.pending_review.length === 0 ? (
              <p className="text-sm text-surface-500 dark:text-surface-400 text-center py-8">
                No content pending review
              </p>
            ) : (
              contentQueue?.pending_review.slice(0, 3).map((content) => (
                <div
                  key={content.id}
                  className="p-4 rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20"
                >
                  <p 
                    className="text-sm text-surface-700 dark:text-surface-300 line-clamp-2 cursor-help"
                    title={content.caption}
                  >
                    {content.caption}
                  </p>
                  <div className="flex items-center gap-3 mt-3">
                    <button
                      onClick={() => approveContentMutation.mutate(content.id)}
                      disabled={approveContentMutation.isPending}
                      className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 hover:text-emerald-500 transition-colors disabled:opacity-50"
                    >
                      {approveContentMutation.isPending ? "..." : "Approve"}
                    </button>
                    <span className="text-surface-300 dark:text-surface-600">
                      |
                    </span>
                    <button
                      onClick={() => rejectContentMutation.mutate(content.id)}
                      disabled={rejectContentMutation.isPending}
                      className="text-xs font-semibold text-red-600 dark:text-red-400 hover:text-red-500 transition-colors disabled:opacity-50"
                    >
                      {rejectContentMutation.isPending ? "..." : "Reject"}
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Scheduled */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-display font-bold text-surface-900 dark:text-surface-100">
              Scheduled
            </h3>
            <span className="badge-info">
              {contentQueue?.scheduled.length ?? 0}
            </span>
          </div>
          <div className="space-y-3">
            {contentQueue?.scheduled.length === 0 ? (
              <p className="text-sm text-surface-500 dark:text-surface-400 text-center py-8">
                No scheduled content
              </p>
            ) : (
              contentQueue?.scheduled.slice(0, 3).map((content) => (
                <div
                  key={content.id}
                  className="p-4 rounded-xl bg-primary-50 dark:bg-primary-500/10 border border-primary-200 dark:border-primary-500/20"
                >
                  <p 
                    className="text-sm text-surface-700 dark:text-surface-300 line-clamp-2 cursor-help"
                    title={content.caption}
                  >
                    {content.caption}
                  </p>
                  {content.scheduled_for && (
                    <p className="text-xs text-primary-600 dark:text-primary-400 mt-3 flex items-center gap-1.5 font-medium">
                      <Calendar className="w-3.5 h-3.5" />
                      {new Date(content.scheduled_for).toLocaleDateString()}
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Recent Posts */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-display font-bold text-surface-900 dark:text-surface-100">
              Recent Posts
            </h3>
            <span className="badge-success">
              {contentQueue?.posted.length ?? 0}
            </span>
          </div>
          <div className="space-y-3">
            {contentQueue?.posted.length === 0 ? (
              <p className="text-sm text-surface-500 dark:text-surface-400 text-center py-8">
                No posts yet
              </p>
            ) : (
              contentQueue?.posted.slice(0, 3).map((content) => (
                <div
                  key={content.id}
                  className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20"
                >
                  <p 
                    className="text-sm text-surface-700 dark:text-surface-300 line-clamp-2 cursor-help"
                    title={content.caption}
                  >
                    {content.caption}
                  </p>
                  <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-3 flex items-center gap-1.5 font-medium">
                    <Heart className="w-3.5 h-3.5" />
                    {content.engagement_count} engagements
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Configuration */}
      <div className="card">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
            <Settings className="w-5 h-5 text-surface-500 dark:text-surface-400" />
          </div>
          <h3 className="font-display font-bold text-lg text-surface-900 dark:text-surface-100">
            Configuration
          </h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div className="p-4 rounded-xl bg-surface-50 dark:bg-surface-800/50 border border-surface-100 dark:border-surface-700">
            <p className="text-sm font-medium text-surface-500 dark:text-surface-400 mb-1">
              AI Provider
            </p>
            <p className="text-surface-900 dark:text-surface-100 font-semibold capitalize">
              {persona.ai_provider}
            </p>
          </div>
          <div className="p-4 rounded-xl bg-surface-50 dark:bg-surface-800/50 border border-surface-100 dark:border-surface-700">
            <p className="text-sm font-medium text-surface-500 dark:text-surface-400 mb-1">
              Voice Tone
            </p>
            <p className="text-surface-900 dark:text-surface-100 font-semibold capitalize">
              {persona.voice.tone}
            </p>
          </div>
          <div className="p-4 rounded-xl bg-surface-50 dark:bg-surface-800/50 border border-surface-100 dark:border-surface-700">
            <p className="text-sm font-medium text-surface-500 dark:text-surface-400 mb-1">
              Emoji Usage
            </p>
            <p className="text-surface-900 dark:text-surface-100 font-semibold capitalize">
              {persona.voice.emoji_usage}
            </p>
          </div>
          <div className="p-4 rounded-xl bg-surface-50 dark:bg-surface-800/50 border border-surface-100 dark:border-surface-700">
            <p className="text-sm font-medium text-surface-500 dark:text-surface-400 mb-1">
              Active Hours
            </p>
            <p className="text-surface-900 dark:text-surface-100 font-semibold">
              {persona.engagement_hours_start}:00 -{" "}
              {persona.engagement_hours_end}:00
            </p>
          </div>
        </div>
      </div>

      {/* Generate Content Button */}
      <div className="flex justify-center">
        <button
          onClick={async () => {
            await api.generateContent(personaId);
            queryClient.invalidateQueries({
              queryKey: ["content-queue", personaId],
            });
          }}
          className="btn-primary flex items-center gap-2"
        >
          <Sparkles className="w-4 h-4" />
          Generate New Content
        </button>
      </div>
    </div>
  );
}
