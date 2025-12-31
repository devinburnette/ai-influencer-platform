"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  Plus,
  Search,
  Clock,
  CheckCircle,
  XCircle,
  Edit3,
  Eye,
  Trash2,
  Calendar,
  Image,
  Send,
  X,
  Copy,
  ExternalLink,
  Hash,
  RefreshCw,
} from "lucide-react";
import { useState } from "react";
import { api, Content, Persona, PlatformAccount } from "@/lib/api";
import { formatDistanceToNow, format } from "date-fns";
import { clsx } from "clsx";
import Link from "next/link";
import { Sparkles, Loader2, User } from "lucide-react";

const statusConfig = {
  draft: {
    label: "Draft",
    icon: Edit3,
    color: "text-surface-500",
    bgColor: "bg-surface-100 dark:bg-surface-700",
  },
  pending_review: {
    label: "Pending Review",
    icon: Eye,
    color: "text-amber-600 dark:text-amber-400",
    bgColor: "bg-amber-100 dark:bg-amber-500/20",
  },
  approved: {
    label: "Approved",
    icon: CheckCircle,
    color: "text-emerald-600 dark:text-emerald-400",
    bgColor: "bg-emerald-100 dark:bg-emerald-500/20",
  },
  scheduled: {
    label: "Scheduled",
    icon: Calendar,
    color: "text-primary-600 dark:text-primary-400",
    bgColor: "bg-primary-100 dark:bg-primary-500/20",
  },
  posted: {
    label: "Posted",
    icon: Send,
    color: "text-emerald-600 dark:text-emerald-400",
    bgColor: "bg-emerald-100 dark:bg-emerald-500/20",
  },
  published: {
    label: "Published",
    icon: Send,
    color: "text-emerald-600 dark:text-emerald-400",
    bgColor: "bg-emerald-100 dark:bg-emerald-500/20",
  },
  failed: {
    label: "Failed",
    icon: XCircle,
    color: "text-red-600 dark:text-red-400",
    bgColor: "bg-red-100 dark:bg-red-500/20",
  },
};

function ContentModal({
  content,
  onClose,
  onApprove,
  onReject,
  onDelete,
  onPostNow,
  onRetry,
  onUpdateImage,
  isPosting,
  isRetrying,
  isUpdatingImage,
  connectedPlatforms,
}: {
  content: Content;
  onClose: () => void;
  onApprove?: (id: string) => void;
  onReject?: (id: string) => void;
  onDelete?: (id: string) => void;
  onPostNow?: (id: string, platforms: string[]) => void;
  onRetry?: (id: string) => void;
  onUpdateImage?: (id: string, imageUrl: string) => void;
  isPosting?: boolean;
  isRetrying?: boolean;
  isUpdatingImage?: boolean;
  connectedPlatforms?: { platform: string; username: string }[];
}) {
  const [copied, setCopied] = useState(false);
  const [showPlatformSelector, setShowPlatformSelector] = useState(false);
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([]);
  const [showImageInput, setShowImageInput] = useState(false);
  const [imageUrl, setImageUrl] = useState("");
  
  // Get platforms that haven't received this content yet
  const postedPlatforms = content.posted_platforms || [];
  const allPlatforms = connectedPlatforms || [];
  const availablePlatforms = allPlatforms.filter(p => !postedPlatforms.includes(p.platform.toLowerCase()));
  const hasRemainingPlatforms = availablePlatforms.length > 0;
  
  const status =
    statusConfig[content.status as keyof typeof statusConfig] ||
    statusConfig.draft;
  const StatusIcon = status.icon;
  
  const togglePlatform = (platform: string) => {
    setSelectedPlatforms(prev => 
      prev.includes(platform) 
        ? prev.filter(p => p !== platform)
        : [...prev, platform]
    );
  };
  
  const handlePostNow = () => {
    if (availablePlatforms.length === 0) {
      alert("No connected platforms. Please connect a social media account first.");
      return;
    }
    
    if (availablePlatforms.length === 1) {
      // Only one platform - post directly
      onPostNow?.(content.id, [availablePlatforms[0].platform]);
    } else if (!showPlatformSelector) {
      // Multiple platforms - show selector with all selected by default
      setSelectedPlatforms(availablePlatforms.map(p => p.platform));
      setShowPlatformSelector(true);
    } else {
      // Selector is shown - post to selected platforms
      if (selectedPlatforms.length === 0) {
        alert("Please select at least one platform.");
        return;
      }
      onPostNow?.(content.id, selectedPlatforms);
    }
  };

  const handleCopy = async () => {
    const fullText =
      content.caption +
      (content.hashtags.length > 0
        ? "\n\n" + content.hashtags.map((h) => `#${h}`).join(" ")
        : "");
    await navigator.clipboard.writeText(fullText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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
          <div className="flex items-center gap-3 flex-wrap">
            {/* Content Type Badge */}
            <div className={clsx(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold",
              content.content_type === "reel" 
                ? "bg-pink-100 dark:bg-pink-500/20 text-pink-600 dark:text-pink-400" 
                : content.content_type === "story" 
                  ? "bg-amber-100 dark:bg-amber-500/20 text-amber-600 dark:text-amber-400"
                  : content.content_type === "carousel"
                    ? "bg-indigo-100 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400"
                    : "bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400"
            )}>
              {content.content_type === "reel" ? (
                <>🎬 Reel</>
              ) : content.content_type === "story" ? (
                <>📱 Story</>
              ) : content.content_type === "carousel" ? (
                <>🖼️ Carousel</>
              ) : (
                <>📸 Post</>
              )}
            </div>
            <div
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold",
                status.bgColor,
                status.color
              )}
            >
              <StatusIcon className="w-4 h-4" />
              {status.label}
            </div>
            {content.auto_generated && (
              <span className="px-2.5 py-1 rounded-full bg-accent-100 dark:bg-accent-500/20 text-accent-600 dark:text-accent-400 text-xs font-semibold">
                AI Generated
              </span>
            )}
            {/* Show platforms this content has been posted to */}
            {postedPlatforms.length > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-surface-500">Posted to:</span>
                {postedPlatforms.map(platform => (
                  <span 
                    key={platform}
                    className="px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs font-medium flex items-center gap-1"
                  >
                    {platform === "twitter" ? (
                      <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                      </svg>
                    ) : (
                      <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                      </svg>
                    )}
                    <span className="capitalize">{platform}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl hover:bg-surface-100 dark:hover:bg-surface-800 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[60vh]">
          {/* Media Preview - Video or Image */}
          {content.video_urls && content.video_urls.length > 0 ? (
            <div className="mb-6 rounded-xl overflow-hidden bg-surface-900 relative">
              <video
                src={content.video_urls[0]}
                controls
                className="w-full max-h-96 object-contain"
                poster={content.media_urls?.[0]}
              />
              <div className="absolute top-2 left-2 px-2 py-1 rounded-md bg-black/60 text-white text-xs font-medium flex items-center gap-1">
                🎬 Video
              </div>
            </div>
          ) : content.media_urls && content.media_urls.length > 0 ? (
            <div className="mb-6 rounded-xl overflow-hidden bg-surface-900 relative group">
              <img
                src={content.media_urls[0]}
                alt="Content media"
                className="w-full max-h-96 object-contain"
              />
              {/* Replace image option for non-posted content */}
              {content.status !== "posted" && content.status !== "published" && onUpdateImage && (
                <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                  <button
                    onClick={() => setShowImageInput(true)}
                    className="px-4 py-2 rounded-lg bg-white/90 text-surface-800 font-medium text-sm hover:bg-white transition-colors"
                  >
                    Replace Image
                  </button>
                </div>
              )}
            </div>
          ) : (
            // No image attached - show attach option for non-posted content
            content.status !== "posted" && content.status !== "published" && onUpdateImage && (
              <div className="mb-6">
                {showImageInput ? (
                  <div className="p-4 rounded-xl border-2 border-dashed border-surface-300 dark:border-surface-600 bg-surface-50 dark:bg-surface-800">
                    <label className="block text-sm font-semibold text-surface-700 dark:text-surface-300 mb-2">
                      Image URL
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="url"
                        value={imageUrl}
                        onChange={(e) => setImageUrl(e.target.value)}
                        placeholder="https://example.com/image.jpg"
                        className="flex-1 px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-800 dark:text-surface-200 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      />
                      <button
                        onClick={() => {
                          if (imageUrl.trim()) {
                            onUpdateImage(content.id, imageUrl.trim());
                            setImageUrl("");
                            setShowImageInput(false);
                          }
                        }}
                        disabled={!imageUrl.trim() || isUpdatingImage}
                        className="px-4 py-2 rounded-lg bg-primary-500 text-white font-medium text-sm hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                      >
                        {isUpdatingImage ? (
                          <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        ) : (
                          <Image className="w-4 h-4" />
                        )}
                        Attach
                      </button>
                      <button
                        onClick={() => {
                          setShowImageInput(false);
                          setImageUrl("");
                        }}
                        className="px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 text-sm"
                      >
                        Cancel
                      </button>
                    </div>
                    <p className="mt-2 text-xs text-surface-500">
                      Enter a publicly accessible image URL. Required for Instagram posts.
                    </p>
                  </div>
                ) : (
                  <button
                    onClick={() => setShowImageInput(true)}
                    className="w-full p-6 rounded-xl border-2 border-dashed border-surface-300 dark:border-surface-600 hover:border-primary-400 dark:hover:border-primary-500 bg-surface-50 dark:bg-surface-800 hover:bg-primary-50 dark:hover:bg-primary-500/10 transition-colors group"
                  >
                    <div className="flex flex-col items-center gap-2">
                      <div className="p-3 rounded-full bg-surface-200 dark:bg-surface-700 group-hover:bg-primary-100 dark:group-hover:bg-primary-500/20 transition-colors">
                        <Image className="w-6 h-6 text-surface-500 dark:text-surface-400 group-hover:text-primary-600 dark:group-hover:text-primary-400" />
                      </div>
                      <span className="text-sm font-medium text-surface-600 dark:text-surface-400 group-hover:text-primary-600 dark:group-hover:text-primary-400">
                        Attach Image
                      </span>
                      <span className="text-xs text-surface-400 dark:text-surface-500">
                        Required for Instagram posts
                      </span>
                    </div>
                  </button>
                )}
              </div>
            )
          )}
          
          {/* Show image input for replacing existing image */}
          {content.media_urls && content.media_urls.length > 0 && showImageInput && (
            <div className="mb-6 p-4 rounded-xl border-2 border-primary-300 dark:border-primary-600 bg-primary-50 dark:bg-primary-500/10">
              <label className="block text-sm font-semibold text-surface-700 dark:text-surface-300 mb-2">
                New Image URL
              </label>
              <div className="flex gap-2">
                <input
                  type="url"
                  value={imageUrl}
                  onChange={(e) => setImageUrl(e.target.value)}
                  placeholder="https://example.com/image.jpg"
                  className="flex-1 px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 bg-white dark:bg-surface-700 text-surface-800 dark:text-surface-200 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
                <button
                  onClick={() => {
                    if (imageUrl.trim() && onUpdateImage) {
                      onUpdateImage(content.id, imageUrl.trim());
                      setImageUrl("");
                      setShowImageInput(false);
                    }
                  }}
                  disabled={!imageUrl.trim() || isUpdatingImage}
                  className="px-4 py-2 rounded-lg bg-primary-500 text-white font-medium text-sm hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {isUpdatingImage ? (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <Image className="w-4 h-4" />
                  )}
                  Update
                </button>
                <button
                  onClick={() => {
                    setShowImageInput(false);
                    setImageUrl("");
                  }}
                  className="px-3 py-2 rounded-lg border border-surface-300 dark:border-surface-600 text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700 text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Caption */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-3">
              Caption
            </h3>
            <div className="p-4 rounded-xl bg-surface-50 dark:bg-surface-800 border border-surface-200 dark:border-surface-700">
              <p className="text-surface-800 dark:text-surface-200 whitespace-pre-wrap leading-relaxed">
                {content.caption}
              </p>
            </div>
          </div>

          {/* Hashtags */}
          {content.hashtags.length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-3 flex items-center gap-2">
                <Hash className="w-4 h-4" />
                Hashtags ({content.hashtags.length})
              </h3>
              <div className="flex flex-wrap gap-2">
                {content.hashtags.map((tag) => (
                  <span
                    key={tag}
                    className="px-3 py-1.5 rounded-lg bg-primary-50 dark:bg-primary-500/10 text-primary-600 dark:text-primary-400 text-sm font-medium"
                  >
                    #{tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Metadata */}
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-surface-50 dark:bg-surface-800 border border-surface-200 dark:border-surface-700">
              <p className="text-xs font-semibold text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-1">
                Created
              </p>
              <p className="text-sm font-medium text-surface-800 dark:text-surface-200">
                {format(new Date(content.created_at), "MMM d, yyyy 'at' h:mm a")}
              </p>
            </div>
            {content.scheduled_for && (
              <div className="p-4 rounded-xl bg-surface-50 dark:bg-surface-800 border border-surface-200 dark:border-surface-700">
                <p className="text-xs font-semibold text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-1">
                  Scheduled For
                </p>
                <p className="text-sm font-medium text-surface-800 dark:text-surface-200">
                  {format(
                    new Date(content.scheduled_for),
                    "MMM d, yyyy 'at' h:mm a"
                  )}
                </p>
              </div>
            )}
            {content.posted_at && (
              <div className="p-4 rounded-xl bg-surface-50 dark:bg-surface-800 border border-surface-200 dark:border-surface-700">
                <p className="text-xs font-semibold text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-1">
                  Posted
                </p>
                <p className="text-sm font-medium text-surface-800 dark:text-surface-200">
                  {format(
                    new Date(content.posted_at),
                    "MMM d, yyyy 'at' h:mm a"
                  )}
                </p>
              </div>
            )}
            <div className="p-4 rounded-xl bg-surface-50 dark:bg-surface-800 border border-surface-200 dark:border-surface-700">
              <p className="text-xs font-semibold text-surface-500 dark:text-surface-400 uppercase tracking-wide mb-1">
                Character Count
              </p>
              <p className="text-sm font-medium text-surface-800 dark:text-surface-200">
                {content.caption.length} / 280
                {content.caption.length > 280 && (
                  <span className="text-red-500 ml-2">(over limit for Twitter)</span>
                )}
              </p>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-5 border-t border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50 space-y-3">
          {/* Primary Actions Row */}
          {content.status === "pending_review" ? (
            <div className="flex items-center justify-between gap-3">
              {/* Destructive action - left side */}
              {onReject && (
                <button 
                  onClick={() => {
                    if (confirm("Are you sure you want to reject and delete this content?")) {
                      onReject(content.id);
                      onClose();
                    }
                  }}
                  className="px-4 py-2.5 rounded-xl text-sm font-semibold border-2 border-red-200 dark:border-red-500/30 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors flex items-center gap-2"
                >
                  <Trash2 className="w-4 h-4" />
                  Delete
                </button>
              )}
              
              {/* Positive actions - right side */}
              <div className="flex items-center gap-2">
                {onApprove && (
                  <button 
                    onClick={() => {
                      onApprove(content.id);
                      onClose();
                    }}
                    className="px-4 py-2.5 rounded-xl text-sm font-semibold border-2 border-emerald-200 dark:border-emerald-500/30 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-500/10 transition-colors flex items-center gap-2"
                  >
                    <CheckCircle className="w-4 h-4" />
                    Approve
                  </button>
                )}
                {onPostNow && (
                  <div className="flex flex-col items-end gap-2">
                    {showPlatformSelector && availablePlatforms.length > 1 && (
                      <div className="flex items-center gap-3 p-3 rounded-xl bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700">
                        <span className="text-xs font-semibold text-surface-500 uppercase">Post to:</span>
                        <div className="flex items-center gap-2">
                          {availablePlatforms.map(p => (
                            <label 
                              key={p.platform}
                              className={clsx(
                                "flex items-center gap-2 px-3 py-1.5 rounded-lg cursor-pointer transition-all border-2",
                                selectedPlatforms.includes(p.platform)
                                  ? "bg-primary-50 dark:bg-primary-500/10 border-primary-500 text-primary-700 dark:text-primary-300"
                                  : "bg-white dark:bg-surface-700 border-surface-200 dark:border-surface-600 text-surface-600 dark:text-surface-400 hover:border-surface-300"
                              )}
                            >
                              <input
                                type="checkbox"
                                checked={selectedPlatforms.includes(p.platform)}
                                onChange={() => togglePlatform(p.platform)}
                                className="sr-only"
                              />
                              {p.platform === "twitter" ? (
                                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                                </svg>
                              ) : (
                                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                                  <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                                </svg>
                              )}
                              <span className="text-sm font-medium capitalize">{p.platform}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    )}
                    <button 
                      onClick={handlePostNow}
                      disabled={isPosting}
                      className="btn-primary text-sm px-5 py-2.5 flex items-center gap-2 disabled:opacity-50"
                    >
                      {isPosting ? (
                        <>
                          <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                          Posting...
                        </>
                      ) : (
                        <>
                          <Send className="w-4 h-4" />
                          {showPlatformSelector ? `Post to ${selectedPlatforms.length} Platform${selectedPlatforms.length !== 1 ? 's' : ''}` : 'Post Now'}
                        </>
                      )}
                    </button>
                  </div>
                )}
              </div>
            </div>
          ) : (content.status === "scheduled" || content.status === "draft") && onPostNow ? (
            <div className="flex flex-col items-end gap-2">
              {showPlatformSelector && availablePlatforms.length > 1 && (
                <div className="flex items-center gap-3 p-3 rounded-xl bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700">
                  <span className="text-xs font-semibold text-surface-500 uppercase">Post to:</span>
                  <div className="flex items-center gap-2">
                    {availablePlatforms.map(p => (
                      <label 
                        key={p.platform}
                        className={clsx(
                          "flex items-center gap-2 px-3 py-1.5 rounded-lg cursor-pointer transition-all border-2",
                          selectedPlatforms.includes(p.platform)
                            ? "bg-primary-50 dark:bg-primary-500/10 border-primary-500 text-primary-700 dark:text-primary-300"
                            : "bg-white dark:bg-surface-700 border-surface-200 dark:border-surface-600 text-surface-600 dark:text-surface-400 hover:border-surface-300"
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={selectedPlatforms.includes(p.platform)}
                          onChange={() => togglePlatform(p.platform)}
                          className="sr-only"
                        />
                        {p.platform === "twitter" ? (
                          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                          </svg>
                        ) : (
                          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                          </svg>
                        )}
                        <span className="text-sm font-medium capitalize">{p.platform}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
              <button 
                onClick={handlePostNow}
                disabled={isPosting}
                className="btn-primary text-sm px-5 py-2.5 flex items-center gap-2 disabled:opacity-50"
              >
                {isPosting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Posting...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    {showPlatformSelector ? `Post to ${selectedPlatforms.length} Platform${selectedPlatforms.length !== 1 ? 's' : ''}` : 'Post Now'}
                  </>
                )}
              </button>
            </div>
          ) : content.status === "failed" ? (
            <div className="flex items-center justify-between gap-3">
              {/* Error message */}
              {content.error_message && (
                <div className="flex-1 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10 px-3 py-2 rounded-lg truncate" title={content.error_message}>
                  {content.error_message}
                </div>
              )}
              
              <div className="flex items-center gap-2">
                {/* Delete button */}
                {onDelete && (
                  <button 
                    onClick={() => {
                      if (confirm("Are you sure you want to delete this content?")) {
                        onDelete(content.id);
                        onClose();
                      }
                    }}
                    className="px-4 py-2.5 rounded-xl text-sm font-semibold border-2 border-red-200 dark:border-red-500/30 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors flex items-center gap-2"
                  >
                    <Trash2 className="w-4 h-4" />
                    Delete
                  </button>
                )}
                
                {/* Retry button */}
                {onRetry && (
                  <button 
                    onClick={() => onRetry(content.id)}
                    disabled={isRetrying}
                    className="btn-primary text-sm px-5 py-2.5 flex items-center gap-2 disabled:opacity-50"
                  >
                    {isRetrying ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Retrying...
                      </>
                    ) : (
                      <>
                        <RefreshCw className="w-4 h-4" />
                        Retry
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          ) : (content.status === "posted" || content.status === "published") && hasRemainingPlatforms && onPostNow ? (
            // Already posted but can post to other platforms
            <div className="flex flex-col items-end gap-2">
              <div className="text-sm text-surface-500 dark:text-surface-400">
                Post to remaining platforms:
              </div>
              {showPlatformSelector && (
                <div className="flex items-center gap-3 p-3 rounded-xl bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700">
                  <span className="text-xs font-semibold text-surface-500 uppercase">Select:</span>
                  <div className="flex items-center gap-2">
                    {availablePlatforms.map(p => (
                      <label 
                        key={p.platform}
                        className={clsx(
                          "flex items-center gap-2 px-3 py-1.5 rounded-lg cursor-pointer transition-all border-2",
                          selectedPlatforms.includes(p.platform)
                            ? "bg-primary-50 dark:bg-primary-500/10 border-primary-500 text-primary-700 dark:text-primary-300"
                            : "bg-white dark:bg-surface-700 border-surface-200 dark:border-surface-600 text-surface-600 dark:text-surface-400 hover:border-surface-300"
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={selectedPlatforms.includes(p.platform)}
                          onChange={() => togglePlatform(p.platform)}
                          className="sr-only"
                        />
                        {p.platform === "twitter" ? (
                          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                          </svg>
                        ) : (
                          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                          </svg>
                        )}
                        <span className="text-sm font-medium capitalize">{p.platform}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
              <button 
                onClick={handlePostNow}
                disabled={isPosting}
                className="btn-primary text-sm px-5 py-2.5 flex items-center gap-2 disabled:opacity-50"
              >
                {isPosting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Posting...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    {showPlatformSelector ? `Post to ${selectedPlatforms.length} Platform${selectedPlatforms.length !== 1 ? 's' : ''}` : 'Post to Other Platforms'}
                  </>
                )}
              </button>
            </div>
          ) : null}
          
          {/* Utility Actions Row */}
          <div className="flex items-center justify-between pt-3 border-t border-surface-200 dark:border-surface-700">
            <button
              onClick={handleCopy}
              className={clsx(
                "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all",
                copied
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-surface-500 hover:text-surface-700 dark:hover:text-surface-300"
              )}
            >
              {copied ? (
                <>
                  <CheckCircle className="w-4 h-4" />
                  Copied!
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  Copy
                </>
              )}
            </button>
            <button
              onClick={onClose}
              className="px-3 py-2 rounded-lg text-sm font-medium text-surface-500 hover:text-surface-700 dark:hover:text-surface-300 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function CreateContentModal({
  personas,
  onClose,
  onGenerate,
  isGenerating,
}: {
  personas: Persona[];
  onClose: () => void;
  onGenerate: (personaId: string, options?: { topic?: string; content_type?: 'post' | 'video_post' | 'story' | 'reel'; generate_video?: boolean }) => void;
  isGenerating: boolean;
}) {
  const [selectedPersonaId, setSelectedPersonaId] = useState<string>(
    personas[0]?.id || ""
  );
  const [topic, setTopic] = useState("");
  const [contentType, setContentType] = useState<'post' | 'video_post' | 'story' | 'reel'>('post');
  
  // Video is auto-generated for video posts, stories, and reels
  const willGenerateVideo = contentType === 'video_post' || contentType === 'story' || contentType === 'reel';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-surface-900 rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-surface-200 dark:border-surface-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent-500 to-pink-500 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-display font-bold text-surface-900 dark:text-surface-100">
                Generate Content
              </h2>
              <p className="text-sm text-surface-500">
                AI will create a post for your persona
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl hover:bg-surface-100 dark:hover:bg-surface-800 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5">
          {personas.length === 0 ? (
            <div className="text-center py-8">
              <div className="w-12 h-12 rounded-xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center mx-auto mb-3">
                <User className="w-6 h-6 text-surface-400" />
              </div>
              <p className="text-surface-600 dark:text-surface-400 mb-4">
                No personas available. Create a persona first.
              </p>
              <Link
                href="/personas"
                className="btn-primary inline-flex items-center gap-2"
              >
                <Plus className="w-4 h-4" />
                Create Persona
              </Link>
            </div>
          ) : (
            <>
              {/* Persona Selection */}
              <div>
                <label className="block text-sm font-semibold text-surface-700 dark:text-surface-300 mb-2">
                  Select Persona
                </label>
                <div className="grid gap-2">
                  {personas.map((persona) => (
                    <button
                      key={persona.id}
                      onClick={() => setSelectedPersonaId(persona.id)}
                      className={clsx(
                        "flex items-center gap-3 p-3 rounded-xl border-2 transition-all text-left",
                        selectedPersonaId === persona.id
                          ? "border-primary-500 bg-primary-50 dark:bg-primary-500/10"
                          : "border-surface-200 dark:border-surface-700 hover:border-surface-300 dark:hover:border-surface-600"
                      )}
                    >
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center text-white font-bold shrink-0">
                        {persona.name.charAt(0)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="font-semibold text-surface-900 dark:text-surface-100">
                          {persona.name}
                        </p>
                        <p className="text-xs text-surface-500">
                          {persona.niche?.join(", ") || "General"}
                        </p>
                        {persona.bio && (
                          <p className="text-xs text-surface-600 dark:text-surface-400 mt-1 line-clamp-2">
                            {persona.bio}
                          </p>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Content Type Selection */}
              <div>
                <label className="block text-sm font-semibold text-surface-700 dark:text-surface-300 mb-2">
                  Content Type
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { value: 'post', label: 'Image Post', desc: 'Photo in feed', icon: '📸' },
                    { value: 'video_post', label: 'Video Post', desc: 'Video in feed', icon: '🎥' },
                    { value: 'story', label: 'Story', desc: 'Vertical video', icon: '📱' },
                    { value: 'reel', label: 'Reel', desc: 'Vertical video', icon: '🎬' },
                  ].map((type) => (
                    <button
                      key={type.value}
                      type="button"
                      onClick={() => setContentType(type.value as 'post' | 'video_post' | 'story' | 'reel')}
                      className={clsx(
                        "flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all",
                        contentType === type.value
                          ? "border-primary-500 bg-primary-50 dark:bg-primary-500/10"
                          : "border-surface-200 dark:border-surface-700 hover:border-surface-300 dark:hover:border-surface-600"
                      )}
                    >
                      <span className="text-xl">{type.icon}</span>
                      <span className="font-semibold text-sm text-surface-900 dark:text-surface-100">
                        {type.label}
                      </span>
                      <span className="text-xs text-surface-500">{type.desc}</span>
                    </button>
                  ))}
                </div>
                {willGenerateVideo && (
                  <p className="text-xs text-primary-600 dark:text-primary-400 mt-2 flex items-center gap-1">
                    <span>🎥</span> Video will be generated automatically (takes 1-3 min)
                  </p>
                )}
              </div>

              {/* Topic Input */}
              <div>
                <label className="block text-sm font-semibold text-surface-700 dark:text-surface-300 mb-2">
                  Topic (optional)
                </label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g., morning routine, productivity tips..."
                  className="input"
                />
                <p className="text-xs text-surface-500 mt-1.5">
                  Leave empty to let AI choose based on persona's niche
                </p>
              </div>

            </>
          )}
        </div>

        {/* Footer */}
        {personas.length > 0 && (
          <div className="flex items-center justify-end gap-3 p-5 border-t border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-sm font-semibold bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-300 hover:bg-surface-200 dark:hover:bg-surface-600 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => onGenerate(selectedPersonaId, { 
                topic: topic || undefined, 
                content_type: contentType,
                generate_video: willGenerateVideo,
              })}
              disabled={!selectedPersonaId || isGenerating}
              className="btn-primary text-sm px-4 py-2 flex items-center gap-2 disabled:opacity-50"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {willGenerateVideo ? 'Generating Video...' : 'Generating...'}
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Generate {contentType === 'post' ? 'Post' : contentType === 'video_post' ? 'Video Post' : contentType === 'story' ? 'Story' : 'Reel'}
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ContentPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [personaFilter, setPersonaFilter] = useState<string>("all");
  const [selectedContent, setSelectedContent] = useState<Content | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const queryClient = useQueryClient();

  const { data: content, isLoading } = useQuery<Content[]>({
    queryKey: ["content"],
    queryFn: () => api.getContent(),
  });

  const { data: personas } = useQuery<Persona[]>({
    queryKey: ["personas"],
    queryFn: api.getPersonas,
  });

  // Fetch platform accounts for the selected content's persona
  const { data: platformAccounts } = useQuery<PlatformAccount[]>({
    queryKey: ["platform-accounts", selectedContent?.persona_id],
    queryFn: () => api.getPlatformAccounts(selectedContent!.persona_id),
    enabled: !!selectedContent,
  });

  const generateContentMutation = useMutation({
    mutationFn: ({ personaId, options }: { personaId: string; options?: { topic?: string; content_type?: 'post' | 'video_post' | 'story' | 'reel'; generate_video?: boolean } }) =>
      api.generateContent(personaId, options),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content"] });
      setShowCreateModal(false);
    },
  });

  const deleteContentMutation = useMutation({
    mutationFn: (contentId: string) => api.deleteContent(contentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content"] });
    },
  });

  const approveContentMutation = useMutation({
    mutationFn: (contentId: string) => api.approveContent(contentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content"] });
    },
  });

  const rejectContentMutation = useMutation({
    mutationFn: (contentId: string) => api.rejectContent(contentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content"] });
    },
  });

  const postNowMutation = useMutation({
    mutationFn: ({ contentId, platforms }: { contentId: string; platforms: string[] }) => 
      api.postContentNow(contentId, platforms),
    onSuccess: () => {
      // Immediately invalidate to show "scheduled" status
      queryClient.invalidateQueries({ queryKey: ["content"] });
      setSelectedContent(null);
      
      // Refetch again after delays to catch async status updates from Celery
      // The posting happens in the background, so we poll a few times
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["content"] }), 2000);
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["content"] }), 5000);
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["content"] }), 10000);
    },
  });

  const retryMutation = useMutation({
    mutationFn: (contentId: string) => api.retryContent(contentId),
    onSuccess: () => {
      // Immediately invalidate to show "scheduled" status
      queryClient.invalidateQueries({ queryKey: ["content"] });
      setSelectedContent(null);
      
      // Refetch again after delays to catch async status updates from Celery
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["content"] }), 2000);
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["content"] }), 5000);
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["content"] }), 10000);
    },
  });

  const updateImageMutation = useMutation({
    mutationFn: ({ contentId, imageUrl }: { contentId: string; imageUrl: string }) => 
      api.updateContent(contentId, { media_urls: [imageUrl] }),
    onSuccess: (updatedContent) => {
      queryClient.invalidateQueries({ queryKey: ["content"] });
      // Update the selected content with the new image
      setSelectedContent(updatedContent);
    },
  });

  const filteredContent = content?.filter((item) => {
    const matchesSearch =
      item.caption.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.hashtags.some((h) =>
        h.toLowerCase().includes(searchQuery.toLowerCase())
      );
    const matchesStatus =
      statusFilter === "all" || item.status === statusFilter;
    const matchesPersona =
      personaFilter === "all" || item.persona_id === personaFilter;
    return matchesSearch && matchesStatus && matchesPersona;
  });

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Content Detail Modal */}
      {selectedContent && (
        <ContentModal
          content={selectedContent}
          onClose={() => setSelectedContent(null)}
          onApprove={(id) => approveContentMutation.mutate(id)}
          onReject={(id) => rejectContentMutation.mutate(id)}
          onDelete={(id) => {
            deleteContentMutation.mutate(id);
            setSelectedContent(null);
          }}
          onPostNow={(id, platforms) => postNowMutation.mutate({ contentId: id, platforms })}
          onRetry={(id) => retryMutation.mutate(id)}
          onUpdateImage={(id, imageUrl) => updateImageMutation.mutate({ contentId: id, imageUrl })}
          isPosting={postNowMutation.isPending}
          isRetrying={retryMutation.isPending}
          isUpdatingImage={updateImageMutation.isPending}
          connectedPlatforms={platformAccounts?.filter(a => a.is_connected).map(a => ({ 
            platform: a.platform, 
            username: a.username 
          }))}
        />
      )}

      {/* Create Content Modal */}
      {showCreateModal && (
        <CreateContentModal
          personas={personas || []}
          onClose={() => setShowCreateModal(false)}
          onGenerate={(personaId, options) =>
            generateContentMutation.mutate({ personaId, options })
          }
          isGenerating={generateContentMutation.isPending}
        />
      )}

      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent-500 to-pink-500 flex items-center justify-center">
              <FileText className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-3xl font-display font-bold text-surface-900 dark:text-surface-100">
              Content
            </h1>
          </div>
          <p className="text-surface-500 dark:text-surface-400 font-medium">
            Manage scheduled and published content
          </p>
        </div>
        <button 
          onClick={() => setShowCreateModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Sparkles className="w-4 h-4" />
          Generate Content
        </button>
      </div>

      {/* Filters */}
      <div className="card flex flex-col lg:flex-row items-stretch lg:items-center gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-400" />
          <input
            type="text"
            placeholder="Search content..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input pl-12"
          />
        </div>

        {/* Persona Filter */}
        {personas && personas.length > 0 && (
          <div className="flex items-center gap-2">
            <User className="w-4 h-4 text-surface-400 hidden sm:block" />
            <select
              value={personaFilter}
              onChange={(e) => setPersonaFilter(e.target.value)}
              className="input py-2 pr-8 min-w-[140px]"
            >
              <option value="all">All Personas</option>
              {personas.map((persona) => (
                <option key={persona.id} value={persona.id}>
                  {persona.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Status Filter */}
        <div className="flex items-center gap-1 p-1 bg-surface-100 dark:bg-surface-800 rounded-xl overflow-x-auto">
          {["all", "pending_review", "scheduled", "posted", "failed"].map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={clsx(
                "px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-300 whitespace-nowrap",
                statusFilter === status
                  ? "bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 shadow-sm"
                  : "text-surface-500 hover:text-surface-700 dark:hover:text-surface-300"
              )}
            >
              {status === "pending_review"
                ? "Pending"
                : status === "posted"
                ? "Posted"
                : status.charAt(0).toUpperCase() + status.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Content Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="card h-80 animate-pulse bg-surface-100 dark:bg-surface-800"
            />
          ))}
        </div>
      ) : filteredContent && filteredContent.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {filteredContent.map((item, index) => {
            const status =
              statusConfig[item.status as keyof typeof statusConfig] ||
              statusConfig.draft;
            const StatusIcon = status.icon;

            return (
              <div
                key={item.id}
                className="card-hover group animate-slide-up overflow-hidden cursor-pointer"
                style={{ animationDelay: `${index * 50}ms` }}
                onClick={() => setSelectedContent(item)}
              >
                {/* Media placeholder - aspect ratio based on content type */}
                <div className="relative -mx-6 -mt-6 mb-4 bg-gradient-to-br from-surface-100 to-surface-200 dark:from-surface-800 dark:to-surface-700 flex items-center justify-center overflow-hidden aspect-square">
                  {item.video_urls && item.video_urls.length > 0 ? (
                    <video
                      src={item.video_urls[0]}
                      className="w-full h-full object-cover object-top"
                      muted
                      loop
                      playsInline
                      onMouseEnter={(e) => e.currentTarget.play()}
                      onMouseLeave={(e) => { e.currentTarget.pause(); e.currentTarget.currentTime = 0; }}
                    />
                  ) : item.media_urls && item.media_urls.length > 0 ? (
                    <img
                      src={item.media_urls[0]}
                      alt="Content preview"
                      className={clsx(
                        "w-full h-full object-cover",
                        (item.content_type === "reel" || item.content_type === "story") && "object-top"
                      )}
                    />
                  ) : (
                    <Image className="w-12 h-12 text-surface-300 dark:text-surface-600" />
                  )}
                  {/* Content Type Badge */}
                  <div className={clsx(
                    "absolute top-2 left-2 px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm",
                    item.content_type === "reel" 
                      ? "bg-gradient-to-r from-pink-500 to-rose-500 text-white" 
                      : item.content_type === "story" 
                        ? "bg-gradient-to-r from-amber-500 to-orange-500 text-white"
                        : item.content_type === "carousel"
                          ? "bg-gradient-to-r from-indigo-500 to-purple-500 text-white"
                          : "bg-gradient-to-r from-emerald-500 to-teal-500 text-white"
                  )}>
                    {item.content_type === "reel" ? (
                      <>🎬 Reel</>
                    ) : item.content_type === "story" ? (
                      <>📱 Story</>
                    ) : item.content_type === "carousel" ? (
                      <>🖼️ Carousel</>
                    ) : (
                      <>📸 Post</>
                    )}
                  </div>
                  {/* Status badge */}
                  <div
                    className={clsx(
                      "absolute top-2 right-2 flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold shadow-sm",
                      status.bgColor,
                      status.color
                    )}
                  >
                    <StatusIcon className="w-3.5 h-3.5" />
                    {status.label}
                  </div>
                  {/* Click hint */}
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity bg-white/90 dark:bg-surface-900/90 px-3 py-1.5 rounded-full text-xs font-semibold text-surface-700 dark:text-surface-200 flex items-center gap-1.5">
                      <Eye className="w-3.5 h-3.5" />
                      Click to view
                    </div>
                  </div>
                </div>

                {/* Content */}
                <div className="space-y-3">
                  <p 
                    className="text-surface-800 dark:text-surface-200 line-clamp-3 text-sm leading-relaxed cursor-help"
                    title={item.caption}
                  >
                    {item.caption}
                  </p>

                  {/* Hashtags */}
                  <div className="flex flex-wrap gap-1.5">
                    {item.hashtags.slice(0, 4).map((tag) => (
                      <span
                        key={tag}
                        className="px-2 py-0.5 rounded-md bg-primary-50 dark:bg-primary-500/10 text-primary-600 dark:text-primary-400 text-xs font-medium"
                      >
                        #{tag}
                      </span>
                    ))}
                    {item.hashtags.length > 4 && (
                      <span className="px-2 py-0.5 rounded-md bg-surface-100 dark:bg-surface-700 text-surface-500 text-xs font-medium">
                        +{item.hashtags.length - 4}
                      </span>
                    )}
                  </div>

                  {/* Footer */}
                  <div className="flex items-center justify-between pt-3 border-t border-surface-100 dark:border-surface-700">
                    <div className="flex items-center gap-3">
                      {/* Persona indicator */}
                      {personas && (() => {
                        const persona = personas.find(p => p.id === item.persona_id);
                        return persona ? (
                          <div className="flex items-center gap-1.5">
                            <div className="w-5 h-5 rounded-full bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center text-white text-xs font-bold">
                              {persona.name.charAt(0)}
                            </div>
                            <span className="text-xs font-medium text-surface-600 dark:text-surface-400 hidden sm:inline">
                              {persona.name}
                            </span>
                          </div>
                        ) : null;
                      })()}
                      <div className="flex items-center gap-1.5 text-surface-500 text-xs font-medium">
                        <Clock className="w-3.5 h-3.5" />
                        {item.scheduled_for
                          ? format(new Date(item.scheduled_for), "MMM d, h:mm a")
                          : formatDistanceToNow(new Date(item.created_at), {
                              addSuffix: true,
                            })}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          // Edit action
                        }}
                        className="p-1.5 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-700 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors"
                      >
                        <Edit3 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm("Are you sure you want to delete this content?")) {
                            deleteContentMutation.mutate(item.id);
                          }
                        }}
                        disabled={deleteContentMutation.isPending}
                        className="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-500/10 text-surface-400 hover:text-red-500 transition-colors disabled:opacity-50"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="card text-center py-16">
          <div className="w-16 h-16 rounded-2xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center mx-auto mb-4">
            <FileText className="w-8 h-8 text-surface-400" />
          </div>
          <h3 className="font-semibold text-lg text-surface-900 dark:text-surface-100 mb-2">
            {searchQuery || statusFilter !== "all"
              ? "No matching content"
              : "No content yet"}
          </h3>
          <p className="text-surface-500 dark:text-surface-400 mb-6">
            {searchQuery || statusFilter !== "all"
              ? "Try adjusting your search or filter"
              : "Content will appear here as your personas create it"}
          </p>
        </div>
      )}
    </div>
  );
}
