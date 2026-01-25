"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
    Users,
    PieChart,
    Send,
    Phone,
    ShoppingBag,
    MessageSquare,
    FileText,
    Tag,
    DollarSign,
    Clock,
    Settings,
    LogOut,
    ChevronRight,
    Zap,
    GitBranch,
    Plus,
    X,
    Play,
    CheckCircle,
    AlertCircle
} from "lucide-react";

// -- Types --
interface Contact {
    id: string;
    email: string;
    first_name: string;
    last_name: string;
    lifecycle_stage: string;
    engagement_score: number;
    lifetime_value: number;
    last_seen_at: string;
}

interface TimelineEvent {
    id: string;
    event_type: string;
    summary: string;
    timeline_type: string;
    occurred_at?: string;
    created_at?: string;
    started_at?: string;
    transcript?: string;
    source_channel?: string;
}

interface Pipeline {
    id: string;
    name: string;
    description: string;
    is_default: boolean;
    stages: PipelineStage[];
}

interface PipelineStage {
    id: string;
    name: string;
    color: string;
    sort_order: number;
    probability: number;
}

interface Workflow {
    id: string;
    name: string;
    trigger_type: string;
    trigger_event: string;
    is_active: boolean;
    created_at: string;
}

interface ContactTag {
    id: string;
    tag: string;
    created_by: string;
    created_at: string;
}

// -- Sidebar Component --
function Sidebar({ activeTab, setActiveTab }: { activeTab: string; setActiveTab: (tab: string) => void }) {
    const navItems = [
        { icon: Users, label: "Contacts", id: "contacts" },
        { icon: GitBranch, label: "Pipelines", id: "pipelines" },
        { icon: Zap, label: "Workflows", id: "workflows" },
        { icon: PieChart, label: "Segments", id: "segments" },
        { icon: Send, label: "Campaigns", id: "campaigns" },
        { icon: Phone, label: "Voice", id: "voice" },
        { icon: ShoppingBag, label: "Commerce", id: "commerce" },
    ];

    return (
        <aside className="w-64 bg-[#2C3E50] min-h-screen flex flex-col fixed left-0 top-0">
            {/* Logo */}
            <div className="px-6 py-6 border-b border-white/10">
                <div className="flex items-center gap-3">
                    <div
                        className="w-10 h-10 bg-gradient-to-br from-[#00B894] to-[#55EFC4] flex items-center justify-center"
                        style={{ clipPath: "polygon(0 0, 100% 0, 100% 75%, 75% 100%, 0 100%)" }}
                    >
                        <span className="text-white text-lg font-bold">E</span>
                    </div>
                    <div>
                        <span className="font-serif text-xl font-bold text-white">Elastique</span>
                        <p className="text-[10px] text-[#00B894] uppercase tracking-[0.15em] font-semibold">CRM Platform</p>
                    </div>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 py-6">
                <p className="px-6 text-[10px] text-white/40 uppercase tracking-wider font-semibold mb-4">Main Menu</p>
                {navItems.map((item) => {
                    const Icon = item.icon;
                    const isActive = activeTab === item.id;
                    return (
                        <button
                            key={item.id}
                            onClick={() => setActiveTab(item.id)}
                            className={`
                                w-full flex items-center gap-3 px-6 py-3 mx-3 mb-1 transition-all group text-left
                                ${isActive
                                    ? "bg-[#00B894] text-white"
                                    : "text-white/60 hover:text-white hover:bg-white/5"
                                }
                            `}
                            style={isActive ? { clipPath: "polygon(0 0, 100% 0, 100% 70%, 92% 100%, 0 100%)", width: "calc(100% - 24px)" } : { width: "calc(100% - 24px)" }}
                        >
                            <Icon size={18} strokeWidth={1.5} />
                            <span className="text-sm font-medium flex-1">{item.label}</span>
                            {isActive && <ChevronRight size={14} className="opacity-60" />}
                        </button>
                    );
                })}

                <div className="my-6 mx-6 border-t border-white/10" />

                <p className="px-6 text-[10px] text-white/40 uppercase tracking-wider font-semibold mb-4">Settings</p>
                <button className="w-full flex items-center gap-3 px-6 py-3 mx-3 text-white/60 hover:text-white hover:bg-white/5 transition-all text-left" style={{ width: "calc(100% - 24px)" }}>
                    <Settings size={18} strokeWidth={1.5} />
                    <span className="text-sm font-medium">Settings</span>
                </button>
            </nav>

            {/* User Section */}
            <div className="px-6 py-4 border-t border-white/10">
                <div className="flex items-center gap-3">
                    <div
                        className="w-9 h-9 bg-gradient-to-br from-white/20 to-white/10 flex items-center justify-center text-white text-sm font-semibold"
                        style={{ clipPath: "polygon(0 0, 100% 0, 100% 75%, 75% 100%, 0 100%)" }}
                    >
                        A
                    </div>
                    <div className="flex-1">
                        <p className="text-sm text-white font-medium">Admin</p>
                        <p className="text-[11px] text-white/40">admin@elastique.com</p>
                    </div>
                    <button className="text-white/40 hover:text-white transition">
                        <LogOut size={16} strokeWidth={1.5} />
                    </button>
                </div>
            </div>
        </aside>
    );
}

// -- Contact Row Component --
function ContactRow({ contact, onSelect, isSelected }: { contact: Contact; onSelect: () => void; isSelected: boolean }) {
    const stageColors: Record<string, string> = {
        lead: "bg-blue-50 text-blue-600 border-l-2 border-blue-400",
        customer: "bg-emerald-50 text-emerald-600 border-l-2 border-emerald-400",
        vip: "bg-purple-50 text-purple-600 border-l-2 border-purple-400",
        visitor: "bg-gray-50 text-gray-500 border-l-2 border-gray-300",
    };

    return (
        <tr
            onClick={onSelect}
            className={`
                border-b border-[#E8EDEF] cursor-pointer transition-all duration-150
                ${isSelected
                    ? "bg-[#00B894]/10 border-l-4 border-l-[#00B894]"
                    : "hover:bg-[#F8FAFB]"
                }
            `}
        >
            <td className="py-4 px-5">
                <div className="flex items-center gap-4">
                    <div
                        className="w-10 h-10 bg-gradient-to-br from-[#00B894] to-[#55EFC4] flex items-center justify-center text-sm font-bold text-white"
                        style={{ clipPath: "polygon(0 0, 100% 0, 100% 75%, 75% 100%, 0 100%)" }}
                    >
                        {contact.first_name?.[0] || "?"}
                    </div>
                    <div>
                        <p className="font-semibold text-[#2C3E50]">{contact.first_name} {contact.last_name}</p>
                        <p className="text-xs text-[#636E72] mt-0.5">{contact.email}</p>
                    </div>
                </div>
            </td>
            <td className="py-4 px-5">
                <span className={`px-3 py-1.5 text-xs font-semibold ${stageColors[contact.lifecycle_stage] || stageColors.visitor}`}>
                    {contact.lifecycle_stage?.toUpperCase()}
                </span>
            </td>
            <td className="py-4 px-5 text-right">
                <span className="font-mono text-sm text-[#2C3E50]">{contact.engagement_score}</span>
            </td>
            <td className="py-4 px-5 text-right">
                <span className="font-mono text-sm text-[#00B894] font-bold">${contact.lifetime_value?.toFixed(0) || "0"}</span>
            </td>
        </tr>
    );
}

// -- Timeline Item Component --
function TimelineItem({ event }: { event: TimelineEvent }) {
    const iconMap: Record<string, { Icon: React.ElementType; accent: string }> = {
        chat_started: { Icon: MessageSquare, accent: "#3498db" },
        chat_session: { Icon: MessageSquare, accent: "#3498db" },
        voice_call_completed: { Icon: Phone, accent: "#9b59b6" },
        order_placed: { Icon: ShoppingBag, accent: "#00B894" },
        note: { Icon: FileText, accent: "#f39c12" },
        ticket: { Icon: Tag, accent: "#e74c3c" },
        deal: { Icon: DollarSign, accent: "#27ae60" },
        event: { Icon: Clock, accent: "#636E72" },
    };

    const config = iconMap[event.timeline_type] || iconMap[event.event_type] || { Icon: Clock, accent: "#636E72" };
    const EventIcon = config.Icon;
    const time = event.occurred_at || event.created_at || event.started_at || "";
    const formattedTime = time ? new Date(time).toLocaleString() : "Unknown";

    return (
        <div
            className="flex gap-4 py-4 border-l-2 pl-4 ml-2 mb-2 bg-white"
            style={{ borderLeftColor: config.accent }}
        >
            <div
                className="w-10 h-10 bg-[#F8FAFB] flex items-center justify-center flex-shrink-0 border border-[#E8EDEF]"
                style={{ clipPath: "polygon(0 0, 100% 0, 100% 75%, 75% 100%, 0 100%)" }}
            >
                <EventIcon size={18} strokeWidth={1.5} style={{ color: config.accent }} />
            </div>
            <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[#2C3E50]">{event.summary || event.event_type}</p>
                <p className="text-xs text-[#636E72] mt-1">{formattedTime}</p>
                {event.transcript && (
                    <div className="mt-3 text-xs text-[#636E72] bg-[#F8FAFB] p-3 border-l-2 border-[#00B894]">
                        "{event.transcript}"
                    </div>
                )}
                {event.source_channel && (
                    <span className="inline-block mt-2 text-[10px] px-2 py-1 bg-[#2C3E50] text-white uppercase tracking-wider font-semibold">
                        {event.source_channel}
                    </span>
                )}
            </div>
        </div>
    );
}

// -- Stats Card Component --
function StatCard({ label, value, trend, Icon }: { label: string; value: string; trend?: string; Icon: React.ElementType }) {
    return (
        <div
            className="bg-white p-5 depth-2 border-b-2 border-[#00B894]"
            style={{ clipPath: "polygon(0 0, 100% 0, 100% 85%, 90% 100%, 0 100%)" }}
        >
            <div className="flex items-start justify-between">
                <div>
                    <p className="text-[10px] text-[#636E72] uppercase tracking-wider font-semibold">{label}</p>
                    <p className="text-2xl font-bold text-[#2C3E50] mt-1">{value}</p>
                    {trend && <p className="text-xs text-[#00B894] mt-1">{trend}</p>}
                </div>
                <div
                    className="w-10 h-10 bg-[#F0F4F5] flex items-center justify-center"
                    style={{ clipPath: "polygon(0 0, 100% 0, 100% 75%, 75% 100%, 0 100%)" }}
                >
                    <Icon size={18} strokeWidth={1.5} className="text-[#00B894]" />
                </div>
            </div>
        </div>
    );
}

// -- Pipeline Kanban Stage --
function PipelineStageCard({ stage, deals }: { stage: PipelineStage; deals: number }) {
    return (
        <div
            className="bg-white p-4 min-w-[200px] depth-1"
            style={{ clipPath: "polygon(0 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%)" }}
        >
            <div className="flex items-center gap-2 mb-3">
                <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: stage.color }}
                />
                <span className="text-sm font-semibold text-[#2C3E50]">{stage.name}</span>
            </div>
            <div className="flex items-center justify-between text-xs text-[#636E72]">
                <span>{stage.probability}% prob</span>
                <span className="font-mono">{deals} deals</span>
            </div>
        </div>
    );
}

// -- Workflow Card --
function WorkflowCard({ workflow, onTrigger }: { workflow: Workflow; onTrigger: () => void }) {
    return (
        <div
            className="bg-white p-5 depth-1 border-l-4"
            style={{
                borderLeftColor: workflow.is_active ? "#00B894" : "#636E72",
                clipPath: "polygon(0 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%)"
            }}
        >
            <div className="flex items-start justify-between">
                <div>
                    <h3 className="font-semibold text-[#2C3E50]">{workflow.name}</h3>
                    <p className="text-xs text-[#636E72] mt-1">
                        Trigger: <span className="font-mono">{workflow.trigger_event || workflow.trigger_type}</span>
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {workflow.is_active ? (
                        <span className="flex items-center gap-1 text-xs text-[#00B894]">
                            <CheckCircle size={12} /> Active
                        </span>
                    ) : (
                        <span className="flex items-center gap-1 text-xs text-[#636E72]">
                            <AlertCircle size={12} /> Inactive
                        </span>
                    )}
                </div>
            </div>
            <button
                onClick={onTrigger}
                className="mt-3 flex items-center gap-1 text-xs text-[#00B894] hover:text-[#00a885] transition"
            >
                <Play size={12} /> Test Trigger
            </button>
        </div>
    );
}

// -- Tag Pill --
function TagPill({ tag, onRemove }: { tag: string; onRemove?: () => void }) {
    return (
        <span className="inline-flex items-center gap-1 px-2 py-1 bg-[#00B894]/10 text-[#00B894] text-xs font-semibold">
            <Tag size={10} />
            {tag}
            {onRemove && (
                <button onClick={onRemove} className="ml-1 hover:text-red-500 transition">
                    <X size={10} />
                </button>
            )}
        </span>
    );
}

// -- Pipelines View --
function PipelinesView() {
    const [pipelines, setPipelines] = useState<Pipeline[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch("/api/crm/pipelines")
            .then(res => res.json())
            .then(data => {
                setPipelines(Array.isArray(data) ? data : []);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20">
                <div className="inline-block w-6 h-6 border-2 border-[#00B894] border-t-transparent animate-spin" />
            </div>
        );
    }

    return (
        <div>
            <div className="mb-6 flex items-center justify-between">
                <div>
                    <h2 className="font-serif text-2xl font-bold text-[#2C3E50]">Sales Pipelines</h2>
                    <p className="text-sm text-[#636E72] mt-1">Track deals through your sales process</p>
                </div>
                <button
                    className="px-6 py-2.5 bg-[#00B894] text-white text-sm font-semibold hover:bg-[#00a885] transition flex items-center gap-2"
                    style={{ clipPath: "polygon(0 0, 100% 0, 100% 70%, 90% 100%, 0 100%)" }}
                >
                    <Plus size={16} /> New Pipeline
                </button>
            </div>

            {pipelines.map(pipeline => (
                <div key={pipeline.id} className="mb-8">
                    <div className="flex items-center gap-3 mb-4">
                        <h3 className="font-semibold text-[#2C3E50]">{pipeline.name}</h3>
                        {pipeline.is_default && (
                            <span className="px-2 py-0.5 bg-[#00B894]/10 text-[#00B894] text-[10px] font-bold uppercase">Default</span>
                        )}
                    </div>
                    <div className="flex gap-4 overflow-x-auto pb-4">
                        {pipeline.stages.map(stage => (
                            <PipelineStageCard key={stage.id} stage={stage} deals={Math.floor(Math.random() * 10)} />
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}

// -- Workflows View --
function WorkflowsView() {
    const [workflows, setWorkflows] = useState<Workflow[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch("/api/crm/workflows")
            .then(res => res.json())
            .then(data => {
                setWorkflows(Array.isArray(data) ? data : []);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    const handleTrigger = async (workflowId: string) => {
        // Demo: would open modal to select contact
        alert(`Workflow ${workflowId} trigger would open contact selector`);
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20">
                <div className="inline-block w-6 h-6 border-2 border-[#00B894] border-t-transparent animate-spin" />
            </div>
        );
    }

    return (
        <div>
            <div className="mb-6 flex items-center justify-between">
                <div>
                    <h2 className="font-serif text-2xl font-bold text-[#2C3E50]">Automation Workflows</h2>
                    <p className="text-sm text-[#636E72] mt-1">Automate your customer engagement</p>
                </div>
                <button
                    className="px-6 py-2.5 bg-[#00B894] text-white text-sm font-semibold hover:bg-[#00a885] transition flex items-center gap-2"
                    style={{ clipPath: "polygon(0 0, 100% 0, 100% 70%, 90% 100%, 0 100%)" }}
                >
                    <Plus size={16} /> New Workflow
                </button>
            </div>

            {workflows.length === 0 ? (
                <div className="bg-white p-12 text-center depth-1" style={{ clipPath: "polygon(0 0, 100% 0, 100% calc(100% - 12px), calc(100% - 12px) 100%, 0 100%)" }}>
                    <Zap size={48} className="mx-auto text-[#E8EDEF] mb-4" />
                    <p className="text-[#636E72]">No workflows yet. Create your first automation!</p>
                </div>
            ) : (
                <div className="grid grid-cols-2 gap-4">
                    {workflows.map(workflow => (
                        <WorkflowCard
                            key={workflow.id}
                            workflow={workflow}
                            onTrigger={() => handleTrigger(workflow.id)}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}

// -- Contact Detail Panel with Tags --
function ContactDetailPanel({ contact, timeline, tags, onAddTag, onRemoveTag }: {
    contact: Contact | null;
    timeline: TimelineEvent[];
    tags: ContactTag[];
    onAddTag: (tag: string) => void;
    onRemoveTag: (tag: string) => void;
}) {
    const [newTag, setNewTag] = useState("");

    const handleAddTag = () => {
        if (newTag.trim()) {
            onAddTag(newTag.trim());
            setNewTag("");
        }
    };

    return (
        <div
            className="bg-[#2C3E50] text-white overflow-hidden sticky top-24"
            style={{ clipPath: "polygon(8px 0, 100% 0, 100% 100%, 0 100%, 0 8px)" }}
        >
            <div className="px-6 py-4 border-b border-white/10">
                <p className="text-[10px] text-white/50 uppercase tracking-wider font-bold">Contact Detail</p>
                <h2 className="font-serif text-lg font-bold mt-1">
                    {contact ? `${contact.first_name} ${contact.last_name}` : "Select Contact"}
                </h2>
            </div>

            {contact && (
                <div className="px-6 py-4 border-b border-white/10">
                    <p className="text-[10px] text-white/50 uppercase tracking-wider font-bold mb-2">Tags</p>
                    <div className="flex flex-wrap gap-2 mb-3">
                        {tags.map(t => (
                            <TagPill key={t.id} tag={t.tag} onRemove={() => onRemoveTag(t.tag)} />
                        ))}
                        {tags.length === 0 && <span className="text-xs text-white/40">No tags</span>}
                    </div>
                    <div className="flex gap-2">
                        <input
                            type="text"
                            value={newTag}
                            onChange={(e) => setNewTag(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleAddTag()}
                            placeholder="Add tag..."
                            className="flex-1 px-3 py-1.5 bg-white/10 text-white text-xs placeholder-white/40 border border-white/20 focus:border-[#00B894] focus:outline-none"
                        />
                        <button
                            onClick={handleAddTag}
                            className="px-3 py-1.5 bg-[#00B894] text-white text-xs font-semibold hover:bg-[#00a885] transition"
                        >
                            <Plus size={12} />
                        </button>
                    </div>
                </div>
            )}

            <div className="px-6 py-3 border-b border-white/10">
                <p className="text-[10px] text-white/50 uppercase tracking-wider font-bold">Timeline</p>
            </div>

            <div className="max-h-[400px] overflow-y-auto p-4">
                {!contact ? (
                    <div className="py-12 text-center">
                        <div className="text-4xl mb-3">👆</div>
                        <p className="text-white/50 text-sm">Click a contact to view details</p>
                    </div>
                ) : timeline.length === 0 ? (
                    <p className="text-white/50 text-sm py-8 text-center">No timeline events</p>
                ) : (
                    timeline.map((event, i) => <TimelineItem key={event.id || i} event={event} />)
                )}
            </div>
        </div>
    );
}

// -- Contacts View --
function ContactsView({ contacts, loading, selectedContact, setSelectedContact, timeline, tags, onAddTag, onRemoveTag }: {
    contacts: Contact[];
    loading: boolean;
    selectedContact: Contact | null;
    setSelectedContact: (c: Contact) => void;
    timeline: TimelineEvent[];
    tags: ContactTag[];
    onAddTag: (tag: string) => void;
    onRemoveTag: (tag: string) => void;
}) {
    return (
        <>
            {/* Stats Row */}
            <section className="mb-8">
                <p className="text-[10px] text-[#636E72] uppercase tracking-wider font-semibold mb-4">Overview</p>
                <div className="grid grid-cols-4 gap-6">
                    <StatCard label="Total Contacts" value={contacts.length.toString()} Icon={Users} />
                    <StatCard label="Customers" value={contacts.filter(c => c.lifecycle_stage === 'customer').length.toString()} trend="+12% this month" Icon={Users} />
                    <StatCard label="Avg Score" value={contacts.length ? Math.round(contacts.reduce((a, c) => a + (c.engagement_score || 0), 0) / contacts.length).toString() : "0"} Icon={PieChart} />
                    <StatCard label="Total LTV" value={`$${contacts.reduce((a, c) => a + (c.lifetime_value || 0), 0).toFixed(0)}`} Icon={DollarSign} />
                </div>
            </section>

            {/* Main Grid */}
            <div className="grid grid-cols-3 gap-8">
                {/* Contact List */}
                <section className="col-span-2">
                    <div className="bg-white depth-2 overflow-hidden" style={{ clipPath: "polygon(0 0, 100% 0, 100% calc(100% - 12px), calc(100% - 12px) 100%, 0 100%)" }}>
                        <div className="px-6 py-4 border-b border-[#E8EDEF] bg-[#FAFBFC] flex items-center justify-between">
                            <p className="text-[10px] text-[#636E72] uppercase tracking-wider font-bold">Contact List</p>
                            <div className="flex gap-2">
                                <button className="px-3 py-1.5 text-[10px] font-bold text-[#636E72] bg-[#E8EDEF] hover:bg-[#DFE6E9] transition uppercase tracking-wide">
                                    Filter
                                </button>
                                <button className="px-3 py-1.5 text-[10px] font-bold text-[#636E72] bg-[#E8EDEF] hover:bg-[#DFE6E9] transition uppercase tracking-wide">
                                    Export
                                </button>
                            </div>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead className="bg-[#F8FAFB] text-left border-b border-[#E8EDEF]">
                                    <tr>
                                        <th className="py-3 px-5 text-[10px] font-bold text-[#636E72] uppercase tracking-wider">Contact</th>
                                        <th className="py-3 px-5 text-[10px] font-bold text-[#636E72] uppercase tracking-wider">Stage</th>
                                        <th className="py-3 px-5 text-[10px] font-bold text-[#636E72] uppercase tracking-wider text-right">Score</th>
                                        <th className="py-3 px-5 text-[10px] font-bold text-[#636E72] uppercase tracking-wider text-right">LTV</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {loading ? (
                                        <tr>
                                            <td colSpan={4} className="py-12 text-center text-[#636E72]">
                                                <div className="inline-block w-5 h-5 border-2 border-[#00B894] border-t-transparent animate-spin" />
                                                <p className="mt-2 text-sm">Loading...</p>
                                            </td>
                                        </tr>
                                    ) : contacts.length === 0 ? (
                                        <tr>
                                            <td colSpan={4} className="py-12 text-center text-[#636E72]">No contacts found</td>
                                        </tr>
                                    ) : (
                                        contacts.map((contact) => (
                                            <ContactRow
                                                key={contact.id}
                                                contact={contact}
                                                isSelected={selectedContact?.id === contact.id}
                                                onSelect={() => setSelectedContact(contact)}
                                            />
                                        ))
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </section>

                {/* Detail Panel */}
                <section>
                    <ContactDetailPanel
                        contact={selectedContact}
                        timeline={timeline}
                        tags={tags}
                        onAddTag={onAddTag}
                        onRemoveTag={onRemoveTag}
                    />
                </section>
            </div>
        </>
    );
}

// -- Main Page --
export default function AdminDashboard() {
    const [activeTab, setActiveTab] = useState("contacts");
    const [contacts, setContacts] = useState<Contact[]>([]);
    const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
    const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
    const [tags, setTags] = useState<ContactTag[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch("/api/crm/contacts")
            .then((res) => res.json())
            .then((data) => {
                setContacts(Array.isArray(data) ? data : []);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    useEffect(() => {
        if (!selectedContact) return;

        // Fetch timeline
        fetch(`/api/crm/contacts/${selectedContact.id}`)
            .then((res) => res.json())
            .then((data) => {
                setTimeline(data.timeline || []);
            });

        // Fetch tags
        fetch(`/api/crm/contacts/${selectedContact.id}/tags`)
            .then((res) => res.json())
            .then((data) => {
                setTags(data.tags || []);
            });
    }, [selectedContact]);

    const handleAddTag = async (tag: string) => {
        if (!selectedContact) return;
        const res = await fetch(`/api/crm/contacts/${selectedContact.id}/tags`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tag })
        });
        const data = await res.json();
        if (data.status === 'created') {
            setTags([...tags, { id: data.id, tag: data.tag, created_by: 'api', created_at: new Date().toISOString() }]);
        }
    };

    const handleRemoveTag = async (tag: string) => {
        if (!selectedContact) return;
        await fetch(`/api/crm/contacts/${selectedContact.id}/tags/${tag}`, {
            method: 'DELETE'
        });
        setTags(tags.filter(t => t.tag !== tag));
    };

    const getPageTitle = () => {
        switch (activeTab) {
            case "contacts": return { title: "Contacts", subtitle: "Manage your customer relationships" };
            case "pipelines": return { title: "Pipelines", subtitle: "Track deals through your sales process" };
            case "workflows": return { title: "Workflows", subtitle: "Automate your customer engagement" };
            case "segments": return { title: "Segments", subtitle: "Group contacts by behavior and attributes" };
            case "campaigns": return { title: "Campaigns", subtitle: "Send targeted messages to your audience" };
            case "voice": return { title: "Voice", subtitle: "Manage calls and transcriptions" };
            case "commerce": return { title: "Commerce", subtitle: "Track orders and revenue" };
            default: return { title: "Dashboard", subtitle: "" };
        }
    };

    const pageInfo = getPageTitle();

    return (
        <div className="flex min-h-screen bg-[#F0F4F5]" suppressHydrationWarning>
            {/* Sidebar */}
            <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

            {/* Main Content */}
            <main className="flex-1 ml-64">
                {/* Top Header Bar */}
                <header className="bg-white border-b border-[#E8EDEF] px-8 py-4 sticky top-0 z-10">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="font-serif text-2xl font-bold text-[#2C3E50]">{pageInfo.title}</h1>
                            <p className="text-sm text-[#636E72] mt-0.5">{pageInfo.subtitle}</p>
                        </div>
                        {activeTab === "contacts" && (
                            <button
                                className="px-6 py-2.5 bg-[#00B894] text-white text-sm font-semibold hover:bg-[#00a885] transition"
                                style={{ clipPath: "polygon(0 0, 100% 0, 100% 70%, 90% 100%, 0 100%)" }}
                            >
                                + Add Contact
                            </button>
                        )}
                    </div>
                </header>

                {/* Content Area */}
                <div className="p-8">
                    {activeTab === "contacts" && (
                        <ContactsView
                            contacts={contacts}
                            loading={loading}
                            selectedContact={selectedContact}
                            setSelectedContact={setSelectedContact}
                            timeline={timeline}
                            tags={tags}
                            onAddTag={handleAddTag}
                            onRemoveTag={handleRemoveTag}
                        />
                    )}
                    {activeTab === "pipelines" && <PipelinesView />}
                    {activeTab === "workflows" && <WorkflowsView />}
                    {activeTab === "segments" && (
                        <div className="bg-white p-12 text-center depth-1" style={{ clipPath: "polygon(0 0, 100% 0, 100% calc(100% - 12px), calc(100% - 12px) 100%, 0 100%)" }}>
                            <PieChart size={48} className="mx-auto text-[#E8EDEF] mb-4" />
                            <p className="text-[#636E72]">Segments view coming soon...</p>
                        </div>
                    )}
                    {activeTab === "campaigns" && (
                        <div className="bg-white p-12 text-center depth-1" style={{ clipPath: "polygon(0 0, 100% 0, 100% calc(100% - 12px), calc(100% - 12px) 100%, 0 100%)" }}>
                            <Send size={48} className="mx-auto text-[#E8EDEF] mb-4" />
                            <p className="text-[#636E72]">Campaigns view coming soon...</p>
                        </div>
                    )}
                    {activeTab === "voice" && (
                        <div className="bg-white p-12 text-center depth-1" style={{ clipPath: "polygon(0 0, 100% 0, 100% calc(100% - 12px), calc(100% - 12px) 100%, 0 100%)" }}>
                            <Phone size={48} className="mx-auto text-[#E8EDEF] mb-4" />
                            <p className="text-[#636E72]">Voice view coming soon...</p>
                        </div>
                    )}
                    {activeTab === "commerce" && (
                        <div className="bg-white p-12 text-center depth-1" style={{ clipPath: "polygon(0 0, 100% 0, 100% calc(100% - 12px), calc(100% - 12px) 100%, 0 100%)" }}>
                            <ShoppingBag size={48} className="mx-auto text-[#E8EDEF] mb-4" />
                            <p className="text-[#636E72]">Commerce view coming soon...</p>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
