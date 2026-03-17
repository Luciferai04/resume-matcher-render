'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { apiFetch, apiPost, API_BASE } from '@/lib/api/client';
import { getUserId } from '@/lib/api/auth';
import { 
    Plus, Upload, FileText, CheckCircle2, AlertCircle, 
    Trophy, Users, Search, ChevronRight, BarChart3, 
    ArrowLeft, ExternalLink, RefreshCw, X, Download, PieChart, Trash2
} from 'lucide-react';

/* ─── Types ───────────────────────────────────────────────────────────── */

interface Cohort {
    cohort_id: string;
    name: string;
    created_at: string;
}

interface StudentProgress {
    status: string;
    has_resume: boolean;
    resume_filename: string | null;
    processing_status: string | null;
    ats_score: number | null;
    master_score: number | null;
    tailored_score: number | null;
    ats_breakdown: Record<string, number> | null;
    total_resumes: number;
    tailored_count: number;
    job_count: number;
    resume_uploaded_at: string | null;
    error?: string | null;
}

interface Student {
    user_id: string;
    name: string;
    email?: string;
    roll_number?: string;
    college?: string;
    progress: StudentProgress;
}

interface CohortStats {
    total_students: number;
    resumes_uploaded: number;
    resumes_scored: number;
    resumes_improved: number;
    average_ats_score: number | null;
    status_breakdown: Record<string, number>;
}

interface LeaderboardEntry {
    rank: number;
    user_id: string;
    name: string;
    email: string | null;
    ats_score: number | null;
    master_score: number | null;
    tailored_score: number | null;
    resume_filename: string | null;
    tailored_count: number;
    status: string;
}

/* ─── Swiss Design Tokens ─────────────────────────────────────────────── */

const CANVAS = '#f0f0e8';
const INK = '#000000';
const BLUE = '#1d4ed8';
const PANEL = '#e5e5e0';
const GREEN = '#15803d';
const RED = '#dc2626';
const ORANGE = '#f97316';
const VIOLET = '#7c3aed';
const MUTED = '#6b7280';

const FONT_MONO = "'Space Grotesk', 'Geist Mono', monospace";
const FONT_SANS = "'Geist Sans', 'Geist', sans-serif";
const SHADOW = '4px 4px 0px 0px #000';
const SHADOW_SM = '2px 2px 0px 0px #000';

/* ─── Status Badge ────────────────────────────────────────────────────── */

const STATUS_MAP: Record<string, { label: string; color: string }> = {
    not_started: { label: 'NOT STARTED', color: MUTED },
    processing: { label: 'PROCESSING', color: ORANGE },
    upload_failed: { label: 'FAILED', color: RED },
    uploaded: { label: 'UPLOADED', color: BLUE },
    scored: { label: 'SCORED', color: VIOLET },
    improved: { label: 'IMPROVED', color: GREEN },
};

function StatusBadge({ status }: { status: string }) {
    const cfg = STATUS_MAP[status] || STATUS_MAP.not_started;
    return (
        <span
            style={{
                fontFamily: FONT_MONO,
                fontSize: '10px',
                fontWeight: 700,
                letterSpacing: '0.08em',
                color: cfg.color,
                border: `2px solid ${cfg.color}`,
                padding: '2px 8px',
                textTransform: 'uppercase',
            }}
        >
            {cfg.label}
        </span>
    );
}

/* ─── UI Components ───────────────────────────────────────────────────── */

function StatCard({ label, value, accent }: { label: string; value: string | number; accent: string }) {
    return (
        <div style={{ background: CANVAS, border: `2px solid ${INK}`, borderTop: `6px solid ${accent}`, boxShadow: SHADOW, padding: '16px', minWidth: '160px', flex: 1 }}>
            <div style={{ fontFamily: FONT_MONO, fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', color: MUTED, marginBottom: '8px', letterSpacing: '0.05em' }}>
                {label}
            </div>
            <div style={{ fontFamily: FONT_MONO, fontSize: '32px', fontWeight: 800, color: INK }}>
                {value}
            </div>
        </div>
    );
}

function RankBadge({ rank }: { rank: number }) {
    const bg = rank === 1 ? '#000' : rank === 2 ? PANEL : rank === 3 ? '#e5e5e0' : CANVAS;
    const fg = rank === 1 ? '#fff' : INK;
    return (
        <div
            style={{
                width: '32px',
                height: '32px',
                border: `2px solid ${INK}`,
                background: bg,
                color: fg,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: FONT_MONO,
                fontWeight: 800,
                fontSize: '13px',
                flexShrink: 0,
            }}
        >
            {rank}
        </div>
    );
}

/* ─── Main Page ───────────────────────────────────────────────────────── */

export default function AdminPage() {
    const [cohorts, setCohorts] = useState<Cohort[]>([]);
    const [selectedCohort, setSelectedCohort] = useState<string | null>(null);
    const [students, setStudents] = useState<Student[]>([]);
    const [stats, setStats] = useState<CohortStats | null>(null);
    const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
    const [activeTab, setActiveTab] = useState<'students' | 'leaderboard'>('students');
    const [loading, setLoading] = useState(false);
    const [jobs, setJobs] = useState<any[]>([]);
    const [creating, setCreating] = useState(false);
    const [newCohortName, setNewCohortName] = useState('');
    const [bulkStudentText, setBulkStudentText] = useState('');
    const [addingStudents, setAddingStudents] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [uploadResults, setUploadResults] = useState<any[] | null>(null);
    const [sortKey, setSortKey] = useState<string>('name');
    const [sortAsc, setSortAsc] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [scoringJobId, setScoringJobId] = useState('');
    const [retrying, setRetrying] = useState<Record<string, boolean>>({});
    const [rescoring, setRescoring] = useState(false);
    const [showReport, setShowReport] = useState(false);
    const [reportData, setReportData] = useState<any>(null);
    const [fetchingReport, setFetchingReport] = useState(false);
    const [deleting, setDeleting] = useState<string | null>(null);
    const [deletingUser, setDeletingUser] = useState<string | null>(null);
    const [asTailored, setAsTailored] = useState(false);
    const [driveUrl, setDriveUrl] = useState('');
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => { 
        fetchCohorts(); 
        fetchJobs();
    }, []);

    const fetchCohorts = async () => {
        try {
            const res = await apiFetch('/admin/cohorts');
            const data = await res.json();
            setCohorts(data.cohorts || []);
            if (data.cohorts?.length > 0 && !selectedCohort) {
                setSelectedCohort(data.cohorts[0].cohort_id);
            }
        } catch (err) { console.error('Failed to fetch cohorts:', err); }
    };

    const fetchJobs = async () => {
        try {
            const res = await apiFetch('/jobs');
            const data = await res.json();
            setJobs(data.jobs || []);
        } catch (err) { console.error('Failed to fetch jobs:', err); }
    };

    const fetchCohortData = useCallback(async (cohortId: string, silent = false) => {
        if (!silent) setLoading(true);
        try {
            const [sR, stR, lR] = await Promise.all([
                apiFetch(`/admin/cohorts/${cohortId}/students`),
                apiFetch(`/admin/cohorts/${cohortId}/stats`),
                apiFetch(`/admin/cohorts/${cohortId}/leaderboard`),
            ]);
            const [sD, stD, lD] = await Promise.all([sR.json(), stR.json(), lR.json()]);
            setStudents(sD.students || []);
            setStats(stD);
            setLeaderboard(lD.leaderboard || []);
        } catch (err) { console.error('Failed to fetch cohort data:', err); }
        finally { if (!silent) setLoading(false); }
    }, []);

    useEffect(() => { if (selectedCohort) fetchCohortData(selectedCohort); }, [selectedCohort, fetchCohortData]);

    // Polling for processing students
    useEffect(() => {
        if (!selectedCohort || loading) return;
        const hasProcessing = students.some(s => s.progress.status === 'processing' || s.progress.status === 'pending');
        if (hasProcessing) {
            const timer = setTimeout(() => fetchCohortData(selectedCohort, true), 3000);
            return () => clearTimeout(timer);
        }
    }, [selectedCohort, students, loading, fetchCohortData]);

    const handleCreateCohort = async () => {
        if (!newCohortName.trim()) return;
        setCreating(true);
        try {
            const res = await apiPost('/admin/cohorts', { name: newCohortName.trim() });
            const data = await res.json();
            
            if (!res.ok) {
                alert(`Failed to create cohort: ${data.detail || data.message || 'Unknown error'}`);
                return;
            }

            // Ensure data has the required fields
            if (data && data.cohort_id) {
                setCohorts((prev) => [...prev, data]);
                setSelectedCohort(data.cohort_id);
                setNewCohortName('');
                console.log('Cohort created successfully:', data.cohort_id);
            } else {
                throw new Error('Invalid response from server');
            }
        } catch (err: any) { 
            console.error('Cohort creation error:', err);
            alert(`Error: ${err.message || 'Failed to connect to backend'}`);
        }
        finally { setCreating(false); }
    };

    const handleDeleteCohort = async (cohortId: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm('Are you sure you want to delete this cohort? This will remove all students and their resumes.')) return;
        
        setDeleting(cohortId);
        try {
            const res = await apiFetch(`/admin/cohorts/${cohortId}`, { method: 'DELETE' });
            if (res.ok) {
                setCohorts(prev => prev.filter(c => c.cohort_id !== cohortId));
                if (selectedCohort === cohortId) {
                    setSelectedCohort(null);
                    setStudents([]);
                    setStats(null);
                }
            } else {
                alert('Failed to delete cohort');
            }
        } catch (err) {
            console.error('Delete cohort error:', err);
        } finally {
            setDeleting(null);
        }
    };

    const handleDeleteStudentResume = async (userId: string) => {
        if (!confirm('Are you sure you want to delete all resumes and scores for this student?')) return;
        
        setDeletingUser(userId);
        try {
            const res = await apiFetch(`/admin/students/${userId}/resume`, { method: 'DELETE' });
            if (res.ok) {
                if (selectedCohort) fetchCohortData(selectedCohort, true);
            } else {
                alert('Failed to delete student data');
            }
        } catch (err) {
            console.error('Delete student error:', err);
        } finally {
            setDeletingUser(null);
        }
    };

    const handleAddStudents = async () => {
        if (!selectedCohort || !bulkStudentText.trim()) return;
        setAddingStudents(true);
        try {
            const lines = bulkStudentText.split('\n').map(l => l.trim()).filter(Boolean);
            const entries = lines.map(line => {
                const p = line.split(',').map(s => s.trim());
                return { name: p[0], email: p[1] || undefined, user_id: p[2] || undefined };
            });
            await apiPost(`/admin/cohorts/${selectedCohort}/students`, { students: entries });
            setBulkStudentText('');
            fetchCohortData(selectedCohort);
        } catch (err) { console.error(err); }
        finally { setAddingStudents(false); }
    };

    const handleRetry = async (userId: string) => {
        setRetrying(prev => ({ ...prev, [userId]: true }));
        try {
            const query = scoringJobId.trim() ? `?job_id=${scoringJobId.trim()}` : '';
            await apiPost(`/admin/students/${userId}/retry${query}`, {});
            if (selectedCohort) fetchCohortData(selectedCohort, true);
        } catch (err) {
            console.error('Retry failed:', err);
        } finally {
            setRetrying(prev => ({ ...prev, [userId]: false }));
        }
    };

    const handleRescoreAll = async () => {
        if (!selectedCohort) return;
        
        // No longer preventing rescoring if jobs.length === 0
        // The backend will now provide a general score.

        setRescoring(true);
        try {
            const query = scoringJobId.trim() ? `?job_id=${scoringJobId.trim()}` : '';
            const res = await apiPost(`/admin/cohorts/${selectedCohort}/rescore-all${query}`, {});
            const data = await res.json();
            if (data.status === 'success') {
                alert(`Rescoring complete: ${data.scored} scored, ${data.failed} failed, ${data.skipped} skipped`);
                fetchCohortData(selectedCohort);
            } else {
                alert(data.message || 'Unknown error during rescoring');
            }
        } catch (err: any) {
            console.error('Rescore failed:', err);
            alert(`Error: ${err.message || 'Failed to rescore'}`);
        } finally {
            setRescoring(false);
        }
    };

    const fetchReport = async () => {
        if (!selectedCohort) return;
        setFetchingReport(true);
        try {
            const res = await apiFetch(`/admin/cohorts/${selectedCohort}/report`);
            const data = await res.json();
            setReportData(data);
            setShowReport(true);
        } catch (err) {
            console.error('Failed to fetch report:', err);
            alert('Failed to generate report');
        } finally {
            setFetchingReport(false);
        }
    };

    const handlePrint = () => {
        window.print();
    };

    const handleBulkUpload = async (files: FileList | null, urlOverride?: string) => {
        if (!selectedCohort) return;
        if ((!files || files.length === 0) && !urlOverride) return;
        
        setUploading(true); setUploadResults(null);
        try {
            const fd = new FormData();
            if (files) {
                for (let i = 0; i < files.length; i++) fd.append('files', files[i]);
            }
            
            const endpoint = `/admin/cohorts/${selectedCohort}/bulk-upload-resumes`;
            const params = new URLSearchParams();
            if (scoringJobId.trim()) params.append('job_id', scoringJobId.trim());
            if (asTailored) params.append('as_tailored', 'true');
            if (urlOverride) params.append('drive_url', urlOverride);
            
            const queryString = params.toString();
            
            const res = await apiFetch(`${endpoint}${queryString ? `?${queryString}` : ''}`, {
                method: 'POST',
                body: fd,
            });
            
            if (!res.ok) {
                const errorData = await res.json().catch(() => ({ detail: 'Upload failed with server error' }));
                setUploadResults([{ 
                    filename: 'Upload Process', 
                    status: 'error', 
                    error: errorData.detail || errorData.message || `Server error (${res.status})` 
                }]);
                return;
            }
            
            const data = await res.json();
            setUploadResults(data.results || []);
            fetchCohortData(selectedCohort);
        } catch (err: any) { 
            console.error('Upload error:', err);
            setUploadResults([{ 
                filename: 'Network/Client', 
                status: 'error', 
                error: err.message || 'Failed to connect to server' 
            }]);
        }
        finally { setUploading(false); }
    };

    const handleSort = (key: string) => {
        if (sortKey === key) setSortAsc(!sortAsc);
        else { setSortKey(key); setSortAsc(true); }
    };

    const sortedStudents = [...students]
        .filter(s => !searchTerm ||
            s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            s.user_id.toLowerCase().includes(searchTerm.toLowerCase()))
        .sort((a, b) => {
            let aV: any, bV: any;
            switch (sortKey) {
                case 'name': aV = a.name.toLowerCase(); bV = b.name.toLowerCase(); break;
                case 'status': aV = a.progress.status; bV = b.progress.status; break;
                case 'ats_score': aV = a.progress.ats_score ?? -1; bV = b.progress.ats_score ?? -1; break;
                case 'tailored': aV = a.progress.tailored_count; bV = b.progress.tailored_count; break;
                default: aV = a.name; bV = b.name;
            }
            return aV < bV ? (sortAsc ? -1 : 1) : aV > bV ? (sortAsc ? 1 : -1) : 0;
        });

    const thStyle: React.CSSProperties = {
        padding: '10px 16px',
        textAlign: 'left',
        fontFamily: FONT_MONO,
        fontSize: '10px',
        fontWeight: 700,
        color: MUTED,
        textTransform: 'uppercase',
        letterSpacing: '0.1em',
        borderBottom: `2px solid ${INK}`,
        cursor: 'pointer',
        userSelect: 'none',
        whiteSpace: 'nowrap',
        background: PANEL,
    };

    const SortTh = ({ label, k }: { label: string; k: string }) => (
        <th onClick={() => handleSort(k)} style={thStyle}>
            {label} {sortKey === k ? (sortAsc ? '↑' : '↓') : ''}
        </th>
    );

    const inputStyle: React.CSSProperties = {
        fontFamily: FONT_MONO,
        fontSize: '13px',
        color: INK,
        background: CANVAS,
        border: `2px solid ${INK}`,
        padding: '8px 12px',
        outline: 'none',
    };

    const btnPrimary: React.CSSProperties = {
        fontFamily: FONT_MONO,
        fontSize: '12px',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        background: BLUE,
        color: '#fff',
        border: `2px solid ${INK}`,
        boxShadow: SHADOW_SM,
        padding: '8px 24px',
        cursor: 'pointer',
    };

    return (
        <>
            <div className="no-print" style={{ padding: '40px', maxWidth: '1200px', margin: '0 auto' }}>
                {/* Header */}
            <header style={{ marginBottom: '48px', borderBottom: `4px solid ${INK}`, paddingBottom: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '8px' }}>
                    <h1 style={{ fontFamily: FONT_MONO, fontSize: '48px', fontWeight: 900, textTransform: 'uppercase', color: INK, margin: 0, letterSpacing: '-0.02em' }}>
                        Admin Terminal
                    </h1>
                    <div style={{ fontFamily: FONT_MONO, fontSize: '11px', color: MUTED, textTransform: 'uppercase', background: PANEL, padding: '4px 12px', border: `2px solid ${INK}` }}>
                        V{API_BASE.includes('localhost') ? 'DEV' : 'PROD'} // COHORT MGMT
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
                    <div style={{ fontFamily: FONT_MONO, fontSize: '14px', textTransform: 'uppercase', color: BLUE, fontWeight: 700 }}>
                        System Status: Operational
                    </div>
                    {students.some(s => s.progress.status === 'processing') && (
                        <div style={{ fontFamily: FONT_MONO, fontSize: '12px', color: ORANGE, display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <div style={{ width: '8px', height: '8px', background: ORANGE, borderRadius: '50%', animation: 'pulse 1s infinite' }} />
                            Auto-refreshing resumes...
                        </div>
                    )}
                </div>
            </header>

            {/* Main Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '40px' }}>
                {/* Cohort Sidebar */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
                    <div style={{ background: CANVAS, border: `2px solid ${INK}`, boxShadow: SHADOW, padding: '24px' }}>
                        <h2 style={{ fontFamily: FONT_MONO, fontSize: '14px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <Users size={16} /> Cohorts
                        </h2>
                        
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '24px' }}>
                            {cohorts.map(c => (
                                <div key={c.cohort_id} style={{ position: 'relative', display: 'flex', gap: '4px' }}>
                                    <button
                                        onClick={() => setSelectedCohort(c.cohort_id)}
                                        style={{
                                            fontFamily: FONT_MONO,
                                            fontSize: '13px',
                                            textAlign: 'left',
                                            padding: '12px 16px',
                                            background: selectedCohort === c.cohort_id ? INK : 'transparent',
                                            color: selectedCohort === c.cohort_id ? CANVAS : INK,
                                            border: `2px solid ${INK}`,
                                            cursor: 'pointer',
                                            textTransform: 'uppercase',
                                            fontWeight: 700,
                                            transition: 'all 0.1s ease',
                                            flex: 1,
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            alignItems: 'center'
                                        }}
                                    >
                                        {c.name}
                                    </button>
                                    <button
                                        onClick={(e) => handleDeleteCohort(c.cohort_id, e)}
                                        disabled={deleting === c.cohort_id}
                                        style={{
                                            padding: '8px',
                                            background: CANVAS,
                                            border: `2px solid ${INK}`,
                                            color: RED,
                                            cursor: 'pointer',
                                            opacity: deleting === c.cohort_id ? 0.4 : 1,
                                        }}
                                        title="Delete Cohort"
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                </div>
                            ))}
                        </div>

                        <div style={{ borderTop: `2px solid ${INK}`, paddingTop: '20px' }}>
                            <input
                                type="text"
                                value={newCohortName}
                                onChange={e => setNewCohortName(e.target.value)}
                                placeholder="New Cohort Name..."
                                style={{ ...inputStyle, width: '100%', boxSizing: 'border-box', marginBottom: '8px' }}
                            />
                            <button
                                onClick={handleCreateCohort}
                                disabled={creating || !newCohortName.trim()}
                                style={{ ...btnPrimary, width: '100%', opacity: creating || !newCohortName.trim() ? 0.4 : 1 }}
                            >
                                {creating ? 'Creating...' : 'Create Cohort'}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Content Area */}
                <div style={{ minWidth: 0 }}>
                    <div style={{ marginBottom: '32px', display: 'flex', gap: '12px', alignItems: 'center' }}>
                        <div style={{ fontFamily: FONT_MONO, fontSize: '12px', color: MUTED, textTransform: 'uppercase', paddingRight: '12px', borderRight: `2px solid ${PANEL}` }}>
                            Job Focus:
                        </div>
                        <select
                            value={scoringJobId}
                            onChange={e => setScoringJobId(e.target.value)}
                            style={{ ...inputStyle, padding: '4px 12px', fontSize: '12px', textTransform: 'uppercase' }}
                        >
                            <option value="">No Active Job (General Score)</option>
                            {jobs.length > 0 ? (
                                <optgroup label="Select Job">
                                    {jobs.map(j => (
                                        <option key={j.job_id} value={j.job_id}>
                                            {j.content.substring(0, 50)}...
                                        </option>
                                    ))}
                                </optgroup>
                            ) : (
                                <option disabled>No jobs found in database</option>
                            )}
                        </select>
                    </div>

                    {!selectedCohort ? (
                        <div style={{ textAlign: 'center', color: MUTED, fontFamily: FONT_MONO, fontSize: '14px', padding: '80px 0', textTransform: 'uppercase' }}>
                            Create or select a cohort to begin
                        </div>
                    ) : loading ? (
                        <div style={{ textAlign: 'center', color: MUTED, fontFamily: FONT_MONO, fontSize: '14px', padding: '80px 0', textTransform: 'uppercase' }}>
                            Loading...
                        </div>
                    ) : (
                        <>
                            {/* Stats */}
                            {stats && (
                                <div style={{ display: 'flex', gap: '12px', marginBottom: '32px', flexWrap: 'wrap' }}>
                                    <StatCard label="Total Students" value={stats.total_students} accent={INK} />
                                    <StatCard label="Resumes Uploaded" value={stats.resumes_uploaded} accent={BLUE} />
                                    <StatCard label="ATS Scored" value={stats.resumes_scored} accent={VIOLET} />
                                    <StatCard label="Avg ATS Score" value={stats.average_ats_score ?? '—'} accent={GREEN} />
                                    <StatCard label="Improved" value={stats.resumes_improved} accent={ORANGE} />
                                </div>
                            )}

                            {/* Rescore Button */}
                            {stats && stats.resumes_uploaded > 0 && (
                                <div style={{ marginBottom: '16px', display: 'flex', gap: '12px', alignItems: 'center' }}>
                                    <button
                                        onClick={handleRescoreAll}
                                        disabled={rescoring}
                                        style={{
                                            ...btnPrimary,
                                            background: VIOLET,
                                            opacity: rescoring ? 0.4 : 1,
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '8px',
                                        }}
                                    >
                                        <BarChart3 size={14} />
                                        {rescoring ? 'Scoring...' : 'Rescore All Unscored'}
                                    </button>
                                    <button
                                        onClick={fetchReport}
                                        disabled={fetchingReport}
                                        style={{
                                            ...btnPrimary,
                                            background: GREEN,
                                            opacity: fetchingReport ? 0.4 : 1,
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '8px',
                                        }}
                                    >
                                        <PieChart size={14} />
                                        {fetchingReport ? 'Loading...' : 'View Report'}
                                    </button>
                                    {stats.resumes_scored < stats.resumes_uploaded && (
                                        <span style={{ fontFamily: FONT_MONO, fontSize: '11px', color: ORANGE }}>
                                            {stats.resumes_uploaded - stats.resumes_scored} resumes need scoring
                                        </span>
                                    )}
                                </div>
                            )}

                            {/* Action Row */}
                            <div style={{ display: 'flex', gap: '12px', marginBottom: '32px', flexWrap: 'wrap' }}>
                                {/* Add Students */}
                                <div style={{ background: CANVAS, border: `2px solid ${INK}`, boxShadow: SHADOW, padding: '24px', flex: '1 1 400px' }}>
                                    <h3 style={{ fontFamily: FONT_MONO, fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '12px' }}>
                                        Add Students
                                    </h3>
                                    <textarea
                                        value={bulkStudentText}
                                        onChange={e => setBulkStudentText(e.target.value)}
                                        placeholder={"One per line: Name, Email, StudentID\ne.g.\nJohn Doe, john@college.edu, student_001"}
                                        rows={4}
                                        style={{ ...inputStyle, width: '100%', resize: 'vertical', boxSizing: 'border-box' }}
                                    />
                                    <button
                                        onClick={handleAddStudents}
                                        disabled={addingStudents || !bulkStudentText.trim()}
                                        style={{ ...btnPrimary, marginTop: '8px', background: GREEN, opacity: addingStudents || !bulkStudentText.trim() ? 0.4 : 1 }}
                                    >
                                        {addingStudents ? 'Adding...' : 'Add Students'}
                                    </button>
                                </div>

                                {/* Bulk Upload */}
                                <div style={{ background: CANVAS, border: `2px solid ${INK}`, boxShadow: SHADOW, padding: '24px', flex: '1 1 400px' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                                        <h3 style={{ fontFamily: FONT_MONO, fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', margin: 0 }}>
                                            Bulk Upload
                                        </h3>
                                        <div 
                                            onClick={() => setAsTailored(!asTailored)}
                                            style={{ 
                                                display: 'flex', 
                                                alignItems: 'center', 
                                                gap: '6px', 
                                                cursor: 'pointer',
                                                padding: '4px 8px',
                                                background: asTailored ? BLUE : 'transparent',
                                                border: `1px solid ${INK}`,
                                                color: asTailored ? CANVAS : INK,
                                                fontFamily: FONT_MONO,
                                                fontSize: '10px',
                                                fontWeight: 700,
                                                textTransform: 'uppercase'
                                            }}
                                        >
                                            <CheckCircle2 size={10} /> {asTailored ? 'Mode: Tailored' : 'Mode: Master'}
                                        </div>
                                    </div>
                                    <div
                                        onClick={() => !uploading && fileInputRef.current?.click()}
                                        onDragOver={e => e.preventDefault()}
                                        onDrop={e => { e.preventDefault(); if (e.dataTransfer.files.length > 0) handleBulkUpload(e.dataTransfer.files); }}
                                        style={{
                                            border: `2px dashed ${INK}`,
                                            padding: '32px 20px',
                                            textAlign: 'center',
                                            cursor: uploading ? 'wait' : 'pointer',
                                            background: PANEL,
                                        }}
                                    >
                                        <input ref={fileInputRef} type="file" multiple accept=".pdf,.docx,.doc,.csv" style={{ display: 'none' }}
                                            onChange={e => e.target.files && handleBulkUpload(e.target.files)} />
                                        <div style={{ fontFamily: FONT_MONO, fontSize: '11px', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.05em', color: INK }}>
                                            {uploading ? 'Uploading...' : 'Drop Resumes or responses.csv'}
                                        </div>
                                    </div>

                                    {/* Drive Link Input */}
                                    <div style={{ marginTop: '16px', borderTop: `1px solid ${PANEL}`, paddingTop: '16px' }}>
                                        <div style={{ display: 'flex', gap: '8px' }}>
                                            <input
                                                type="text"
                                                value={driveUrl}
                                                onChange={e => setDriveUrl(e.target.value)}
                                                placeholder="Paste Google Drive link..."
                                                style={{ ...inputStyle, flex: 1, fontSize: '12px' }}
                                            />
                                            <button
                                                onClick={() => {
                                                    if (driveUrl.trim()) {
                                                        handleBulkUpload(null, driveUrl.trim());
                                                        setDriveUrl('');
                                                    }
                                                }}
                                                disabled={uploading || !driveUrl.trim()}
                                                style={{ ...btnPrimary, padding: '8px 16px', opacity: uploading || !driveUrl.trim() ? 0.4 : 1 }}
                                            >
                                                {uploading ? '...' : 'Process'}
                                            </button>
                                        </div>
                                        <div style={{ fontFamily: FONT_MONO, fontSize: '9px', color: MUTED, marginTop: '4px', textTransform: 'uppercase' }}>
                                            Supports direct folders or individual PDF links
                                        </div>
                                    </div>

                                    {uploadResults && (
                                        <div style={{ marginTop: '10px', fontFamily: FONT_MONO, fontSize: '11px' }}>
                                            {uploadResults.slice(0, 3).map((r, i) => (
                                                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', color: r.status === 'uploaded' ? GREEN : RED }}>
                                                    <span>{r.filename}</span>
                                                    <span>{r.status === 'uploaded' ? '✓' : '✗'}</span>
                                                </div>
                                            ))}
                                            {uploadResults.length > 3 && <div style={{ color: MUTED }}>...and {uploadResults.length - 3} more</div>}
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Tabs */}
                            <div style={{ display: 'flex', border: `2px solid ${INK}`, background: PANEL, marginBottom: '-2px' }}>
                                {['students', 'leaderboard'].map(tab => (
                                    <button
                                        key={tab}
                                        onClick={() => setActiveTab(tab as any)}
                                        style={{
                                            padding: '12px 24px',
                                            fontFamily: FONT_MONO,
                                            fontSize: '12px',
                                            fontWeight: 800,
                                            textTransform: 'uppercase',
                                            background: activeTab === tab ? CANVAS : 'transparent',
                                            color: activeTab === tab ? INK : MUTED,
                                            border: 'none',
                                            borderRight: `2px solid ${INK}`,
                                            cursor: 'pointer',
                                            outline: 'none',
                                        }}
                                    >
                                        {tab}
                                    </button>
                                ))}
                                {activeTab === 'students' && (
                                    <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', padding: '0 4px' }}>
                                        <input
                                            type="text" value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
                                            placeholder="Search..."
                                            style={{ ...inputStyle, fontSize: '11px', padding: '4px 10px', width: '180px', borderBottom: 'none' }}
                                        />
                                    </div>
                                )}
                            </div>

                            {/* Students Table */}
                            {activeTab === 'students' && (
                                <div style={{ border: `2px solid ${INK}`, borderTop: 'none', background: CANVAS }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                        <thead>
                                            <tr>
                                                <SortTh label="Name" k="name" />
                                                <th style={thStyle}>Roll & College</th>
                                                <SortTh label="Status" k="status" />
                                                <SortTh label="ATS Score" k="ats_score" />
                                                <SortTh label="Tailored" k="tailored" />
                                                <th style={thStyle}>Resume</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {sortedStudents.length === 0 ? (
                                                <tr><td colSpan={6} style={{ padding: '40px', textAlign: 'center', fontFamily: FONT_MONO, fontSize: '12px', color: MUTED, textTransform: 'uppercase' }}>
                                                    No students yet
                                                </td></tr>
                                            ) : sortedStudents.map(s => (
                                                <tr key={s.user_id} style={{ borderBottom: `1px solid ${PANEL}` }}>
                                                    <td style={{ padding: '12px 16px' }}>
                                                        <div style={{ fontFamily: FONT_SANS, fontWeight: 700, color: INK, fontSize: '14px' }}>{s.name}</div>
                                                        {s.email && <div style={{ fontFamily: FONT_MONO, color: MUTED, fontSize: '10px', marginTop: '2px' }}>{s.email}</div>}
                                                    </td>
                                                    <td style={{ padding: '12px 16px', fontFamily: FONT_MONO, color: MUTED, fontSize: '10px' }}>
                                                        <div>{s.roll_number || 'No ID'}</div>
                                                        <div style={{ color: INK, fontWeight: 700 }}>{s.college || '—'}</div>
                                                    </td>
                                                    <td style={{ padding: '12px 16px' }}>
                                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                            <StatusBadge status={s.progress.status} />
                                                            {(s.progress.status === 'upload_failed' || s.progress.status === 'processing') && (
                                                                <button
                                                                    onClick={() => handleRetry(s.user_id)}
                                                                    disabled={retrying[s.user_id]}
                                                                    title="Force retry processing"
                                                                    style={{
                                                                        padding: '2px',
                                                                        background: PANEL,
                                                                        border: `1px solid ${INK}`,
                                                                        cursor: 'pointer',
                                                                        display: 'flex',
                                                                        alignItems: 'center',
                                                                        opacity: retrying[s.user_id] ? 0.3 : 1
                                                                    }}
                                                                >
                                                                    <RefreshCw size={12} style={{ animation: retrying[s.user_id] ? 'spin 1.5s linear infinite' : 'none' }} />
                                                                </button>
                                                            )}
                                                            {s.progress.has_resume && (
                                                                <button
                                                                    onClick={() => handleDeleteStudentResume(s.user_id)}
                                                                    disabled={deletingUser === s.user_id}
                                                                    title="Delete student resumes & scores"
                                                                    style={{
                                                                        padding: '2px',
                                                                        background: PANEL,
                                                                        border: `1px solid ${INK}`,
                                                                        cursor: 'pointer',
                                                                        display: 'flex',
                                                                        alignItems: 'center',
                                                                        color: RED,
                                                                        opacity: deletingUser === s.user_id ? 0.3 : 1
                                                                    }}
                                                                >
                                                                    <Trash2 size={12} />
                                                                </button>
                                                            )}
                                                        </div>
                                                        {s.progress.error && (
                                                            <div style={{ fontFamily: FONT_SANS, fontSize: '9px', color: RED, marginTop: '4px', maxWidth: '150px' }}>
                                                                {s.progress.error}
                                                            </div>
                                                        )}
                                                    </td>
                                                    <td style={{ padding: '12px 16px' }}>
                                                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                                                            {s.progress.master_score !== null ? (
                                                                <span style={{ 
                                                                    fontFamily: FONT_MONO, 
                                                                    fontWeight: 800, 
                                                                    fontSize: s.progress.tailored_score ? '12px' : '20px', 
                                                                    color: s.progress.master_score >= 75 ? GREEN : s.progress.master_score >= 50 ? ORANGE : RED,
                                                                    opacity: s.progress.tailored_score ? 0.6 : 1
                                                                }}>
                                                                    {s.progress.tailored_score ? `M: ${s.progress.master_score}` : s.progress.master_score}
                                                                </span>
                                                            ) : !s.progress.tailored_score && <span style={{ color: PANEL }}>—</span>}
                                                            
                                                            {s.progress.tailored_score !== null && (
                                                                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                                                    {s.progress.master_score !== null && <div style={{ width: '2px', height: '10px', background: MUTED, opacity: 0.3 }} />}
                                                                    <span style={{ 
                                                                        fontFamily: FONT_MONO, 
                                                                        fontWeight: 900, 
                                                                        fontSize: '20px', 
                                                                        color: s.progress.tailored_score >= 75 ? GREEN : s.progress.tailored_score >= 50 ? ORANGE : RED 
                                                                    }}>
                                                                        {s.progress.tailored_score}
                                                                        <span style={{ fontSize: '10px', marginLeft: '2px', verticalAlign: 'top', opacity: 0.8 }}>★</span>
                                                                    </span>
                                                                </div>
                                                            )}
                                                        </div>
                                                    </td>
                                                    <td style={{ padding: '12px 16px', fontFamily: FONT_MONO, fontSize: '13px', color: s.progress.tailored_count > 0 ? GREEN : MUTED, fontWeight: 700 }}>
                                                        {s.progress.tailored_count}
                                                    </td>
                                                    <td style={{ padding: '12px 16px', fontFamily: FONT_MONO, fontSize: '10px', color: MUTED, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '120px' }}>
                                                        {s.progress.resume_filename || '—'}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}

                            {/* Leaderboard */}
                            {activeTab === 'leaderboard' && (
                                <div style={{ border: `2px solid ${INK}`, borderTop: 'none', background: CANVAS }}>
                                    {leaderboard.length === 0 ? (
                                        <div style={{ padding: '60px', textAlign: 'center', fontFamily: FONT_MONO, fontSize: '12px', color: MUTED, textTransform: 'uppercase' }}>
                                            No scored students yet
                                        </div>
                                    ) : (
                                        <div>
                                            {leaderboard.map((entry, i) => (
                                                <div
                                                    key={entry.user_id}
                                                    style={{
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        gap: '16px',
                                                        padding: '14px 24px',
                                                        borderBottom: i < leaderboard.length - 1 ? `1px solid ${PANEL}` : 'none',
                                                        background: entry.rank <= 3 ? (entry.rank === 1 ? '#fefce8' : entry.rank === 2 ? PANEL : '#fff7ed') : CANVAS,
                                                    }}
                                                >
                                                    <RankBadge rank={entry.rank} />
                                                    <div style={{ flex: 1 }}>
                                                        <div style={{ fontFamily: FONT_SANS, fontWeight: 700, color: INK, fontSize: '14px' }}>{entry.name}</div>
                                                    </div>
                                                    <StatusBadge status={entry.status} />
                                                    <div style={{ textAlign: 'right', minWidth: '80px' }}>
                                                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                                                            {entry.master_score !== null && entry.tailored_score !== null ? (
                                                                <>
                                                                    <span style={{ fontFamily: FONT_MONO, fontWeight: 700, fontSize: '10px', color: MUTED, opacity: 0.7 }}>
                                                                        {entry.master_score} →
                                                                    </span>
                                                                    <span style={{ fontFamily: FONT_MONO, fontWeight: 900, fontSize: '24px', color: entry.tailored_score >= 75 ? GREEN : entry.tailored_score >= 50 ? ORANGE : RED }}>
                                                                        {entry.tailored_score}
                                                                        <span style={{ fontSize: '12px', marginLeft: '2px', verticalAlign: 'top' }}>★</span>
                                                                    </span>
                                                                </>
                                                            ) : entry.ats_score !== null ? (
                                                                <span style={{ fontFamily: FONT_MONO, fontWeight: 800, fontSize: '24px', color: entry.ats_score >= 75 ? GREEN : entry.ats_score >= 50 ? ORANGE : RED }}>
                                                                    {entry.ats_score}
                                                                </span>
                                                            ) : (
                                                                <span style={{ color: PANEL, fontFamily: FONT_MONO }}>—</span>
                                                            )}
                                                        </div>
                                                    </div>
                                                    {entry.tailored_count > 0 && (
                                                        <div style={{ fontFamily: FONT_MONO, fontSize: '10px', color: MUTED, textTransform: 'uppercase', minWidth: '70px', textAlign: 'right' }}>
                                                            {entry.tailored_count} tailored
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>
            </div> {/* End no-print (485) */}
            
            {/* Executive Report Modal */}
            {showReport && reportData && (
                <div style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: 'rgba(0,0,0,0.95)',
                    zIndex: 1000,
                    display: 'flex',
                    flexDirection: 'column',
                    padding: '24px',
                    overflowY: 'auto',
                }} className="modal-container">
                    
                    {/* Floating Controls (Hidden in Print) */}
                    <div style={{ 
                        position: 'sticky', 
                        top: '0', 
                        alignSelf: 'center',
                        zIndex: 1001,
                        display: 'flex', 
                        gap: '8px',
                        marginBottom: '20px',
                        background: INK,
                        padding: '12px 24px',
                        border: `2px solid ${INK}`,
                        boxShadow: '8px 8px 0px rgba(0,0,0,0.3)'
                    }} className="no-print">
                        <button onClick={handlePrint} style={{ ...btnPrimary, background: CANVAS, color: INK, display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
                            <Download size={14} /> DOWNLOAD OFFICIAL PDF
                        </button>
                        <button onClick={() => setShowReport(false)} style={{ ...btnPrimary, background: RED, color: CANVAS, padding: '8px', border: 'none' }}>
                            <X size={18} />
                        </button>
                    </div>

                    <div style={{
                        background: CANVAS,
                        border: `2px solid ${INK}`,
                        width: '100%',
                        maxWidth: '960px',
                        margin: '0 auto 60px auto',
                        minHeight: '1414px', // A4 Ratio approximation
                        padding: '80px',
                        position: 'relative',
                        boxShadow: '30px 30px 0px rgba(0,0,0,0.4)',
                        color: INK
                    }} className="report-paper">
                        
                        {/* Watermark / Context */}
                        <div style={{ position: 'absolute', top: '24px', left: '24px', fontFamily: FONT_MONO, fontSize: '9px', opacity: 0.3, textTransform: 'uppercase', letterSpacing: '0.2em' }}>
                            OFFICIAL AUDIT // RESUME MATCHER // {new Date().getFullYear()}
                        </div>

                        {/* Report Content */}
                        <div id="executive-report">
                            <div style={{ borderBottom: `12px solid ${INK}`, paddingBottom: '40px', marginBottom: '60px' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                    <div style={{ flex: 1 }}>
                                        <div style={{ fontFamily: FONT_MONO, fontSize: '14px', fontWeight: 800, color: BLUE, textTransform: 'uppercase', marginBottom: '12px', letterSpacing: '0.1em' }}>
                                            // {reportData.cohort?.name} Report
                                        </div>
                                        <h1 style={{ fontFamily: FONT_MONO, fontSize: '72px', fontWeight: 900, textTransform: 'uppercase', margin: 0, lineHeight: 0.85, letterSpacing: '-0.02em' }}>
                                            TALENT<br/>AUDIT
                                        </h1>
                                    </div>
                                    <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                        <div style={{ fontFamily: FONT_MONO, fontSize: '48px', fontWeight: 900, lineHeight: 1 }}>{reportData.summary.engagement_rate}%</div>
                                        <div style={{ fontFamily: FONT_MONO, fontSize: '10px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Engagement Rate</div>
                                    </div>
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '48px', alignItems: 'flex-end' }}>
                                    <div style={{ fontFamily: FONT_MONO, fontSize: '10px', color: MUTED, textTransform: 'uppercase' }}>
                                        ID: {reportData.cohort?.cohort_id}<br/>
                                        TIMESTAMP: {new Date(reportData.generated_at).toLocaleString()}
                                    </div>
                                    <div style={{ display: 'flex', gap: '32px' }}>
                                        <div style={{ textAlign: 'right' }}>
                                            <div style={{ fontFamily: FONT_MONO, fontSize: '12px', fontWeight: 900 }}>{reportData.summary.total_students}</div>
                                            <div style={{ fontFamily: FONT_MONO, fontSize: '8px', color: MUTED, textTransform: 'uppercase' }}>Total Cohort</div>
                                        </div>
                                        <div style={{ textAlign: 'right' }}>
                                            <div style={{ fontFamily: FONT_MONO, fontSize: '12px', fontWeight: 900 }}>{reportData.summary.completion_rate}%</div>
                                            <div style={{ fontFamily: FONT_MONO, fontSize: '8px', color: MUTED, textTransform: 'uppercase' }}>Success Rate</div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Section 01: Funnel */}
                            <div style={{ marginBottom: '80px' }}>
                                <h2 style={{ fontFamily: FONT_MONO, fontSize: '24px', fontWeight: 900, textTransform: 'uppercase', borderBottom: `4px solid ${INK}`, paddingBottom: '12px', marginBottom: '32px' }}>
                                    01. Talent Pipeline Funnel
                                </h2>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                    {reportData.funnel.map((f: any, i: number) => {
                                        const colors = [INK, BLUE, VIOLET, GREEN];
                                        return (
                                            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
                                                <div style={{ width: '180px', fontFamily: FONT_MONO, fontSize: '13px', fontWeight: 800, textTransform: 'uppercase' }}>
                                                    {f.stage}
                                                </div>
                                                <div style={{ flex: 1, height: '40px', background: PANEL, border: `2px solid ${INK}`, position: 'relative' }}>
                                                    <div style={{ 
                                                        height: '100%', 
                                                        width: `${f.pct}%`, 
                                                        background: colors[i] || INK,
                                                        transition: 'width 1.5s cubic-bezier(0.16, 1, 0.3, 1)'
                                                    }} />
                                                    <div style={{ 
                                                        position: 'absolute', 
                                                        right: '16px', 
                                                        top: '50%', 
                                                        transform: 'translateY(-50%)', 
                                                        fontFamily: FONT_MONO, 
                                                        fontWeight: 900, 
                                                        fontSize: '14px',
                                                        color: f.pct > 80 ? CANVAS : INK,
                                                        mixBlendMode: 'difference'
                                                    }}>
                                                        {f.count} ({f.pct}%)
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* Section 02: Benchmarks */}
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '60px', marginBottom: '80px' }}>
                                <div>
                                    <h2 style={{ fontFamily: FONT_MONO, fontSize: '20px', fontWeight: 900, textTransform: 'uppercase', borderBottom: `4px solid ${INK}`, paddingBottom: '12px', marginBottom: '32px' }}>
                                        02. ATS Evolution
                                    </h2>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                                        <div style={{ borderLeft: `8px solid ${BLUE}`, paddingLeft: '20px' }}>
                                            <div style={{ fontFamily: FONT_MONO, fontSize: '11px', color: MUTED, marginBottom: '8px' }}>AVERAGE INITIAL SCORE</div>
                                            <div style={{ fontFamily: FONT_MONO, fontSize: '42px', fontWeight: 900, lineHeight: 1 }}>{reportData.score_growth.average_initial_score || '—'}</div>
                                        </div>
                                        <div style={{ borderLeft: `8px solid ${GREEN}`, paddingLeft: '20px' }}>
                                            <div style={{ fontFamily: FONT_MONO, fontSize: '11px', color: MUTED, marginBottom: '8px' }}>AVERAGE OPTIMIZED SCORE</div>
                                            <div style={{ fontFamily: FONT_MONO, fontSize: '42px', fontWeight: 900, lineHeight: 1 }}>{reportData.score_growth.average_improved_score || '—'}</div>
                                        </div>
                                    </div>
                                </div>
                                <div>
                                    <h2 style={{ fontFamily: FONT_MONO, fontSize: '20px', fontWeight: 900, textTransform: 'uppercase', borderBottom: `4px solid ${INK}`, paddingBottom: '12px', marginBottom: '32px' }}>
                                        03. Skill Coverage
                                    </h2>
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
                                        {reportData.skill_gaps.map((gap: any, i: number) => (
                                            <div key={i} style={{ padding: '12px', border: `2px solid ${INK}`, background: i < 2 ? '#fee2e2' : CANVAS }}>
                                                <div style={{ fontFamily: FONT_MONO, fontWeight: 900, fontSize: '12px', textTransform: 'uppercase' }}>{gap.skill}</div>
                                                <div style={{ fontFamily: FONT_MONO, fontSize: '10px', color: RED, fontWeight: 800, marginTop: '4px' }}>GAP: {gap.students_affected} STUDENTS</div>
                                            </div>
                                        ))}
                                        {reportData.skill_gaps.length === 0 && <div style={{ fontFamily: FONT_MONO, fontSize: '12px', color: MUTED }}>NO SIGNIFICANT GAPS IDENTIFIED</div>}
                                    </div>
                                </div>
                            </div>

                            {/* Section 04: TOP PERFORMERS */}
                            <div style={{ marginBottom: '80px', pageBreakBefore: 'always' }}>
                                <h2 style={{ fontFamily: FONT_MONO, fontSize: '24px', fontWeight: 900, textTransform: 'uppercase', borderBottom: `4px solid ${INK}`, paddingBottom: '12px', marginBottom: '32px' }}>
                                    04. Top Performing Candidates
                                </h2>
                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '12px' }}>
                                    {reportData.top_performers.slice(0, 10).map((p: any, i: number) => (
                                        <div key={i} style={{ border: `2px solid ${INK}`, padding: '16px', background: CANVAS }}>
                                            <div style={{ fontFamily: FONT_MONO, fontSize: '9px', fontWeight: 800, color: MUTED }}>RANK {i + 1}</div>
                                            <div style={{ fontFamily: FONT_SANS, fontWeight: 800, fontSize: '14px', margin: '8px 0', minHeight: '34px', lineHeight: 1.2 }}>{p.name}</div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: `1px solid ${PANEL}`, paddingTop: '8px' }}>
                                                <span style={{ fontFamily: FONT_MONO, fontSize: '20px', fontWeight: 900, color: GREEN }}>{p.ats_score}</span>
                                                <div style={{ padding: '4px', background: INK, color: CANVAS, borderRadius: '4px', fontSize: '10px' }}>
                                                    <Trophy size={10} />
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Section 05: FULL STUDENT DIRECTORY & JOURNEY */}
                            <div style={{ pageBreakBefore: 'always' }}>
                                <h2 style={{ fontFamily: FONT_MONO, fontSize: '24px', fontWeight: 900, textTransform: 'uppercase', borderBottom: `4px solid ${INK}`, paddingBottom: '12px', marginBottom: '32px' }}>
                                    05. Comprehensive Journey Log
                                </h2>
                                <div style={{ border: `2px solid ${INK}` }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                                        <thead>
                                            <tr style={{ background: INK, color: CANVAS }}>
                                                <th style={{ padding: '12px 16px', fontFamily: FONT_MONO, fontSize: '11px', textTransform: 'uppercase' }}>Student Name</th>
                                                <th style={{ padding: '12px 16px', fontFamily: FONT_MONO, fontSize: '11px', textTransform: 'uppercase' }}>Email</th>
                                                <th style={{ padding: '12px 16px', fontFamily: FONT_MONO, fontSize: '11px', textTransform: 'uppercase' }}>Journey Status</th>
                                                <th style={{ padding: '12px 16px', fontFamily: FONT_MONO, fontSize: '11px', textTransform: 'uppercase', textAlign: 'right' }}>ATS Score</th>
                                                <th style={{ padding: '12px 16px', fontFamily: FONT_MONO, fontSize: '11px', textTransform: 'uppercase', textAlign: 'right' }}>Improvements</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {reportData.all_students.map((s: any, idx: number) => (
                                                <tr key={idx} style={{ borderBottom: `1px solid ${PANEL}`, background: idx % 2 === 0 ? CANVAS : '#f9f9f9' }}>
                                                    <td style={{ padding: '12px 16px', fontFamily: FONT_SANS, fontWeight: 700, fontSize: '13px' }}>{s.name}</td>
                                                    <td style={{ padding: '12px 16px', fontFamily: FONT_MONO, fontSize: '11px', color: MUTED }}>{s.email || '—'}</td>
                                                    <td style={{ padding: '12px 16px' }}>
                                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                            {s.status === 'ready' ? <CheckCircle2 size={12} color={GREEN} /> : s.status === 'processing' ? <RefreshCw size={12} color={BLUE} className="spin" /> : <X size={12} color={MUTED} />}
                                                            <span style={{ fontFamily: FONT_MONO, fontSize: '10px', textTransform: 'uppercase', fontWeight: 700 }}>
                                                                {s.status.replace('_', ' ')}
                                                            </span>
                                                        </div>
                                                    </td>
                                                    <td style={{ padding: '12px 16px', fontFamily: FONT_MONO, textAlign: 'right' }}>
                                                        {s.master_score !== null && s.tailored_score !== null ? (
                                                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                                                                <span style={{ fontSize: '9px', color: MUTED }}>{s.master_score} INITIAL</span>
                                                                <span style={{ 
                                                                    fontSize: '14px', 
                                                                    fontWeight: 900, 
                                                                    color: s.tailored_score >= 75 ? GREEN : s.tailored_score >= 50 ? ORANGE : RED 
                                                                }}>
                                                                    {s.tailored_score} OPTIMIZED
                                                                </span>
                                                            </div>
                                                        ) : (
                                                            <span style={{ 
                                                                fontSize: '14px', 
                                                                fontWeight: 900, 
                                                                color: s.ats_score ? (s.ats_score >= 75 ? GREEN : s.ats_score >= 50 ? ORANGE : RED) : MUTED 
                                                            }}>
                                                                {s.ats_score ?? '—'}
                                                            </span>
                                                        )}
                                                    </td>
                                                    <td style={{ padding: '12px 16px', fontFamily: FONT_MONO, fontSize: '11px', fontWeight: 800, textAlign: 'right' }}>
                                                        {s.tailored_count} tailored
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                            
                            {/* Footer for PDF */}
                            <div style={{ marginTop: '80px', borderTop: `1px solid ${PANEL}`, paddingTop: '24px', textAlign: 'center' }}>
                                <div style={{ fontFamily: FONT_MONO, fontSize: '9px', color: MUTED, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                                    End of Official Report // Page 01 of 01 // Generated by Resume Matcher AI
                                </div>
                            </div>
                        </div>

                    </div>
                </div>
            )}

            <style jsx>{`
                @keyframes pulse {
                    0% { opacity: 1; }
                    50% { opacity: 0.4; }
                    100% { opacity: 1; }
                }
                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }

                @media print {
                    .no-print, .dashboard-content { display: none !important; }
                    .modal-container, .modal-container * { 
                        visibility: visible !important; 
                    }
                    html, body { 
                        margin: 0 !important; 
                        padding: 0 !important; 
                        background: white !important;
                        overflow: visible !important;
                        height: auto !important;
                    }
                    .modal-container { 
                        position: static !important; 
                        width: 100% !important;
                        height: auto !important;
                        background: white !important; 
                        padding: 0 !important; 
                        margin: 0 !important;
                        overflow: visible !important;
                        display: block !important;
                        z-index: 9999 !important;
                    }
                    .report-paper { 
                        box-shadow: none !important; 
                        border: none !important; 
                        width: 100% !important;
                        max-width: none !important;
                        margin: 0 !important;
                        padding: 1cm !important;
                        background: white !important;
                        min-height: 0 !important;
                    }
                    table { page-break-inside: auto; }
                    tr { page-break-inside: avoid; page-break-after: auto; }
                    thead { display: table-header-group; }
                    tfoot { display: table-footer-group; }
                }
                @page {
                    margin: 0;
                    size: A4 portrait;
                }
            `}</style>
        </>
    );
}
