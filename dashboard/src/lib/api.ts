import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const client = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export interface Persona {
  id: string;
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
  is_active: boolean;
  follower_count: number;
  following_count: number;
  post_count: number;
  likes_today: number;
  comments_today: number;
  follows_today: number;
  // Per-persona engagement limits (null means use global defaults)
  max_likes_per_day?: number | null;
  max_comments_per_day?: number | null;
  max_follows_per_day?: number | null;
  higgsfield_character_id?: string | null;
  // Custom prompt templates
  content_prompt_template?: string | null;
  comment_prompt_template?: string | null;
  image_prompt_template?: string | null;
  // DM settings
  dm_auto_respond?: boolean;
  dm_response_delay_min?: number;
  dm_response_delay_max?: number;
  dm_max_responses_per_day?: number;
  dm_responses_today?: number;
  dm_prompt_template?: string | null;
}

export interface Content {
  id: string;
  persona_id: string;
  video_urls?: string[];
  content_type: string;
  caption: string;
  hashtags: string[];
  media_urls: string[];
  status: string;
  scheduled_for: string | null;
  posted_at: string | null;
  auto_generated: boolean;
  engagement_count: number;
  error_message: string | null;
  posted_platforms: string[];  // Which platforms have received this content
  platform_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface DashboardOverview {
  total_personas: number;
  active_personas: number;
  total_posts: number;
  posts_today: number;
  engagements_today: number;
  pending_content: number;
  // Profile metrics
  total_followers: number;
  total_following: number;
  total_engagement_received: number;
}

// Alias for backward compatibility
export type DashboardStats = DashboardOverview;

export interface ActivityLogEntry {
  id: string;
  persona_id: string;
  persona_name: string;
  action_type: string;
  platform: string;
  target_url: string | null;
  target_username: string | null;
  details: string | null;
  created_at: string;
}

export interface RateLimits {
  max_posts_per_day: number;
  max_likes_per_day: number;
  max_comments_per_day: number;
  max_follows_per_day: number;
  min_action_delay: number;
  max_action_delay: number;
}

export interface PlatformAccount {
  id: string;
  platform: string;
  username: string;
  platform_user_id: string | null;
  profile_url: string | null;
  is_connected: boolean;
  is_primary: boolean;
  last_sync_at: string | null;
  connection_error: string | null;
  engagement_enabled: boolean;
  engagement_paused: boolean;
  posting_paused: boolean;
  // Platform-specific stats
  follower_count: number;
  following_count: number;
  post_count: number;
}

export interface PersonaStats {
  persona_id: string;
  persona_name: string;
  follower_count: number;
  following_count: number;
  post_count: number;
  total_likes_given: number;
  total_comments_given: number;
  content_pending_review: number;
  content_scheduled: number;
  is_active: boolean;
}

export const api = {
  // Dashboard
  getOverview: async (): Promise<DashboardOverview> => {
    const { data } = await client.get("/api/analytics/overview");
    return data;
  },

  // Dashboard stats
  getDashboardStats: async (): Promise<DashboardStats> => {
    const { data } = await client.get("/api/analytics/overview");
    return data;
  },

  // Personas
  getPersonas: async (): Promise<Persona[]> => {
    const { data } = await client.get("/api/personas/");
    return data;
  },

  getPersona: async (id: string): Promise<Persona> => {
    const { data } = await client.get(`/api/personas/${id}`);
    return data;
  },

  createPersona: async (persona: Partial<Persona>): Promise<Persona> => {
    const { data } = await client.post("/api/personas/", persona);
    return data;
  },

  updatePersona: async (
    id: string,
    updates: Partial<Persona>
  ): Promise<Persona> => {
    const { data } = await client.patch(`/api/personas/${id}`, updates);
    return data;
  },

  deletePersona: async (id: string): Promise<void> => {
    await client.delete(`/api/personas/${id}`);
  },

  pausePersona: async (id: string): Promise<Persona> => {
    const { data } = await client.post(`/api/personas/${id}/pause`);
    return data;
  },

  resumePersona: async (id: string): Promise<Persona> => {
    const { data } = await client.post(`/api/personas/${id}/resume`);
    return data;
  },

  getPersonaStats: async (id: string): Promise<PersonaStats> => {
    const { data } = await client.get(`/api/analytics/personas/${id}/stats`);
    return data;
  },

  // Platform Accounts
  getPlatformAccounts: async (personaId: string): Promise<PlatformAccount[]> => {
    const { data } = await client.get(`/api/personas/${personaId}/accounts`);
    return data;
  },

  startTwitterOAuth: async (
    personaId: string
  ): Promise<{ authorization_url: string; oauth_token: string }> => {
    const { data } = await client.post(`/api/personas/${personaId}/accounts/twitter/start-oauth`);
    return data;
  },

  completeTwitterOAuth: async (
    personaId: string,
    oauthData: { oauth_token: string; pin: string }
  ): Promise<PlatformAccount> => {
    const { data } = await client.post(`/api/personas/${personaId}/accounts/twitter/complete-oauth`, oauthData);
    return data;
  },

  disconnectPlatformAccount: async (personaId: string, accountId: string): Promise<void> => {
    await client.delete(`/api/personas/${personaId}/accounts/${accountId}`);
  },

  connectInstagram: async (
    personaId: string,
    credentials: { username: string; instagram_account_id: string; access_token: string }
  ): Promise<PlatformAccount> => {
    const { data } = await client.post(`/api/personas/${personaId}/accounts/instagram/connect`, credentials);
    return data;
  },

  // Content
  getContent: async (filters?: {
    persona_id?: string;
    status?: string;
  }): Promise<Content[]> => {
    const params = new URLSearchParams();
    if (filters?.persona_id) params.append("persona_id", filters.persona_id);
    if (filters?.status) params.append("status", filters.status);
    const { data } = await client.get(`/api/content/?${params.toString()}`);
    return data;
  },

  getContentQueue: async (
    personaId: string
  ): Promise<{
    pending_review: Content[];
    scheduled: Content[];
    posted: Content[];
  }> => {
    const { data } = await client.get(`/api/content/queue/${personaId}`);
    return data;
  },

  approveContent: async (id: string): Promise<Content> => {
    const { data } = await client.post(`/api/content/${id}/approve`);
    return data;
  },

  rejectContent: async (id: string): Promise<void> => {
    await client.post(`/api/content/${id}/reject`);
  },

  deleteContent: async (id: string): Promise<void> => {
    await client.delete(`/api/content/${id}`);
  },

  updateContent: async (
    id: string,
    updates: {
      caption?: string;
      hashtags?: string[];
      media_urls?: string[];
      scheduled_for?: string;
    }
  ): Promise<Content> => {
    const { data } = await client.patch(`/api/content/${id}`, updates);
    return data;
  },

  postContentNow: async (id: string, platforms?: string[]): Promise<Content> => {
    const body = platforms && platforms.length > 0 ? { platforms } : undefined;
    const { data } = await client.post(`/api/content/${id}/post-now`, body);
    return data;
  },

  retryContent: async (id: string): Promise<Content> => {
    const { data } = await client.post(`/api/content/${id}/retry`);
    return data;
  },

  generateContent: async (
    personaId: string,
    options?: {
      topic?: string;
      content_type?: 'post' | 'video_post' | 'story' | 'reel' | 'carousel';
      generate_video?: boolean;
      platform?: string;
    }
  ): Promise<Content> => {
    // Map video_post to post with video flag for backend compatibility
    const backendContentType = options?.content_type === 'video_post' ? 'post' : (options?.content_type || 'post');
    const shouldGenerateVideo = options?.generate_video || options?.content_type === 'video_post' || options?.content_type === 'story' || options?.content_type === 'reel';
    
    const { data } = await client.post(`/api/content/${personaId}/generate`, {
      topic: options?.topic,
      content_type: backendContentType,
      generate_video: shouldGenerateVideo,
      platform: options?.platform || 'instagram',
    });
    return data;
  },

  // Activity
  getActivityLog: async (limit: number = 50): Promise<ActivityLogEntry[]> => {
    const { data } = await client.get(`/api/analytics/activity-log?limit=${limit}`);
    return data;
  },

  // Settings
  getSystemStatus: async () => {
    const { data } = await client.get("/api/settings/status");
    return data;
  },

  getRateLimits: async (): Promise<RateLimits> => {
    const { data } = await client.get("/api/settings/rate-limits");
    return data;
  },

  // Engagement
  triggerEngagement: async (personaId: string): Promise<{ success: boolean; task_id: string; message: string }> => {
    const { data } = await client.post(`/api/analytics/personas/${personaId}/engagement/trigger`);
    return data;
  },

  // Twitter browser login for engagement
  twitterBrowserLogin: async (
    personaId: string,
    username: string,
    password: string
  ): Promise<{ success: boolean; message: string; has_cookies: boolean }> => {
    const { data } = await client.post(`/api/personas/${personaId}/accounts/twitter/browser-login`, {
      username,
      password,
    });
    return data;
  },

  // Manual Twitter cookies for engagement
  setTwitterCookies: async (
    personaId: string,
    cookies: string
  ): Promise<{ success: boolean; message: string; has_cookies: boolean }> => {
    const { data } = await client.post(`/api/personas/${personaId}/accounts/twitter/set-cookies`, {
      cookies,
    });
    return data;
  },

  // Guided browser session for Twitter (opens visible browser for user to login)
  twitterGuidedSession: async (
    personaId: string
  ): Promise<{ success: boolean; message: string; cookies_captured: boolean; username?: string }> => {
    const { data } = await client.post(`/api/personas/${personaId}/accounts/twitter/guided-session`);
    return data;
  },

  // Guided browser session for Instagram (opens visible browser for user to login)
  instagramGuidedSession: async (
    personaId: string
  ): Promise<{ success: boolean; message: string; cookies_captured: boolean; username?: string }> => {
    const { data } = await client.post(`/api/personas/${personaId}/accounts/instagram/guided-session`);
    return data;
  },

  // Manual Instagram cookies for engagement
  setInstagramCookies: async (
    personaId: string,
    cookies: string
  ): Promise<{ success: boolean; message: string; has_cookies: boolean }> => {
    const { data } = await client.post(`/api/personas/${personaId}/accounts/instagram/set-cookies`, {
      cookies,
    });
    return data;
  },

  // Toggle platform engagement/posting status
  togglePlatformStatus: async (
    personaId: string,
    platform: string,
    updates: { engagement_paused?: boolean; posting_paused?: boolean }
  ): Promise<{
    success: boolean;
    platform: string;
    engagement_paused: boolean;
    posting_paused: boolean;
    message: string;
  }> => {
    const { data } = await client.patch(
      `/api/personas/${personaId}/accounts/${platform}/toggle`,
      updates
    );
    return data;
  },
};


