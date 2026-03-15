'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { apiFetch, apiPost, API_BASE } from '@/lib/api/client';
import { getUserId } from '@/lib/api/auth';
import { 
    Plus, Upload, FileText, CheckCircle2, AlertCircle, 
    Trophy, Users, Search, ChevronRight, BarChart3, 
    ArrowLeft, ExternalLink, RefreshCw, X, Download, PieChart
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

    const handleBulkUpload = async (files: FileList) => {
        if (!selectedCohort || files.length === 0) return;
        setUploading(true); setUploadResults(null);
        try {
            const fd = new FormData();
            for (let i = 0; i < files.length; i++) fd.append('files', files[i]);
            
            const endpoint = `/admin/cohorts/${selectedCohort}/bulk-upload-resumes`;
            const queryParams = scoringJobId.trim() ? `?job_id=${scoringJobId.trim()}` : '';
            
            const res = await apiFetch(`${endpoint}${queryParams}`, {
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
        <div style={{ padding: '40px', maxWidth: '1200px', margin: '0 auto' }}>
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
                                <button
                                    key={c.cohort_id}
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
                                    }}
                                >
                                    {c.name}
                                </button>
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
                                    <h3 style={{ fontFamily: FONT_MONO, fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '12px' }}>
                                        Bulk Upload
                                    </h3>
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
                                                        </div>
                                                        {s.progress.error && (
                                                            <div style={{ fontFamily: FONT_SANS, fontSize: '9px', color: RED, marginTop: '4px', maxWidth: '150px' }}>
                                                                {s.progress.error}
                                                            </div>
                                                        )}
                                                    </td>
                                                    <td style={{ padding: '12px 16px' }}>
                                                        {s.progress.ats_score !== null ? (
                                                            <span style={{ fontFamily: FONT_MONO, fontWeight: 800, fontSize: '20px', color: s.progress.ats_score >= 75 ? GREEN : s.progress.ats_score >= 50 ? ORANGE : RED }}>
                                                                {s.progress.ats_score}
                                                            </span>
                                                        ) : <span style={{ color: PANEL }}>—</span>}
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
                                                    <div style={{ textAlign: 'right', minWidth: '50px' }}>
                                                        {entry.ats_score !== null ? (
                                                            <span style={{ fontFamily: FONT_MONO, fontWeight: 800, fontSize: '24px', color: entry.ats_score >= 75 ? GREEN : entry.ats_score >= 50 ? ORANGE : RED }}>
                                                                {entry.ats_score}
                                                            </span>
                                                        ) : <span style={{ color: PANEL, fontFamily: FONT_MONO }}>—</span>}
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
                    .no-print { display: none !important; }
                    body { background: white !important; margin: 0; padding: 0; }
                    .modal-container { 
                        position: static !important; 
                        background: white !important; 
                        padding: 0 !important; 
                        overflow: visible !important;
                    }
                    .report-paper { 
                        box-shadow: none !important; 
                        border: none !important; 
                        width: 100% !important;
                        max-width: none !important;
                        margin: 0 !important;
                        padding: 0 !important;
                    }
                    @page {
                        margin: 1cm;
                    }
                }
            `}</style>
        </div>
    );
}
