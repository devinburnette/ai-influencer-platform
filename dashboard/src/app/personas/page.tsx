"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Users,
  Plus,
  Search,
  Filter,
  Grid3X3,
  List,
} from "lucide-react";
import { useState } from "react";
import { PersonaCard } from "@/components/PersonaCard";
import { api, Persona } from "@/lib/api";
import Link from "next/link";
import { clsx } from "clsx";

export default function PersonasPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<"list" | "grid">("list");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">(
    "all"
  );

  const { data: personas, isLoading } = useQuery<Persona[]>({
    queryKey: ["personas"],
    queryFn: api.getPersonas,
  });

  const filteredPersonas = personas?.filter((persona) => {
    const matchesSearch =
      persona.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      persona.bio.toLowerCase().includes(searchQuery.toLowerCase()) ||
      persona.niche.some((n) =>
        n.toLowerCase().includes(searchQuery.toLowerCase())
      );
    const matchesStatus =
      statusFilter === "all" ||
      (statusFilter === "active" && persona.is_active) ||
      (statusFilter === "inactive" && !persona.is_active);
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
              <Users className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-3xl font-display font-bold text-surface-900 dark:text-surface-100">
              Personas
            </h1>
          </div>
          <p className="text-surface-500 dark:text-surface-400 font-medium">
            Manage your AI influencer personas
          </p>
        </div>
        <Link href="/personas/new" className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Create Persona
        </Link>
      </div>

      {/* Filters */}
      <div className="card flex flex-col sm:flex-row items-stretch sm:items-center gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-surface-400" />
          <input
            type="text"
            placeholder="Search personas..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input pl-12"
          />
        </div>

        {/* Status Filter */}
        <div className="flex items-center gap-2 p-1 bg-surface-100 dark:bg-surface-800 rounded-xl">
          {(["all", "active", "inactive"] as const).map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={clsx(
                "px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-300",
                statusFilter === status
                  ? "bg-white dark:bg-surface-700 text-surface-900 dark:text-surface-100 shadow-sm"
                  : "text-surface-500 hover:text-surface-700 dark:hover:text-surface-300"
              )}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </button>
          ))}
        </div>

        {/* View Mode */}
        <div className="flex items-center gap-1 p-1 bg-surface-100 dark:bg-surface-800 rounded-xl">
          <button
            onClick={() => setViewMode("list")}
            className={clsx(
              "p-2 rounded-lg transition-all duration-300",
              viewMode === "list"
                ? "bg-white dark:bg-surface-700 shadow-sm"
                : "text-surface-500 hover:text-surface-700 dark:hover:text-surface-300"
            )}
          >
            <List className="w-5 h-5" />
          </button>
          <button
            onClick={() => setViewMode("grid")}
            className={clsx(
              "p-2 rounded-lg transition-all duration-300",
              viewMode === "grid"
                ? "bg-white dark:bg-surface-700 shadow-sm"
                : "text-surface-500 hover:text-surface-700 dark:hover:text-surface-300"
            )}
          >
            <Grid3X3 className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Personas List/Grid */}
      {isLoading ? (
        <div
          className={clsx(
            viewMode === "grid"
              ? "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6"
              : "space-y-4"
          )}
        >
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className={clsx(
                "card animate-pulse bg-surface-100 dark:bg-surface-800",
                viewMode === "grid" ? "h-64" : "h-32"
              )}
            />
          ))}
        </div>
      ) : filteredPersonas && filteredPersonas.length > 0 ? (
        <div
          className={clsx(
            viewMode === "grid"
              ? "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6"
              : "space-y-4"
          )}
        >
          {filteredPersonas.map((persona, index) => (
            <PersonaCard
              key={persona.id}
              persona={persona}
              style={{ animationDelay: `${index * 50}ms` }}
            />
          ))}
        </div>
      ) : (
        <div className="card text-center py-16">
          <div className="w-16 h-16 rounded-2xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center mx-auto mb-4">
            <Users className="w-8 h-8 text-surface-400" />
          </div>
          <h3 className="font-semibold text-lg text-surface-900 dark:text-surface-100 mb-2">
            {searchQuery || statusFilter !== "all"
              ? "No matching personas"
              : "No personas yet"}
          </h3>
          <p className="text-surface-500 dark:text-surface-400 mb-6">
            {searchQuery || statusFilter !== "all"
              ? "Try adjusting your search or filter"
              : "Create your first AI influencer to get started"}
          </p>
          {!searchQuery && statusFilter === "all" && (
            <Link
              href="/personas/new"
              className="btn-primary inline-flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Create Persona
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
