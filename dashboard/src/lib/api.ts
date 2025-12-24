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
}

export interface Content {
  id: string;
  persona_id: string;
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
}

export interface ActivityLogEntry {
  id: string;
  persona_id: string;
  persona_name: string;
  action_type: string;
  target_url: string | null;
  details: string | null;
  created_at: string;
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
    topic?: string
  ): Promise<Content> => {
    const { data } = await client.post(`/api/content/${personaId}/generate`, {
      topic,
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
};

