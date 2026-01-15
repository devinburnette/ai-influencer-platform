"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Sparkles, Save, Users, Mic, Clock, X, Image } from "lucide-react";
import { api } from "@/lib/api";
import { clsx } from "clsx";

export default function NewPersonaPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [formData, setFormData] = useState({
    name: "",
    bio: "",
    niche: [] as string[],
    nicheInput: "",
    voice: {
      tone: "friendly",
      vocabulary_level: "casual",
      emoji_usage: "moderate",
      hashtag_style: "relevant",
      signature_phrases: [] as string[],
    },
    ai_provider: "openai",
    higgsfield_character_id: "",
    posting_schedule: "0 9,13,18 * * *",
    engagement_hours_start: 8,
    engagement_hours_end: 22,
    timezone: "UTC",
    auto_approve_content: false,
    content_prompt_template: "",
    comment_prompt_template: "",
    image_prompt_template: "",
    // Appearance settings for image/video generation
    appearance_ethnicity: "mixed race",
    appearance_age: "25 years old",
    appearance_hair: "curly, naturally styled hair",
    appearance_body_type: "fit and toned",
    appearance_voice: "American",
  });

  const createMutation = useMutation({
    mutationFn: (data: typeof formData) => {
      const { nicheInput, ...rest } = data;
      return api.createPersona(rest);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["personas"] });
      router.push("/personas");
    },
  });

  const addNiche = () => {
    if (
      formData.nicheInput.trim() &&
      !formData.niche.includes(formData.nicheInput.trim())
    ) {
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

  return (
    <div className="max-w-3xl mx-auto space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="w-10 h-10 rounded-xl bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 flex items-center justify-center hover:bg-surface-50 dark:hover:bg-surface-700 transition-colors shadow-sm"
        >
          <ArrowLeft className="w-5 h-5 text-surface-500 dark:text-surface-400" />
        </button>
        <div>
          <div className="flex items-center gap-3 mb-1">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
              <Users className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-3xl font-display font-bold text-surface-900 dark:text-surface-100">
              Create New Persona
            </h1>
          </div>
          <p className="text-surface-500 dark:text-surface-400 font-medium ml-14">
            Set up a new AI influencer personality
          </p>
        </div>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          createMutation.mutate(formData);
        }}
        className="space-y-8"
      >
        {/* Identity Section */}
        <div className="card space-y-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-100 dark:bg-primary-500/20 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-primary-600 dark:text-primary-400" />
            </div>
            <h2 className="text-lg font-display font-bold text-surface-900 dark:text-surface-100">
              Identity
            </h2>
          </div>

          <div className="space-y-5">
            <div>
              <label className="label">Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder="e.g., Alex Fitness Pro"
                className="input"
                required
              />
            </div>

            <div>
              <label className="label">Bio</label>
              <textarea
                value={formData.bio}
                onChange={(e) =>
                  setFormData({ ...formData, bio: e.target.value })
                }
                placeholder="Write a compelling bio for your AI influencer..."
                className="input min-h-24 resize-none"
                required
              />
              <p className="text-xs text-surface-400 dark:text-surface-500 mt-1.5 font-medium">
                {formData.bio.length}/500 characters
              </p>
            </div>

            <div>
              <label className="label">Niche / Topics</label>
              <div className="flex gap-2 mb-3">
                <input
                  type="text"
                  value={formData.nicheInput}
                  onChange={(e) =>
                    setFormData({ ...formData, nicheInput: e.target.value })
                  }
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addNiche();
                    }
                  }}
                  placeholder="Add a topic (press Enter)"
                  className="input flex-1"
                />
                <button type="button" onClick={addNiche} className="btn-secondary">
                  Add
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {formData.niche.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-100 dark:bg-primary-500/20 text-primary-700 dark:text-primary-400 text-sm font-medium border border-primary-200 dark:border-primary-500/30"
                  >
                    {tag}
                    <button
                      type="button"
                      onClick={() => removeNiche(tag)}
                      className="hover:text-primary-500 transition-colors"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </span>
                ))}
                {formData.niche.length === 0 && (
                  <p className="text-sm text-surface-400 dark:text-surface-500 italic">
                    Add at least one topic to continue
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Voice Section */}
        <div className="card space-y-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-accent-100 dark:bg-accent-500/20 flex items-center justify-center">
              <Mic className="w-5 h-5 text-accent-600 dark:text-accent-400" />
            </div>
            <h2 className="text-lg font-display font-bold text-surface-900 dark:text-surface-100">
              Voice & Personality
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div>
              <label className="label">Tone</label>
              <select
                value={formData.voice.tone}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    voice: { ...formData.voice, tone: e.target.value },
                  })
                }
                className="input"
              >
                <option value="friendly">Friendly</option>
                <option value="professional">Professional</option>
                <option value="casual">Casual</option>
                <option value="inspirational">Inspirational</option>
                <option value="humorous">Humorous</option>
                <option value="authoritative">Authoritative</option>
              </select>
            </div>

            <div>
              <label className="label">Vocabulary</label>
              <select
                value={formData.voice.vocabulary_level}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    voice: { ...formData.voice, vocabulary_level: e.target.value },
                  })
                }
                className="input"
              >
                <option value="simple">Simple</option>
                <option value="casual">Casual</option>
                <option value="sophisticated">Sophisticated</option>
                <option value="technical">Technical</option>
              </select>
            </div>

            <div>
              <label className="label">Emoji Usage</label>
              <select
                value={formData.voice.emoji_usage}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    voice: { ...formData.voice, emoji_usage: e.target.value },
                  })
                }
                className="input"
              >
                <option value="none">None</option>
                <option value="minimal">Minimal</option>
                <option value="moderate">Moderate</option>
                <option value="heavy">Heavy</option>
              </select>
            </div>

            <div>
              <label className="label">Hashtag Style</label>
              <select
                value={formData.voice.hashtag_style}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    voice: { ...formData.voice, hashtag_style: e.target.value },
                  })
                }
                className="input"
              >
                <option value="minimal">Minimal (1-3)</option>
                <option value="relevant">Relevant (4-8)</option>
                <option value="comprehensive">Comprehensive (8-15)</option>
                <option value="viral">Viral-focused (15+)</option>
              </select>
            </div>
          </div>
        </div>

        {/* AI & Schedule Section */}
        <div className="card space-y-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-100 dark:bg-emerald-500/20 flex items-center justify-center">
              <Clock className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <h2 className="text-lg font-display font-bold text-surface-900 dark:text-surface-100">
              AI & Schedule
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div>
              <label className="label">AI Provider</label>
              <select
                value={formData.ai_provider}
                onChange={(e) =>
                  setFormData({ ...formData, ai_provider: e.target.value })
                }
                className="input"
              >
                <option value="openai">OpenAI (GPT-4)</option>
                <option value="anthropic">Anthropic (Claude)</option>
              </select>
            </div>

            <div className="md:col-span-2">
              <label className="label">Higgsfield Character ID (Optional)</label>
              <input
                type="text"
                value={formData.higgsfield_character_id}
                onChange={(e) =>
                  setFormData({ ...formData, higgsfield_character_id: e.target.value })
                }
                placeholder="e.g., abc123-def456-..."
                className="input"
              />
              <p className="text-xs text-surface-400 dark:text-surface-500 mt-1.5 font-medium">
                For AI-generated images using Higgsfield's Soul model. Leave empty to skip automatic image generation (you can still manually upload images).
              </p>
            </div>

            <div>
              <label className="label">Timezone</label>
              <select
                value={formData.timezone}
                onChange={(e) =>
                  setFormData({ ...formData, timezone: e.target.value })
                }
                className="input"
              >
                <option value="UTC">UTC</option>
                <option value="America/New_York">Eastern Time</option>
                <option value="America/Los_Angeles">Pacific Time</option>
                <option value="Europe/London">London</option>
                <option value="Europe/Paris">Paris</option>
                <option value="Asia/Tokyo">Tokyo</option>
              </select>
            </div>

            <div>
              <label className="label">Engagement Hours Start</label>
              <input
                type="number"
                min="0"
                max="23"
                value={formData.engagement_hours_start}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    engagement_hours_start: parseInt(e.target.value),
                  })
                }
                className="input"
              />
            </div>

            <div>
              <label className="label">Engagement Hours End</label>
              <input
                type="number"
                min="0"
                max="23"
                value={formData.engagement_hours_end}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    engagement_hours_end: parseInt(e.target.value),
                  })
                }
                className="input"
              />
            </div>
          </div>

          <div className="flex items-center gap-3 p-4 rounded-xl bg-surface-50 dark:bg-surface-800/50 border border-surface-100 dark:border-surface-700">
            <input
              type="checkbox"
              id="autoApprove"
              checked={formData.auto_approve_content}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  auto_approve_content: e.target.checked,
                })
              }
              className="w-5 h-5 rounded-md border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-800 text-primary-500 focus:ring-2 focus:ring-primary-500/30 focus:ring-offset-0"
            />
            <label
              htmlFor="autoApprove"
              className="text-sm font-medium text-surface-700 dark:text-surface-300"
            >
              Auto-approve generated content (skip review queue)
            </label>
          </div>
        </div>

        {/* Appearance Settings Section */}
        <div className="card space-y-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-pink-100 dark:bg-pink-500/20 flex items-center justify-center">
              <Image className="w-5 h-5 text-pink-600 dark:text-pink-400" />
            </div>
            <div>
              <h2 className="text-lg font-display font-bold text-surface-900 dark:text-surface-100">
                Appearance Settings
              </h2>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Define how your persona looks in AI-generated images and videos
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div>
              <label className="label">Ethnicity</label>
              <input
                type="text"
                value={formData.appearance_ethnicity}
                onChange={(e) =>
                  setFormData({ ...formData, appearance_ethnicity: e.target.value })
                }
                placeholder="e.g., mixed race, Latina, Asian"
                className="input"
              />
            </div>

            <div>
              <label className="label">Age</label>
              <input
                type="text"
                value={formData.appearance_age}
                onChange={(e) =>
                  setFormData({ ...formData, appearance_age: e.target.value })
                }
                placeholder="e.g., 25 years old, mid-20s"
                className="input"
              />
            </div>

            <div className="md:col-span-2">
              <label className="label">Hair</label>
              <input
                type="text"
                value={formData.appearance_hair}
                onChange={(e) =>
                  setFormData({ ...formData, appearance_hair: e.target.value })
                }
                placeholder="e.g., curly, naturally styled dark hair"
                className="input"
              />
            </div>

            <div className="md:col-span-2">
              <label className="label">Body Type</label>
              <input
                type="text"
                value={formData.appearance_body_type}
                onChange={(e) =>
                  setFormData({ ...formData, appearance_body_type: e.target.value })
                }
                placeholder="e.g., fit and toned, curvy, slim"
                className="input"
              />
            </div>

            <div className="md:col-span-2">
              <label className="label">Voice/Accent (for videos)</label>
              <select
                value={formData.appearance_voice}
                onChange={(e) =>
                  setFormData({ ...formData, appearance_voice: e.target.value })
                }
                className="input"
              >
                <option value="American">American</option>
                <option value="British">British</option>
                <option value="Australian">Australian</option>
                <option value="Canadian">Canadian</option>
                <option value="Irish">Irish</option>
                <option value="Scottish">Scottish</option>
                <option value="Southern American">Southern American</option>
                <option value="New York">New York</option>
                <option value="California">California</option>
              </select>
              <p className="text-xs text-surface-400 dark:text-surface-500 mt-1.5">
                The accent used when she speaks in generated videos
              </p>
            </div>
          </div>
        </div>

        {/* Prompt Templates Section */}
        <div className="card space-y-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-100 dark:bg-violet-500/20 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-violet-600 dark:text-violet-400" />
            </div>
            <div>
              <h2 className="text-lg font-display font-bold text-surface-900 dark:text-surface-100">
                Prompt Templates
              </h2>
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Customize how the AI generates content (optional)
              </p>
            </div>
          </div>

          <div className="space-y-5">
            <div>
              <label className="label">Content Generation Prompt</label>
              <textarea
                value={formData.content_prompt_template}
                onChange={(e) =>
                  setFormData({ ...formData, content_prompt_template: e.target.value })
                }
                placeholder={`You are {name}, an AI social media influencer.

Bio: {bio}

Your content focuses on: {niche}

Voice and Personality:
- Tone: {tone}
- Vocabulary: {vocabulary_level}
- {emoji_guidance}
- {hashtag_guidance}

Write content that feels authentic to this persona.`}
                rows={8}
                className="input font-mono text-sm"
              />
              <p className="text-xs text-surface-400 dark:text-surface-500 mt-1.5">
                Placeholders: {"{name}"}, {"{bio}"}, {"{niche}"}, {"{tone}"}, {"{vocabulary_level}"}, {"{emoji_usage}"}, {"{emoji_guidance}"}, {"{hashtag_style}"}, {"{hashtag_guidance}"}, {"{signature_phrases}"}
              </p>
            </div>

            <div>
              <label className="label">Comment Generation Prompt</label>
              <textarea
                value={formData.comment_prompt_template}
                onChange={(e) =>
                  setFormData({ ...formData, comment_prompt_template: e.target.value })
                }
                placeholder="Leave empty to use the default prompt (same as content prompt above)"
                rows={6}
                className="input font-mono text-sm"
              />
              <p className="text-xs text-surface-400 dark:text-surface-500 mt-1.5">
                Optional. If empty, uses the content prompt template. Same placeholders available.
              </p>
            </div>

            <div>
              <label className="label">Image Generation Prompt</label>
              <textarea
                value={formData.image_prompt_template}
                onChange={(e) =>
                  setFormData({ ...formData, image_prompt_template: e.target.value })
                }
                placeholder={`Professional photo of {name}, {caption}

Style: realistic photography, high quality, natural lighting
Setting: relevant to the content topic`}
                rows={5}
                className="input font-mono text-sm"
              />
              <p className="text-xs text-surface-400 dark:text-surface-500 mt-1.5">
                Placeholders: {"{caption}"}, {"{niche}"}, {"{name}"}, {"{style_hints}"}. Controls how AI generates images for posts.
              </p>
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex justify-end gap-4">
          <button
            type="button"
            onClick={() => router.back()}
            className="btn-secondary"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={createMutation.isPending || formData.niche.length === 0}
            className={clsx(
              "btn-primary flex items-center gap-2",
              (createMutation.isPending || formData.niche.length === 0) &&
                "opacity-50 cursor-not-allowed"
            )}
          >
            <Save className="w-4 h-4" />
            {createMutation.isPending ? "Creating..." : "Create Persona"}
          </button>
        </div>
      </form>
    </div>
  );
}
